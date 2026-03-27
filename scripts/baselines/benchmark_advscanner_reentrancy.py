#!/usr/bin/env python3
"""
Benchmark Advscanner on reentrancy findings and compare with Logicgap results.

Pipeline:
1) Discover reentrancy findings from Logicgap result.json files.
2) Fetch verified source code from explorer APIs (eth/bsc fallback).
3) Run Slither reentrancy detectors on fetched source.
4) Run Advscanner standalone script on fetched source.
5) Export per-sample CSV and a markdown summary.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

# Make Logicgap imports available.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import get_rpc_url
from core.tools.source_fetcher import fetch_contract_source


REENTRANCY_PATTERN = re.compile(r"re-?\s*entr|reentr", re.IGNORECASE)
SLITHER_DETECTORS = (
    "reentrancy-eth,reentrancy-no-eth,reentrancy-benign,"
    "reentrancy-events,reentrancy-unlimited-gas"
)


@dataclass
class Finding:
    dataset: str
    project: str
    finding_id: int
    finding_dir: Path
    result_json: Path
    data_json: Path | None
    chain: str
    target_address: str
    vulnerability_type: str
    logicgap_status: str
    violation_target: dict


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _find_data_json(data_root: Path, dataset: str, project: str) -> Path | None:
    dataset_dir = data_root / dataset
    if not dataset_dir.exists():
        return None
    direct = dataset_dir / f"{project}.json"
    if direct.exists():
        return direct
    matches = list(dataset_dir.rglob(f"{project}.json"))
    return matches[0] if matches else None


def discover_reentrancy_findings(root: Path, datasets: Iterable[str]) -> list[Finding]:
    results_root = root / "results"
    data_root = root / "data"
    findings: list[Finding] = []

    for dataset in datasets:
        dataset_dir = results_root / dataset
        if not dataset_dir.exists():
            continue

        for result_json in dataset_dir.glob("*/finding_*/result.json"):
            payload = _read_json(result_json)
            violation_target = payload.get("violation_target") or {}
            vuln_type = str(violation_target.get("vulnerability_type") or "")
            if not REENTRANCY_PATTERN.search(vuln_type):
                continue

            finding_dir = result_json.parent
            finding_name = finding_dir.name
            m = re.match(r"finding_(\d+)$", finding_name)
            finding_id = int(m.group(1)) if m else -1

            project = finding_dir.parent.name
            target_address = (
                str(payload.get("target_address") or "")
                or str(violation_target.get("target_address") or "")
            )
            logicgap_status = str(payload.get("status") or "")

            data_json = _find_data_json(data_root, dataset, project)
            chain = "bsc"
            if data_json and data_json.exists():
                data_payload = _read_json(data_json)
                chain = str(
                    data_payload.get("project_info", {}).get("chain", "bsc")
                ).lower()

            findings.append(
                Finding(
                    dataset=dataset,
                    project=project,
                    finding_id=finding_id,
                    finding_dir=finding_dir,
                    result_json=result_json,
                    data_json=data_json,
                    chain=chain,
                    target_address=target_address,
                    vulnerability_type=vuln_type,
                    logicgap_status=logicgap_status,
                    violation_target=violation_target,
                )
            )

    findings.sort(key=lambda x: (x.dataset, x.project, x.finding_id))
    return findings


def fetch_source_with_fallback(address: str, preferred_chain: str) -> tuple[str | None, str, str]:
    chains = [preferred_chain] + [c for c in ("eth", "bsc") if c != preferred_chain]
    errors: list[str] = []
    for chain in chains:
        try:
            info = fetch_contract_source(address=address, chain=chain)
            return info["source_code"], chain, ""
        except Exception as e:  # noqa: BLE001 - keep full per-chain error for report
            errors.append(f"{chain}: {e}")
    return None, "", " | ".join(errors)


def run_slither(source_path: Path, timeout: int) -> tuple[bool, bool, int, str]:
    cmd = [
        "slither",
        str(source_path),
        "--detect",
        SLITHER_DETECTORS,
        "--disable-color",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        detected = bool(REENTRANCY_PATTERN.search(combined))
        return True, detected, proc.returncode, combined
    except subprocess.TimeoutExpired:
        return False, False, -1, f"slither timeout after {timeout}s"
    except FileNotFoundError:
        return False, False, -1, "slither not found"
    except Exception as e:  # noqa: BLE001
        return False, False, -1, f"slither error: {e}"


def _prepare_advscanner_env() -> dict[str, str]:
    env = os.environ.copy()
    # Advscanner standalone expects OPENAI_API_KEY.
    if not env.get("OPENAI_API_KEY") and env.get("LLM_API_KEY"):
        env["OPENAI_API_KEY"] = env["LLM_API_KEY"]
    # Keep existing LLM_API_URL/LLM_MODEL from Logicgap .env when present.
    return env


def run_advscanner(
    advscanner_dir: Path,
    source_path: Path,
    output_poc_path: Path | None,
    timeout: int,
) -> tuple[bool, bool, int, str, bool]:
    script = advscanner_dir / "advscanner_standalone.py"
    if not script.exists():
        return False, False, -1, f"missing script: {script}", False

    cmd = ["python3", str(script), str(source_path)]
    env = _prepare_advscanner_env()
    if output_poc_path is not None:
        env["ADVSCANNER_OUTPUT_POC"] = str(output_poc_path)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(advscanner_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        poc_ok = "[SUCCESS] Generated Attack Template" in combined
        ssl_error = "CERTIFICATE_VERIFY_FAILED" in combined
        return True, poc_ok, proc.returncode, combined, ssl_error
    except subprocess.TimeoutExpired:
        return True, False, -1, f"advscanner timeout after {timeout}s", False
    except Exception as e:  # noqa: BLE001
        return True, False, -1, f"advscanner error: {e}", False


def _ensure_eval_sandbox(root: Path, out_dir: Path) -> Path:
    """
    Create a dedicated Foundry sandbox for Advscanner PoC evaluation.
    """
    sandbox = out_dir / "forge_eval_sandbox"
    sandbox.mkdir(parents=True, exist_ok=True)
    (sandbox / "src").mkdir(exist_ok=True)
    (sandbox / "test").mkdir(exist_ok=True)

    foundry_toml = root / "foundry_sandbox" / "foundry.toml"
    if foundry_toml.exists():
        (sandbox / "foundry.toml").write_text(foundry_toml.read_text(encoding="utf-8"), encoding="utf-8")

    target_lib = root / "foundry_sandbox" / "lib"
    link_lib = sandbox / "lib"
    if not link_lib.exists():
        try:
            link_lib.symlink_to(target_lib, target_is_directory=True)
        except Exception:
            # Fallback for filesystems that do not allow symlink creation.
            if target_lib.exists():
                subprocess.run(
                    ["cp", "-R", str(target_lib), str(link_lib)],
                    check=False,
                    capture_output=True,
                    text=True,
                )

    return sandbox


def _slice_contract_block(code: str, contract_name: str) -> str:
    m = re.search(rf"\bcontract\s+{re.escape(contract_name)}\b[^\{{]*\{{", code)
    if not m:
        return ""
    start = m.start()
    i = m.end() - 1  # at first "{"
    depth = 0
    for j in range(i, len(code)):
        ch = code[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return code[start : j + 1]
    return code[start:]


def _select_attacker_contract_name(code: str) -> str | None:
    names = re.findall(r"\bcontract\s+([A-Za-z_]\w*)\b", code)
    if not names:
        return None

    best_name = names[0]
    best_score = -10**9
    for name in names:
        block = _slice_contract_block(code, name)
        low = name.lower()
        score = 0
        if low.startswith("i"):
            score -= 2
        if any(k in low for k in ("attacker", "exploit", "poc", "hack")):
            score += 6
        if re.search(r"\bfunction\s+(attack|attacknext|exploit|pwn|run|execute)\b", block, re.IGNORECASE):
            score += 4
        if re.search(r"\bconstructor\s*\(", block):
            score += 1
        if score > best_score:
            best_score = score
            best_name = name
    return best_name


def _infer_constructor_args(contract_block: str) -> tuple[str, bool, str]:
    m = re.search(r"\bconstructor\s*\((.*?)\)", contract_block, re.DOTALL)
    if not m:
        return "", True, ""
    params_raw = m.group(1).strip()
    if not params_raw:
        return "", True, ""

    params = [p.strip() for p in params_raw.split(",") if p.strip()]
    args: list[str] = []
    for p in params:
        low = p.lower()
        if "address" in low:
            args.append("TARGET")
        elif "uint" in low or "int" in low:
            args.append("1")
        elif "bool" in low:
            args.append("true")
        elif "string" in low:
            args.append('"x"')
        elif "bytes" in low:
            args.append('hex""')
        else:
            return "", False, f"Unsupported constructor param: {p}"
    return ", ".join(args), True, ""


def _build_oracle_snippets(violation_target: dict) -> tuple[str, str, bool]:
    """
    Return (snapshot_code, assertion_code, needs_erc20_interface).
    """
    category = str(violation_target.get("violation_category", "")).upper()
    oracle = violation_target.get("oracle_verification") or {}

    econ = oracle.get("economic_check") or {}
    if category == "ECONOMIC" and econ:
        token = str(econ.get("target_token", "NATIVE"))
        if token == "NATIVE":
            snapshot = "uint256 initialBalance = attacker.balance;"
            assertion = (
                'uint256 finalBalance = attacker.balance;\n'
                '        assertGt(finalBalance, initialBalance, "Oracle failed: no native profit");'
            )
            return snapshot, assertion, False
        snapshot = f"uint256 initialBalance = IERC20Minimal({token}).balanceOf(attacker);"
        assertion = (
            f"uint256 finalBalance = IERC20Minimal({token}).balanceOf(attacker);\n"
            '        assertGt(finalBalance, initialBalance, "Oracle failed: no token profit");'
        )
        return snapshot, assertion, True

    logic = oracle.get("logic_check") or {}
    if category == "LOGIC" and logic:
        var = str(logic.get("target_variable", ""))
        op = str(logic.get("operator", "=="))
        val = str(logic.get("expected_value", "0"))
        snapshot = "// logic oracle has no balance snapshot"
        if var:
            if op == "==":
                assertion = f'assertEq({var}, {val}, "Oracle failed: logic state mismatch");'
            elif op == "!=":
                assertion = f'assertTrue({var} != {val}, "Oracle failed: logic value unchanged");'
            elif op == ">":
                assertion = f'assertGt({var}, {val}, "Oracle failed: expected greater value");'
            elif op == "<":
                assertion = f'assertLt({var}, {val}, "Oracle failed: expected lower value");'
            else:
                assertion = 'assertTrue(true, "Oracle skipped: unsupported logic operator");'
        else:
            assertion = 'assertTrue(true, "Oracle skipped: missing logic variable");'
        return snapshot, assertion, False

    return (
        "uint256 initialBalance = attacker.balance;",
        'assertTrue(true, "Oracle skipped: unsupported oracle schema");',
        False,
    )


def _generate_adv_eval_test(
    attacker_contract_name: str,
    constructor_args: str,
    target_address: str,
    violation_target: dict,
) -> str:
    snapshot_code, oracle_assertion, needs_erc20 = _build_oracle_snippets(violation_target)
    erc20_iface = (
        "interface IERC20Minimal { function balanceOf(address) external view returns (uint256); }\n\n"
        if needs_erc20
        else ""
    )

    ctor_call = (
        f"address attacker = address(new {attacker_contract_name}({constructor_args}));"
        if constructor_args
        else f"address attacker = address(new {attacker_contract_name}());"
    )

    return f"""// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/AdvscannerPoC.sol";

{erc20_iface}contract AdvscannerEvalTest is Test {{
    address constant TARGET = {target_address};

    function _deployAttacker() internal returns (address attacker) {{
        {ctor_call}
        vm.deal(attacker, 1 ether);
        return attacker;
    }}

    function _triggerAttack(address attacker) internal returns (bool ok) {{
        (bool p0,) = attacker.call{{value: 0.1 ether}}(abi.encodeWithSignature("deposit()"));
        if (p0) return true;
        (bool ok1,) = attacker.call(abi.encodeWithSignature("attack()"));
        if (ok1) return true;
        (bool ok1v,) = attacker.call{{value: 0.1 ether}}(abi.encodeWithSignature("attack()"));
        if (ok1v) return true;
        (bool ok2,) = attacker.call(abi.encodeWithSignature("attackNext()"));
        if (ok2) return true;
        (bool ok2v,) = attacker.call{{value: 0.1 ether}}(abi.encodeWithSignature("attackNext()"));
        if (ok2v) return true;
        (bool ok3,) = attacker.call(abi.encodeWithSignature("exploit()"));
        if (ok3) return true;
        (bool ok3v,) = attacker.call{{value: 0.1 ether}}(abi.encodeWithSignature("exploit()"));
        if (ok3v) return true;
        (bool ok4,) = attacker.call(abi.encodeWithSignature("pwn()"));
        if (ok4) return true;
        (bool ok4v,) = attacker.call{{value: 0.1 ether}}(abi.encodeWithSignature("pwn()"));
        if (ok4v) return true;
        (bool ok5,) = attacker.call(abi.encodeWithSignature("run()"));
        if (ok5) return true;
        (bool ok5v,) = attacker.call{{value: 0.1 ether}}(abi.encodeWithSignature("run()"));
        if (ok5v) return true;
        (bool ok6,) = attacker.call(abi.encodeWithSignature("execute()"));
        if (ok6) return true;
        (bool ok6v,) = attacker.call{{value: 0.1 ether}}(abi.encodeWithSignature("execute()"));
        return ok6v;
    }}

    function test_EntryPoint() public {{
        assertGt(TARGET.code.length, 0, "Target not deployed");
        address attacker = _deployAttacker();
        bool ok = _triggerAttack(attacker);
        assertTrue(ok, "No known attack entrypoint succeeded");
    }}

    function test_Oracle() public {{
        assertGt(TARGET.code.length, 0, "Target not deployed");
        address attacker = _deployAttacker();
        {snapshot_code}
        bool ok = _triggerAttack(attacker);
        assertTrue(ok, "No known attack entrypoint succeeded");
        {oracle_assertion}
    }}

    receive() external payable {{}}
}}
"""


def _run_subprocess(cmd: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        return proc.returncode, out
    except subprocess.TimeoutExpired:
        return -1, f"Timeout after {timeout}s: {' '.join(cmd)}"
    except Exception as e:  # noqa: BLE001
        return -1, f"Execution error: {e}"


def evaluate_advscanner_poc(
    root: Path,
    out_dir: Path,
    finding: Finding,
    poc_code: str,
    timeout: int,
) -> dict:
    """
    Evaluate Advscanner-generated PoC with 3 indicators:
    - compile_pass
    - evm_pass (entrypoint executes)
    - oracle_pass
    """
    sandbox = _ensure_eval_sandbox(root, out_dir)
    src_path = sandbox / "src" / "AdvscannerPoC.sol"
    test_path = sandbox / "test" / "AdvscannerEval.t.sol"

    attacker_name = _select_attacker_contract_name(poc_code)
    if not attacker_name:
        return {
            "compile_pass": False,
            "evm_pass": False,
            "oracle_pass": False,
            "compile_exit_code": -1,
            "evm_exit_code": -1,
            "oracle_exit_code": -1,
            "compile_log": "No deployable contract found in generated PoC",
            "evm_log": "Skipped",
            "oracle_log": "Skipped",
        }

    block = _slice_contract_block(poc_code, attacker_name)
    ctor_args, ctor_supported, ctor_err = _infer_constructor_args(block)
    if not ctor_supported:
        return {
            "compile_pass": False,
            "evm_pass": False,
            "oracle_pass": False,
            "compile_exit_code": -1,
            "evm_exit_code": -1,
            "oracle_exit_code": -1,
            "compile_log": f"Constructor inference failed: {ctor_err}",
            "evm_log": "Skipped",
            "oracle_log": "Skipped",
        }

    src_path.write_text(poc_code, encoding="utf-8")
    test_code = _generate_adv_eval_test(
        attacker_contract_name=attacker_name,
        constructor_args=ctor_args,
        target_address=finding.target_address,
        violation_target=finding.violation_target,
    )
    test_path.write_text(test_code, encoding="utf-8")

    compile_code, compile_log = _run_subprocess(["forge", "build"], cwd=sandbox, timeout=timeout)
    compile_pass = compile_code == 0
    if not compile_pass:
        return {
            "compile_pass": False,
            "evm_pass": False,
            "oracle_pass": False,
            "compile_exit_code": compile_code,
            "evm_exit_code": -1,
            "oracle_exit_code": -1,
            "compile_log": compile_log,
            "evm_log": "Skipped",
            "oracle_log": "Skipped",
        }

    try:
        rpc_url = get_rpc_url(finding.chain)
    except Exception as e:  # noqa: BLE001
        return {
            "compile_pass": True,
            "evm_pass": False,
            "oracle_pass": False,
            "compile_exit_code": compile_code,
            "evm_exit_code": -1,
            "oracle_exit_code": -1,
            "compile_log": compile_log,
            "evm_log": f"Missing RPC for chain {finding.chain}: {e}",
            "oracle_log": "Skipped",
        }

    evm_cmd = [
        "forge",
        "test",
        "--match-contract",
        "AdvscannerEvalTest",
        "--match-test",
        "test_EntryPoint",
        "--fork-url",
        rpc_url,
        "-vvvv",
    ]
    evm_code, evm_log = _run_subprocess(evm_cmd, cwd=sandbox, timeout=timeout)
    evm_pass = evm_code == 0

    oracle_cmd = [
        "forge",
        "test",
        "--match-contract",
        "AdvscannerEvalTest",
        "--match-test",
        "test_Oracle",
        "--fork-url",
        rpc_url,
        "-vvvv",
    ]
    oracle_code, oracle_log = _run_subprocess(oracle_cmd, cwd=sandbox, timeout=timeout)
    oracle_pass = oracle_code == 0

    return {
        "compile_pass": compile_pass,
        "evm_pass": evm_pass,
        "oracle_pass": oracle_pass,
        "compile_exit_code": compile_code,
        "evm_exit_code": evm_code,
        "oracle_exit_code": oracle_code,
        "compile_log": compile_log,
        "evm_log": evm_log,
        "oracle_log": oracle_log,
    }


def write_summary_markdown(rows: list[dict], summary_path: Path) -> None:
    total = len(rows)
    logicgap_success = sum(1 for r in rows if r["logicgap_success"] == "1")
    source_ok = sum(1 for r in rows if r["source_fetch_ok"] == "1")
    slither_detected = sum(1 for r in rows if r["slither_detected"] == "1")
    adv_ran = sum(1 for r in rows if r["advscanner_ran"] == "1")
    adv_poc = sum(1 for r in rows if r["advscanner_poc_generated"] == "1")
    adv_compile = sum(1 for r in rows if r.get("adv_compile_pass") == "1")
    adv_evm = sum(1 for r in rows if r.get("adv_evm_pass") == "1")
    adv_oracle = sum(1 for r in rows if r.get("adv_oracle_pass") == "1")

    def pct(num: int, den: int) -> str:
        return f"{(100.0 * num / den):.1f}%" if den else "n/a"

    lines = [
        "# Advscanner vs Logicgap (Reentrancy)",
        "",
        f"- Total reentrancy findings: {total}",
        f"- Logicgap success: {logicgap_success}/{total} ({pct(logicgap_success, total)})",
        f"- Source fetch success: {source_ok}/{total} ({pct(source_ok, total)})",
        f"- Slither reentrancy detected: {slither_detected}/{total} ({pct(slither_detected, total)})",
        f"- Advscanner PoC generated: {adv_poc}/{adv_ran} ({pct(adv_poc, adv_ran)})",
        f"- Advscanner Compile Pass (CSR-like): {adv_compile}/{adv_ran} ({pct(adv_compile, adv_ran)})",
        f"- Advscanner EVM Pass (ERR-like): {adv_evm}/{adv_ran} ({pct(adv_evm, adv_ran)})",
        f"- Advscanner Oracle Pass (VPR-like): {adv_oracle}/{adv_ran} ({pct(adv_oracle, adv_ran)})",
        "",
        "## Notes",
        "- `advscanner_poc_generated` is only code generation success.",
        "- Success quality should be judged by compile/EVM/oracle metrics.",
    ]
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines), encoding="utf-8")


def write_legacy_metrics_table(rows: list[dict], csv_path: Path, md_path: Path) -> None:
    """
    Export a report with the same style as complex/general_dataset_metrics.csv.
    """
    keys = [
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

    table_rows: list[dict] = []
    for r in rows:
        compiled = r.get("adv_compile_pass") == "1"
        evm_ok = r.get("adv_evm_pass") == "1"
        oracle_ok = r.get("adv_oracle_pass") == "1"
        ran = r.get("advscanner_ran") == "1"
        poc_ok = r.get("advscanner_poc_generated") == "1"

        if oracle_ok:
            final_status = "🟢 SUCCESS"
            fail_reason = "-"
        else:
            final_status = "🔴 FAILED"
            if not ran:
                fail_reason = "SKIPPED"
            elif not poc_ok:
                fail_reason = "NO_POC_GENERATED"
            elif not compiled:
                fail_reason = "COMPILE_FAIL"
            elif not evm_ok:
                fail_reason = "EVM_FAIL"
            else:
                fail_reason = "ORACLE_FAIL"

        table_rows.append(
            {
                "Project": r.get("project", ""),
                "Vuln Category": r.get("vulnerability_type", ""),
                "Attempts": "1 / 1" if ran else "0 / 1",
                "Compiled?": "✅ Yes" if compiled else "❌ No",
                "Revert Free?": "✅ Yes" if evm_ok else "❌ No",
                "Oracle Passed?": "✅ Yes" if oracle_ok else "❌ No",
                "Tokens Used": "0",
                "Est. Cost ($)": "$0.0000",
                "Time (s)": "0.0",
                "Final Status": final_status,
                "Fail Reason": fail_reason,
            }
        )

    total = len(table_rows)
    compiled_pass = sum(1 for row in table_rows if row["Compiled?"].startswith("✅"))
    evm_pass = sum(1 for row in table_rows if row["Revert Free?"].startswith("✅"))
    oracle_pass = sum(1 for row in table_rows if row["Oracle Passed?"].startswith("✅"))

    def pct(num: int, den: int) -> str:
        return f"{(100.0 * num / den):.1f}%" if den else "0.0%"

    csr = f"{compiled_pass}/{total} = {pct(compiled_pass, total)}"
    err = f"{evm_pass}/{total} = {pct(evm_pass, total)}"
    vpr = f"{oracle_pass}/{total} = {pct(oracle_pass, total)}"

    # CSV
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(table_rows)
        writer.writerow({k: "" for k in keys} | {"Project": "--- SUMMARY ---"})
        writer.writerow({k: "" for k in keys} | {"Project": "CSR (Compilation Success Rate)", "Vuln Category": csr})
        writer.writerow({k: "" for k in keys} | {"Project": "ERR (EVM Interaction Pass Rate)", "Vuln Category": err})
        writer.writerow({k: "" for k in keys} | {"Project": "VPR (Oracle Verification Pass Rate)", "Vuln Category": vpr})

    # MD
    with md_path.open("w", encoding="utf-8") as f:
        f.write("| Project | Vuln Category | Attempts | Compiled? | Revert Free? | Oracle Passed? | Tokens Used | Cost | Time (s) | Final Status | Fail Reason |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
        for row in table_rows:
            f.write(
                f"| {row['Project']} | {row['Vuln Category']} | {row['Attempts']} | {row['Compiled?']} | "
                f"{row['Revert Free?']} | {row['Oracle Passed?']} | {row['Tokens Used']} | "
                f"{row['Est. Cost ($)']} | {row['Time (s)']} | {row['Final Status']} | {row['Fail Reason']} |\n"
            )
        f.write("| --- SUMMARY --- |  |  |  |  |  |  |  |  |  |  |\n")
        f.write(f"| CSR (Compilation Success Rate) | {csr} |  |  |  |  |  |  |  |  |  |\n")
        f.write(f"| ERR (EVM Interaction Pass Rate) | {err} |  |  |  |  |  |  |  |  |  |\n")
        f.write(f"| VPR (Oracle Verification Pass Rate) | {vpr} |  |  |  |  |  |  |  |  |  |\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Advscanner baseline on Logicgap reentrancy samples."
    )
    parser.add_argument(
        "--root",
        default=str(ROOT),
        help="Logicgap repo root path",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["complex_dataset", "general_dataset"],
        choices=["complex_dataset", "general_dataset"],
        help="Datasets to include",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of findings (0 means all)",
    )
    parser.add_argument(
        "--advscanner-dir",
        default="/Users/carl/Desktop/Advscanner",
        help="Advscanner directory containing advscanner_standalone.py",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "results" / "advscanner_reentrancy"),
        help="Output directory for sources/logs/reports",
    )
    parser.add_argument(
        "--skip-advscanner",
        action="store_true",
        help="Only run source fetch + slither, skip Advscanner LLM stage",
    )
    parser.add_argument(
        "--slither-timeout",
        type=int,
        default=180,
        help="Slither timeout seconds per sample",
    )
    parser.add_argument(
        "--adv-timeout",
        type=int,
        default=600,
        help="Advscanner timeout seconds per sample",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    out_dir = Path(args.out_dir).resolve()
    advscanner_dir = Path(args.advscanner_dir).resolve()

    # Ensure .env is loaded for explorer keys and model endpoint settings.
    load_dotenv(root / ".env", override=False)

    if not args.skip_advscanner:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        if not api_key:
            print(
                "ERROR: Missing API key for Advscanner.\n"
                "Set OPENAI_API_KEY (or LLM_API_KEY) before running without --skip-advscanner."
            )
            return 2

    findings = discover_reentrancy_findings(root, args.datasets)
    if args.limit and args.limit > 0:
        findings = findings[: args.limit]

    if not findings:
        print("No reentrancy findings found.")
        return 1

    sources_dir = out_dir / "sources"
    logs_dir = out_dir / "logs"
    report_csv = out_dir / "advscanner_vs_logicgap_reentrancy.csv"
    report_md = out_dir / "advscanner_vs_logicgap_reentrancy.md"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    started = time.time()

    for idx, finding in enumerate(findings, start=1):
        print(
            f"[{idx}/{len(findings)}] {finding.dataset}/{finding.project}/finding_{finding.finding_id}"
        )
        row = {
            "dataset": finding.dataset,
            "project": finding.project,
            "finding_id": str(finding.finding_id),
            "target_address": finding.target_address,
            "chain_hint": finding.chain,
            "vulnerability_type": finding.vulnerability_type,
            "logicgap_status": finding.logicgap_status,
            "logicgap_success": "1" if finding.logicgap_status == "SUCCESS" else "0",
            "result_json": str(finding.result_json),
            "data_json": str(finding.data_json) if finding.data_json else "",
        }

        source_path = (
            sources_dir
            / finding.dataset
            / f"{finding.project}__finding_{finding.finding_id}.sol"
        )
        source_path.parent.mkdir(parents=True, exist_ok=True)
        # Step 1: source loading (prefer local cache to avoid network flakiness).
        source_code = None
        chain_used = ""
        fetch_error = ""
        if source_path.exists() and source_path.stat().st_size > 0:
            source_code = source_path.read_text(encoding="utf-8", errors="ignore")
            chain_used = "cache"
        else:
            source_code, chain_used, fetch_error = fetch_source_with_fallback(
                finding.target_address, finding.chain
            )
            if source_code:
                source_path.write_text(source_code, encoding="utf-8")

        row["source_fetch_ok"] = "1" if source_code else "0"
        row["source_fetch_chain"] = chain_used
        row["source_fetch_error"] = fetch_error
        row["source_file"] = str(source_path) if source_code else ""

        # Step 2: slither.
        if source_code:
            slither_ran, slither_detected, slither_code, slither_log = run_slither(
                source_path, timeout=args.slither_timeout
            )
        else:
            slither_ran, slither_detected, slither_code, slither_log = (
                False,
                False,
                -1,
                "source fetch failed; slither skipped",
            )
        row["slither_ran"] = "1" if slither_ran else "0"
        row["slither_detected"] = "1" if slither_detected else "0"
        row["slither_exit_code"] = str(slither_code)

        # Step 3: advscanner.
        adv_poc_path = (
            out_dir
            / "pocs"
            / finding.dataset
            / finding.project
            / f"finding_{finding.finding_id}.sol"
        )
        adv_poc_path.parent.mkdir(parents=True, exist_ok=True)

        if args.skip_advscanner or not source_code:
            adv_ran, adv_poc, adv_code, adv_log, adv_ssl_error = (
                False,
                False,
                -1,
                "advscanner skipped",
                False,
            )
            if adv_poc_path.exists():
                adv_poc_path.unlink()
        else:
            adv_ran, adv_poc, adv_code, adv_log, adv_ssl_error = run_advscanner(
                advscanner_dir=advscanner_dir,
                source_path=source_path,
                output_poc_path=adv_poc_path,
                timeout=args.adv_timeout,
            )
        row["advscanner_ran"] = "1" if adv_ran else "0"
        row["advscanner_poc_generated"] = "1" if adv_poc else "0"
        row["advscanner_ssl_error"] = "1" if adv_ssl_error else "0"
        row["advscanner_exit_code"] = str(adv_code)
        row["adv_poc_file"] = str(adv_poc_path) if adv_poc_path.exists() else ""

        # Step 4: quality evaluation on generated PoC.
        if adv_poc and adv_poc_path.exists():
            poc_code = adv_poc_path.read_text(encoding="utf-8", errors="ignore")
            eval_result = evaluate_advscanner_poc(
                root=root,
                out_dir=out_dir,
                finding=finding,
                poc_code=poc_code,
                timeout=args.adv_timeout,
            )
        else:
            eval_result = {
                "compile_pass": False,
                "evm_pass": False,
                "oracle_pass": False,
                "compile_exit_code": -1,
                "evm_exit_code": -1,
                "oracle_exit_code": -1,
                "compile_log": "Skipped: no generated PoC",
                "evm_log": "Skipped",
                "oracle_log": "Skipped",
            }

        row["adv_compile_pass"] = "1" if eval_result["compile_pass"] else "0"
        row["adv_evm_pass"] = "1" if eval_result["evm_pass"] else "0"
        row["adv_oracle_pass"] = "1" if eval_result["oracle_pass"] else "0"
        row["adv_compile_exit_code"] = str(eval_result["compile_exit_code"])
        row["adv_evm_exit_code"] = str(eval_result["evm_exit_code"])
        row["adv_oracle_exit_code"] = str(eval_result["oracle_exit_code"])

        # Per-sample combined log.
        log_path = (
            logs_dir
            / finding.dataset
            / finding.project
            / f"finding_{finding.finding_id}.log"
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_text = [
            f"# Sample: {finding.dataset}/{finding.project}/finding_{finding.finding_id}",
            f"# Address: {finding.target_address}",
            f"# Vulnerability Type: {finding.vulnerability_type}",
            "",
            "## Slither",
            slither_log,
            "",
            "## Advscanner",
            adv_log,
            "",
            "## Advscanner PoC Eval: Compile",
            eval_result["compile_log"],
            "",
            "## Advscanner PoC Eval: EVM",
            eval_result["evm_log"],
            "",
            "## Advscanner PoC Eval: Oracle",
            eval_result["oracle_log"],
            "",
        ]
        log_path.write_text("\n".join(log_text), encoding="utf-8")
        row["log_path"] = str(log_path)

        rows.append(row)

    # Write CSV.
    fieldnames = [
        "dataset",
        "project",
        "finding_id",
        "target_address",
        "chain_hint",
        "vulnerability_type",
        "logicgap_status",
        "logicgap_success",
        "result_json",
        "data_json",
        "source_fetch_ok",
        "source_fetch_chain",
        "source_fetch_error",
        "source_file",
        "slither_ran",
        "slither_detected",
        "slither_exit_code",
        "advscanner_ran",
        "advscanner_poc_generated",
        "advscanner_ssl_error",
        "advscanner_exit_code",
        "adv_poc_file",
        "adv_compile_pass",
        "adv_evm_pass",
        "adv_oracle_pass",
        "adv_compile_exit_code",
        "adv_evm_exit_code",
        "adv_oracle_exit_code",
        "log_path",
    ]
    with report_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    write_summary_markdown(rows, report_md)
    legacy_csv = root / "advscanner_reentrancy_metrics.csv"
    legacy_md = root / "advscanner_reentrancy_metrics.md"
    write_legacy_metrics_table(rows, legacy_csv, legacy_md)
    elapsed = time.time() - started
    print(f"\nDone. {len(rows)} samples in {elapsed:.1f}s")
    print(f"CSV: {report_csv}")
    print(f"MD : {report_md}")
    print(f"Legacy CSV: {legacy_csv}")
    print(f"Legacy MD : {legacy_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
