"""
Slither Analyzer Tool
Extracts function dependency graphs using the Slither static analysis framework.
"""

import json
import logging
import re
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def extract_program_facts(source_code: str) -> dict:
    """
    Extract deterministic, prompt-sized program facts for VES grounding.

    This intentionally favors stable facts over LLM summaries: externally
    callable functions, modifiers, branch predicates, storage-like declarations,
    token operations, and external interactions. Slither remains available for
    precise per-function slicing via get_function_dependencies().
    """
    clean = _strip_comments(source_code)
    facts = {
        "external_functions": [],
        "modifiers": [],
        "branch_predicates": [],
        "state_variables": [],
        "external_interactions": [],
        "token_operations": [],
        "sensitive_operations": [],
    }

    function_pattern = re.compile(
        r'function\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*([^{};]*)\{',
        re.MULTILINE
    )
    for match in function_pattern.finditer(clean):
        name = match.group(1)
        params = " ".join(match.group(2).split())
        attrs = " ".join(match.group(3).split())
        visibility = _extract_visibility(attrs)
        modifiers = _extract_modifiers(attrs)
        payable = "payable" in attrs.split()
        if visibility in {"external", "public"}:
            facts["external_functions"].append({
                "name": name,
                "params": params,
                "visibility": visibility,
                "modifiers": modifiers,
                "payable": payable,
            })

        body = _extract_body(clean, match.end() - 1)
        for predicate in re.findall(r'\b(?:require|assert|if)\s*\((.*?)\)', body, re.DOTALL):
            compact = " ".join(predicate.split())
            if compact and len(compact) <= 220:
                facts["branch_predicates"].append({
                    "function": name,
                    "predicate": compact,
                })

        for receiver, func in re.findall(r'\b([A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)\s*\(', body):
            if receiver in {"super", "this"}:
                continue
            entry = {"function": name, "target": receiver, "call": func}
            facts["external_interactions"].append(entry)
            if func in {"transfer", "transferFrom", "approve", "balanceOf", "mint", "burn"}:
                facts["token_operations"].append(entry)
            if func.lower() in {
                "call", "delegatecall", "send", "transfer", "swapexacttokensforethsupportingfeeontransfertokens",
                "swapexacttokensfortokenssupportingfeeontransfertokens", "addliquidityeth", "addliquidity",
            }:
                facts["sensitive_operations"].append(entry)

    for modifier_match in re.finditer(r'modifier\s+([A-Za-z_]\w*)\s*(?:\([^)]*\))?\s*\{', clean):
        name = modifier_match.group(1)
        body = _extract_body(clean, modifier_match.end() - 1)
        facts["modifiers"].append({
            "name": name,
            "guards": [" ".join(g.split()) for g in re.findall(r'\brequire\s*\((.*?)\)', body, re.DOTALL)[:5]],
        })

    state_pattern = re.compile(
        r'^\s*(?:mapping\s*\([^;]+\)|[A-Za-z_]\w*(?:\s*\[[^\]]*\])?)\s+'
        r'(?:public|private|internal|constant|immutable|override|\s)*'
        r'([A-Za-z_]\w*)\s*(?:=|;)',
        re.MULTILINE
    )
    for var in state_pattern.findall(clean):
        if var not in {"memory", "storage", "calldata"}:
            facts["state_variables"].append(var)

    for key in facts:
        if isinstance(facts[key], list):
            facts[key] = _dedupe(facts[key])[:60]
    return facts


def get_function_dependencies(
    source_code: str,
    target_function: str,
    contract_name: Optional[str] = None,
    compiler_version: Optional[str] = None,
) -> dict:
    """
    Use Slither to extract function dependencies for a target function.
    Performs backward slicing to find state variables read by the target
    function and which functions can modify them.

    Args:
        source_code: Solidity source code.
        target_function: Name of the function to analyze.
        contract_name: Optional contract name to focus analysis on.
        compiler_version: Optional compiler version to use.

    Returns:
        Dict with:
        - state_vars_read: State variables read by target function
        - state_vars_written: State variables written by target function
        - modifying_functions: Functions that modify the state vars read by target
        - internal_calls: Internal functions called by target
        - external_calls: External calls made by target
    """
    result = {
        "target_function": target_function,
        "state_vars_read": [],
        "state_vars_written": [],
        "modifying_functions": [],
        "internal_calls": [],
        "external_calls": [],
        "error": None,
    }

    try:
        result = _run_slither_analysis(
            source_code, target_function, contract_name, compiler_version
        )
    except Exception as e:
        logger.warning(f"Slither analysis failed, falling back to regex: {e}")
        result = _fallback_regex_analysis(source_code, target_function)
        result["error"] = f"Slither failed ({e}), used regex fallback"

    return result


def _strip_comments(source_code: str) -> str:
    source_code = re.sub(r'/\*.*?\*/', '', source_code, flags=re.DOTALL)
    source_code = re.sub(r'//.*', '', source_code)
    return source_code


def _extract_visibility(attrs: str) -> str:
    for visibility in ("external", "public", "internal", "private"):
        if re.search(rf'\b{visibility}\b', attrs):
            return visibility
    return "public"


def _extract_modifiers(attrs: str) -> list[str]:
    keywords = {
        "external", "public", "internal", "private", "payable", "view", "pure",
        "virtual", "override", "returns", "memory", "calldata", "storage",
    }
    mods = []
    attrs = re.sub(r'returns\s*\([^)]*\)', '', attrs)
    for token in re.findall(r'\b[A-Za-z_]\w*\b', attrs):
        if token not in keywords:
            mods.append(token)
    return mods


def _extract_body(source_code: str, open_brace_pos: int) -> str:
    depth = 0
    for pos in range(open_brace_pos, len(source_code)):
        char = source_code[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source_code[open_brace_pos + 1:pos]
    return ""


def _dedupe(items: list) -> list:
    seen = set()
    deduped = []
    for item in items:
        marker = json.dumps(item, sort_keys=True) if isinstance(item, dict) else item
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(item)
    return deduped


def _run_slither_analysis(
    source_code: str,
    target_function: str,
    contract_name: Optional[str] = None,
    compiler_version: Optional[str] = None,
) -> dict:
    """Run Slither analysis using the Python API."""
    from slither.slither import Slither

    result = {
        "target_function": target_function,
        "state_vars_read": [],
        "state_vars_written": [],
        "modifying_functions": [],
        "internal_calls": [],
        "external_calls": [],
        "error": None,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        sol_file = Path(tmpdir) / "Target.sol"
        sol_file.write_text(source_code)

        # Run slither
        try:
            slither_args = {}
            if compiler_version:
                # Extract version number (e.g., "v0.8.7+commit.xxx" -> "0.8.7")
                ver = compiler_version.lstrip("v").split("+")[0]
                slither_args["solc"] = f"solc-{ver}" if ver else None

            slither = Slither(str(sol_file), **{k: v for k, v in slither_args.items() if v})
        except Exception as e:
            logger.warning(f"Slither initialization failed: {e}")
            raise

        # Find the target contract
        target_contract = None
        for contract in slither.contracts:
            if contract_name and contract.name == contract_name:
                target_contract = contract
                break
            if not contract_name and not contract.is_library:
                target_contract = contract

        if not target_contract:
            raise ValueError(f"Contract not found: {contract_name or 'any non-library'}")

        # Find the target function
        target_func = None
        for func in target_contract.functions:
            if func.name == target_function:
                target_func = func
                break

        if not target_func:
            raise ValueError(f"Function '{target_function}' not found in {target_contract.name}")

        # Extract state variables read
        for var in target_func.state_variables_read:
            result["state_vars_read"].append(var.name)

        # Extract state variables written
        for var in target_func.state_variables_written:
            result["state_vars_written"].append(var.name)

        # Find modifying functions (backward slice)
        read_vars = set(v.name for v in target_func.state_variables_read)
        for func in target_contract.functions:
            if func.name == target_function:
                continue
            written_vars = set(v.name for v in func.state_variables_written)
            overlapping = read_vars & written_vars
            if overlapping:
                result["modifying_functions"].append({
                    "name": func.name,
                    "modifies": list(overlapping),
                    "visibility": str(func.visibility),
                })

        # Extract internal calls
        for call in target_func.internal_calls:
            if hasattr(call, "name"):
                result["internal_calls"].append(call.name)

        # Extract external calls (high-level)
        for call in target_func.high_level_calls:
            contract_type, func_called = call
            result["external_calls"].append({
                "contract": contract_type.name if hasattr(contract_type, "name") else str(contract_type),
                "function": func_called.name if hasattr(func_called, "name") else str(func_called),
            })

    return result


def _fallback_regex_analysis(source_code: str, target_function: str) -> dict:
    """
    Fallback regex-based analysis when Slither is unavailable.
    Less accurate but works without Slither installation.
    """
    import re

    result = {
        "target_function": target_function,
        "state_vars_read": [],
        "state_vars_written": [],
        "modifying_functions": [],
        "internal_calls": [],
        "external_calls": [],
        "error": None,
    }

    # Find the target function body
    func_pattern = re.compile(
        rf'function\s+{re.escape(target_function)}\s*\([^)]*\)[^{{]*\{{',
        re.MULTILINE
    )
    match = func_pattern.search(source_code)
    if not match:
        result["error"] = f"Function '{target_function}' not found in source"
        return result

    # Extract function body (simple brace matching)
    start = match.end()
    depth = 1
    pos = start
    while pos < len(source_code) and depth > 0:
        if source_code[pos] == '{':
            depth += 1
        elif source_code[pos] == '}':
            depth -= 1
        pos += 1

    func_body = source_code[start:pos - 1]

    # Find state variable references (heuristic: not declared locally)
    var_refs = re.findall(r'\b([a-zA-Z_]\w*)\b', func_body)

    # Find function calls in the body
    call_pattern = re.compile(r'\b([a-zA-Z_]\w*)\s*\(')
    for m in call_pattern.finditer(func_body):
        fname = m.group(1)
        if fname not in ('if', 'for', 'while', 'require', 'assert', 'emit', 'return'):
            result["internal_calls"].append(fname)

    # Find external calls (pattern: expr.func())
    ext_call_pattern = re.compile(r'(\w+)\.(\w+)\s*\(')
    for m in ext_call_pattern.finditer(func_body):
        result["external_calls"].append({
            "contract": m.group(1),
            "function": m.group(2),
        })

    return result


def format_dependencies_for_agent(deps: dict) -> str:
    """
    Format dependency analysis results into a human-readable string
    suitable for inclusion in an LLM prompt.
    """
    lines = [f"## Dependency Analysis for `{deps['target_function']}`\n"]

    if deps.get("error"):
        lines.append(f"⚠️ Analysis note: {deps['error']}\n")

    if deps["state_vars_read"]:
        lines.append("### State Variables Read:")
        for var in deps["state_vars_read"]:
            lines.append(f"  - `{var}`")

    if deps["state_vars_written"]:
        lines.append("### State Variables Written:")
        for var in deps["state_vars_written"]:
            lines.append(f"  - `{var}`")

    if deps["modifying_functions"]:
        lines.append("### Functions that Modify Read Variables (Backward Slice):")
        for func in deps["modifying_functions"]:
            modifies = ", ".join(f"`{v}`" for v in func.get("modifies", []))
            lines.append(f"  - `{func['name']}` (modifies: {modifies}, visibility: {func.get('visibility', '?')})")

    if deps["internal_calls"]:
        lines.append("### Internal Calls:")
        for call in deps["internal_calls"]:
            lines.append(f"  - `{call}`")

    if deps["external_calls"]:
        lines.append("### External Calls:")
        for call in deps["external_calls"]:
            lines.append(f"  - `{call['contract']}.{call['function']}()`")

    return "\n".join(lines)
