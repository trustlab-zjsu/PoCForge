"""
Pure LLM baseline for PoC generation.

This implements the baseline described in the paper's experimental setup:
the model receives the bug report, source code, ABI summary, and Foundry
constraints, then directly emits a complete Exploit.t.sol. It intentionally
does not use VES formalization, EDG planning, dependency tools, or feedback
repair loops.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import time
from pathlib import Path

from langchain_community.callbacks import get_openai_callback
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from core.config import (
    FOUNDRY_SANDBOX_DIR,
    LLM_API_KEY,
    LLM_API_URL,
    LLM_MAX_RETRIES,
    LLM_MODEL,
    LLM_REQUEST_TIMEOUT,
    get_rpc_url,
)
from core.executor import forge_runner, trace_parser
from core.main import load_target
from core.tools.code_writer import write_poc_to_disk
from core.tools.source_fetcher import fetch_contract_source
from core.utils import strip_solidity_comments

try:
    from web3 import Web3
except Exception:
    Web3 = None

logger = logging.getLogger("pure_llm_baseline")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPARISON_RESULTS_DIR = PROJECT_ROOT / "experimental_artifact" / "results" / "Comparison"
COMPARISON_STATS_DIR = PROJECT_ROOT / "experimental_artifact" / "Statistical Results" / "Comparison"
_SOURCE_CACHE: dict[tuple[str, str], tuple[str, dict]] = {}


SYSTEM_PROMPT = """You are an elite smart contract exploit developer. Your task is to produce a working Foundry PoC test from the report, ABI summary, source code, and chain context.

This is the pure LLM baseline. You must solve the task directly in one response. Do not request tools, do not ask for dependency analysis, do not use VES/EDG/planning-debt terminology, and do not rely on a later feedback or repair loop.

## Mission
Generate a complete `Exploit.t.sol` that:
1. Reaches the reported vulnerable behavior on the forked deployed contract.
2. Demonstrates the intended impact with concrete assertions.
3. Uses only information available in the report, ABI summary, source code, and target metadata.

## Foundry Patterns You May Use
```solidity
deal(address(this), 100 ether);
deal(tokenAddress, address(this), 1_000_000 * 1e18);

vm.prank(actor);
vm.startPrank(actor);
vm.stopPrank();

vm.warp(block.timestamp + 1 days);
vm.roll(block.number + 100);

vm.store(targetContract, bytes32(uint256(slot)), bytes32(value));
vm.label(targetAddress, "Target");
```

## Harness Requirements
1. Output exactly one full Solidity file wrapped in a ```solidity code block.
2. Import `forge-std/Test.sol` and define `contract ExploitTest is Test`.
3. Include all required interfaces in the same file; interact with deployed contracts through interfaces.
4. Define target/external addresses as constants or state variables using the supplied metadata/source/report.
5. Include `setUp()` when initialization, labels, baselines, approvals, or helper deployments are useful.
6. Include at least one `test...()` function that executes the exploit and asserts the impact.
7. For economic bugs, assert attacker balance/profit or victim balance loss. For logic bugs, assert the corrupted/unauthorized state.
8. Do not call `vm.createFork`, `vm.createSelectFork`, or `vm.rpcUrl`; the runner already executes `forge test` on the correct fork and optional fork block.
9. Keep the exploit focused. Prefer minimal fork-compatible calls over large unrelated scaffolding.
"""


def create_llm() -> ChatOpenAI:
    return ChatOpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_API_URL,
        model=LLM_MODEL,
        temperature=0.2,
        request_timeout=LLM_REQUEST_TIMEOUT,
        max_retries=LLM_MAX_RETRIES,
    )


def run_pure_llm_baseline(
    target_path: str,
    output_dir: str,
    finding_id: int | None = None,
    block_number: int | None = None,
) -> dict:
    started = time.time()
    target_input = load_target(target_path)
    project_id = Path(target_path).stem
    if project_id.endswith(".pdf"):
        project_id = project_id[:-4]

    finding = _select_finding(target_input, finding_id)
    if finding is None:
        raise ValueError("No finding selected for pure LLM baseline")

    source_code, contract_info = _load_source(target_path, target_input)
    rpc_url = get_rpc_url(target_input.project_info.chain)

    prompt = _build_prompt(
        target_input=target_input,
        finding=finding,
        source_code=source_code,
        contract_info=contract_info,
    )

    llm = create_llm()
    with get_openai_callback() as cb:
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

    poc_code = _normalize_addresses(_extract_solidity(response.content))
    result_dir = Path(output_dir) / project_id / f"finding_{finding.id}"
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "llm_response.txt").write_text(response.content, encoding="utf-8")

    if not poc_code:
        result = {
            "project_id": project_id,
            "finding_id": finding.id,
            "vulnerability_category": finding.title,
            "status": "ERROR",
            "compiled": False,
            "executed": False,
            "oracle_passed": False,
            "error_message": "LLM response did not contain a Solidity code block",
            "prompt_tokens": cb.prompt_tokens,
            "completion_tokens": cb.completion_tokens,
            "total_cost": cb.total_cost,
            "duration_seconds": time.time() - started,
        }
        _save_result(result_dir, result)
        return result

    (result_dir / "Exploit.t.sol").write_text(poc_code, encoding="utf-8")
    write_poc_to_disk(poc_code, str(FOUNDRY_SANDBOX_DIR))

    build_exit, build_stdout, build_stderr = forge_runner.build_only(FOUNDRY_SANDBOX_DIR)
    (result_dir / "forge_build_stdout.txt").write_text(build_stdout, encoding="utf-8")
    (result_dir / "forge_build_stderr.txt").write_text(build_stderr, encoding="utf-8")

    if build_exit != 0:
        error = trace_parser.parse(build_stdout, build_stderr)
        result = {
            "project_id": project_id,
            "finding_id": finding.id,
            "vulnerability_category": finding.title,
            "status": "FAILED",
            "compiled": False,
            "executed": False,
            "oracle_passed": False,
            "error": error.model_dump(mode="json"),
            "prompt_tokens": cb.prompt_tokens,
            "completion_tokens": cb.completion_tokens,
            "total_cost": cb.total_cost,
            "duration_seconds": time.time() - started,
        }
        _save_result(result_dir, result)
        return result

    test_exit, test_stdout, test_stderr = forge_runner.run(
        sandbox_dir=FOUNDRY_SANDBOX_DIR,
        rpc_url=rpc_url,
        block_number=block_number,
    )
    (result_dir / "forge_test_stdout.txt").write_text(test_stdout, encoding="utf-8")
    (result_dir / "forge_test_stderr.txt").write_text(test_stderr, encoding="utf-8")

    evidence = trace_parser.collect_evidence(test_stdout, test_stderr, exit_code=test_exit)
    result = {
        "project_id": project_id,
        "finding_id": finding.id,
        "vulnerability_category": finding.title,
        "status": "SUCCESS" if test_exit == 0 else "FAILED",
        "compiled": True,
        "executed": test_exit == 0,
        "oracle_passed": test_exit == 0,
        "execution_evidence": evidence.model_dump(mode="json"),
        "prompt_tokens": cb.prompt_tokens,
        "completion_tokens": cb.completion_tokens,
        "total_cost": cb.total_cost,
        "duration_seconds": time.time() - started,
    }
    if test_exit != 0:
        result["error"] = trace_parser.parse(test_stdout, test_stderr).model_dump(mode="json")

    _save_result(result_dir, result)
    return result


def run_pure_llm_batch(
    batch_dir: str,
    output_dir: str,
    severity_filter: list[str] | None = None,
    block_number: int | None = None,
    limit: int | None = None,
    metrics_csv: str | None = None,
) -> list[dict]:
    """Run the pure LLM baseline over all selected findings in a directory."""
    batch_path = Path(batch_dir)
    severity_filter = [s.lower() for s in (severity_filter or ["critical", "high", "medium"])]
    target_files = sorted({
        *batch_path.glob("**/*.pdf.json"),
        *batch_path.glob("**/*.json"),
    })
    if limit is not None:
        target_files = target_files[:limit]

    results = []
    for index, target_file in enumerate(target_files, 1):
        logger.info("[%s/%s] Pure LLM target: %s", index, len(target_files), target_file)
        try:
            target_input = load_target(str(target_file))
        except Exception as e:
            logger.error("Failed to load %s: %s", target_file, e)
            results.append({
                "project_id": target_file.stem,
                "finding_id": -1,
                "vulnerability_category": "LOAD_TARGET",
                "status": "ERROR",
                "error_message": str(e),
            })
            continue

        selected_findings = [
            finding for finding in target_input.findings
            if finding.severity.lower() in severity_filter
        ]
        if not selected_findings:
            logger.info("No selected findings in %s", target_file)
            continue

        for finding in selected_findings:
            try:
                results.append(run_pure_llm_baseline(
                    target_path=str(target_file),
                    output_dir=output_dir,
                    finding_id=finding.id,
                    block_number=block_number,
                ))
            except Exception as e:
                logger.error("Pure LLM failed for %s finding %s: %s", target_file, finding.id, e)
                result = {
                    "project_id": target_file.stem,
                    "finding_id": finding.id,
                    "vulnerability_category": finding.title,
                    "status": "ERROR",
                    "error_message": str(e),
                }
                results.append(result)

    summary = {
        "total": len(results),
        "success": sum(1 for r in results if r.get("status") == "SUCCESS"),
        "failed": sum(1 for r in results if r.get("status") == "FAILED"),
        "error": sum(1 for r in results if r.get("status") == "ERROR"),
        "results": results,
    }
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "batch_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if metrics_csv:
        write_metrics_csv(results, metrics_csv)
    logger.info("Pure LLM batch complete: %s", summary)
    return results


def write_metrics_csv(results: list[dict], output_csv: str | Path) -> None:
    """Write Comparison-compatible metrics CSV."""
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "Project",
        "Vuln Category",
        "Attempts",
        "Compiled?",
        "Revert Free?",
        "Oracle Passed?",
        "Tokens Used",
        "Est. Cost ($)",
        "Time (s)",
        "Final Status",
        "Fail Reason",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(_metrics_row(result))
    logger.info("Pure LLM metrics saved to %s", output_path)


def _metrics_row(result: dict) -> dict:
    status = result.get("status")
    compiled = bool(result.get("compiled"))
    executed = bool(result.get("executed"))
    oracle_passed = bool(result.get("oracle_passed"))
    prompt_tokens = int(result.get("prompt_tokens", 0) or 0)
    completion_tokens = int(result.get("completion_tokens", 0) or 0)
    total_tokens = prompt_tokens + completion_tokens
    return {
        "Project": result.get("project_id", ""),
        "Vuln Category": result.get("vulnerability_category", ""),
        "Attempts": "1 / 1",
        "Compiled?": "✅ Yes" if compiled else "❌ No",
        "Revert Free?": "✅ Yes" if executed else "❌ No",
        "Oracle Passed?": "✅ Yes" if oracle_passed else "❌ No",
        "Tokens Used": total_tokens,
        "Est. Cost ($)": f"${float(result.get('total_cost', 0.0) or 0.0):.4f}",
        "Time (s)": round(float(result.get("duration_seconds", 0.0) or 0.0), 1),
        "Final Status": "🟢 SUCCESS" if status == "SUCCESS" else "🔴 FAILED",
        "Fail Reason": _fail_reason(result),
    }


def _fail_reason(result: dict) -> str:
    if result.get("status") == "SUCCESS":
        return "-"
    if result.get("error_message"):
        return str(result["error_message"])[:120]
    error = result.get("error") or {}
    error_type = error.get("error_type")
    if error_type == "COMPILE_ERROR":
        return "COMPILE_FAIL"
    if error_type == "EVM_REVERT":
        return "EVM_FAIL"
    if error_type == "ASSERTION_FAILED":
        return "ASSERT_FAIL"
    return error_type or "ERROR"


def _load_source(target_path: str, target_input) -> tuple[str, dict]:
    target_dir = Path(target_path).parent
    local_sol_files = list(target_dir.glob("*.sol"))
    if local_sol_files:
        source_code = ""
        for sol_file in local_sol_files:
            source_code += f"// ===== {sol_file.name} =====\n"
            source_code += sol_file.read_text(encoding="utf-8") + "\n\n"
        return source_code, {
            "source_code": source_code,
            "abi": [],
            "contract_name": Path(target_path).stem,
            "compiler_version": target_input.project_info.compiler_version[0]
            if target_input.project_info.compiler_version else "0.8.20",
        }

    fetch_address = _primary_address(target_input.project_info.address)
    cache_key = (
        target_input.project_info.chain.lower(),
        fetch_address.lower(),
    )
    if cache_key in _SOURCE_CACHE:
        return _SOURCE_CACHE[cache_key]

    contract_info = fetch_contract_source(
        fetch_address,
        target_input.project_info.chain,
    )
    contract_info["selected_address"] = fetch_address
    contract_info["original_address"] = target_input.project_info.address
    result = (contract_info["source_code"], contract_info)
    _SOURCE_CACHE[cache_key] = result
    return result


def _build_prompt(target_input, finding, source_code: str, contract_info: dict) -> str:
    selected_address = contract_info.get("selected_address") or _primary_address(target_input.project_info.address)
    return f"""## Contract
- Address: {selected_address}
- Original Address Field: {target_input.project_info.address}
- Chain: {target_input.project_info.chain}
- Contract Name: {contract_info.get('contract_name', 'Unknown')}
- Compiler: {', '.join(target_input.project_info.compiler_version)}

## Vulnerability Finding
- ID: {finding.id}
- Title: {finding.title}
- Severity: {finding.severity}
- Location: {finding.location or 'Not specified'}
- Category: {json.dumps(finding.category, ensure_ascii=False)}
- Description: {finding.description}

## ABI Summary
{_format_abi_summary(contract_info.get('abi', []))}

## Source Code
```solidity
{strip_solidity_comments(source_code)}
```

## Direct Baseline Task
Generate a direct Foundry proof-of-concept exploit test for this single finding.

The output must be one complete `Exploit.t.sol` file. Use the supplied contract address as the deployed target unless the source/report identifies a more specific vulnerable deployed address. If the vulnerability depends on caller identity, token balances, timestamps, block numbers, storage state, or approvals, construct those conditions inside the test with standard Foundry cheatcodes.

Do not create or select a fork inside Solidity; assume the test already runs on the forked chain. Do not output JSON, explanations, VES, EDG, action schemas, or repair instructions.
"""


def _primary_address(address_field: str) -> str:
    """Return the first valid EVM address from a possibly multi-address field."""
    matches = re.findall(r'0x[a-fA-F0-9]{40}', address_field or "")
    if not matches:
        return address_field
    address = matches[0]
    if Web3 is None:
        return address
    try:
        return Web3.to_checksum_address(address)
    except Exception:
        return address


def _select_finding(target_input, finding_id: int | None):
    if finding_id is not None:
        for finding in target_input.findings:
            if finding.id == finding_id:
                return finding
        return None
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(
        target_input.findings,
        key=lambda item: severity_order.get(item.severity.lower(), 99),
    )[0] if target_input.findings else None


def _extract_solidity(text: str) -> str:
    match = re.search(r'```solidity\s*\n(.*?)\n```', text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r'```(?:\w+)?\s*\n(.*?)\n```', text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip() if "contract ExploitTest" in text else ""


def _normalize_addresses(code: str) -> str:
    if not code or Web3 is None:
        return code

    def replace(match: re.Match) -> str:
        address = match.group(0)
        try:
            return Web3.to_checksum_address(address)
        except Exception:
            return address

    return re.sub(r'0x[a-fA-F0-9]{40}', replace, code)


def _format_abi_summary(abi: list) -> str:
    functions = [item for item in abi if item.get("type") == "function"]
    if not functions:
        return "No ABI available."
    lines = []
    for func in functions[:40]:
        inputs = ", ".join(
            f"{item.get('type', '?')} {item.get('name', '')}" for item in func.get("inputs", [])
        )
        mutability = func.get("stateMutability", "")
        lines.append(f"- {func['name']}({inputs}) [{mutability}]")
    return "\n".join(lines)


def _save_result(result_dir: Path, result: dict) -> None:
    (result_dir / "result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def infer_run_name(path: str | None) -> str:
    if not path:
        return "pure_llm_single"
    normalized = str(path).lower()
    if "d_mix" in normalized or "dmix" in normalized:
        return "pure_llm_D_mix"
    if "d_log" in normalized or "dlog" in normalized:
        return "pure_llm_D_log"
    return "pure_llm"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run pure LLM PoC generation baseline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--target", help="Path to a single target JSON")
    group.add_argument("--batch", help="Path to a directory containing target JSON files")
    parser.add_argument("--finding-id", type=int, default=None)
    parser.add_argument("--output", "-o", default=None)
    parser.add_argument("--metrics-csv", default=None)
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--block-number", type=int, default=None)
    parser.add_argument("--severity", nargs="+", default=["critical", "high", "medium"])
    parser.add_argument("--limit", type=int, default=None, help="Limit target files in batch mode")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    run_name = args.run_name or infer_run_name(args.batch or args.target)
    output_dir = args.output or str(COMPARISON_RESULTS_DIR / run_name)
    metrics_csv = args.metrics_csv or str(COMPARISON_STATS_DIR / f"{run_name}_metrics.csv")
    if args.target:
        result = run_pure_llm_baseline(
            target_path=args.target,
            output_dir=output_dir,
            finding_id=args.finding_id,
            block_number=args.block_number,
        )
        write_metrics_csv([result], metrics_csv)
        logger.info("Pure LLM baseline result: %s", result["status"])
    else:
        run_pure_llm_batch(
            batch_dir=args.batch,
            output_dir=output_dir,
            severity_filter=args.severity,
            block_number=args.block_number,
            limit=args.limit,
            metrics_csv=metrics_csv,
        )


if __name__ == "__main__":
    main()
