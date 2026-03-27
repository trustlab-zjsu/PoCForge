#!/usr/bin/env python3
"""
Benchmark Quimera on Logicgap complex_dataset and export 3-layer metrics.

Outputs:
1) Detailed comparison CSV/MD under results/quimera_complex/
2) Legacy-style metrics CSV/MD at repo root:
   - quimera_complex_metrics.csv
   - quimera_complex_metrics.md
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Make Logicgap imports available.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import get_rpc_url


@dataclass
class Finding:
    dataset: str
    project: str
    finding_id: int
    result_json: Path
    data_json: Path | None
    target_address: str
    chain: str
    vulnerability_type: str
    violation_category: str
    has_economic_oracle: bool
    logicgap_status: str


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _find_data_json(root: Path, dataset: str, project: str) -> Path | None:
    # Current dataset layout keeps files under data/<dataset>/<dataset>/*.json
    candidates = [
        root / "data" / dataset / f"{project}.json",
        root / "data" / dataset / dataset / f"{project}.json",
        root / "data" / dataset / dataset / f"{project}.pdf.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    nested = list((root / "data" / dataset).rglob(f"{project}.json"))
    if nested:
        return nested[0]
    nested_pdf = list((root / "data" / dataset).rglob(f"{project}.pdf.json"))
    return nested_pdf[0] if nested_pdf else None


def discover_complex_findings(root: Path) -> list[Finding]:
    dataset = "complex_dataset"
    findings: list[Finding] = []
    results_root = root / "results" / dataset
    if not results_root.exists():
        return findings

    for result_json in results_root.glob("*/finding_*/result.json"):
        payload = _read_json(result_json)
        project = result_json.parent.parent.name
        finding_name = result_json.parent.name
        try:
            finding_id = int(finding_name.split("_", 1)[1])
        except Exception:
            finding_id = -1

        data_json = _find_data_json(root, dataset, project)
        chain = "bsc"
        if data_json and data_json.exists():
            data_payload = _read_json(data_json)
            chain = str(
                (data_payload.get("project_info") or {}).get("chain", "bsc")
            ).lower()
        if chain == "mainnet":
            chain = "eth"

        target_address = str(payload.get("target_address") or "").strip()
        violation_target = payload.get("violation_target") or {}
        vuln_type = str(violation_target.get("vulnerability_type") or "")
        violation_category = str(violation_target.get("violation_category") or "").upper()
        economic_check = (violation_target.get("oracle_verification") or {}).get("economic_check")
        logicgap_status = str(payload.get("status") or "")

        findings.append(
            Finding(
                dataset=dataset,
                project=project,
                finding_id=finding_id,
                result_json=result_json,
                data_json=data_json,
                target_address=target_address,
                chain=chain,
                vulnerability_type=vuln_type,
                violation_category=violation_category,
                has_economic_oracle=bool(economic_check),
                logicgap_status=logicgap_status,
            )
        )

    findings.sort(key=lambda x: (x.project, x.finding_id))
    return findings


def _chain_for_quimera(chain: str) -> str:
    if chain.lower() in ("eth", "ethereum", "mainnet"):
        return "mainnet"
    if chain.lower() in ("bsc", "bnb"):
        return "bsc"
    return chain.lower()


def _is_network_failure_text(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    network_markers = (
        "failed to resolve",
        "nameresolutionerror",
        "max retries exceeded",
        "incomplete chunked read",
        "connection reset by peer",
        "connection aborted",
        "read timed out",
        "request timed out",
        "temporary failure in name resolution",
        "nodename nor servname provided",
        "could not resolve host",
        "failed to get latest block number",
        "explorer api error",
        "you are using a deprecated v1 endpoint",
        "missing/invalid api key",
        "rate limit reached",
        "429 too many requests",
        "status code: 429",
    )
    return any(m in low for m in network_markers)


def _rpc_candidates_from_env(chain: str) -> list[str]:
    chain = chain.lower()
    urls: list[str] = []
    if chain == "bsc":
        urls.extend(
            [
                os.getenv("BSC_RPC_URL", ""),
                "https://bsc-dataseed.binance.org",
                "https://bsc-rpc.publicnode.com",
            ]
        )
    else:
        urls.extend(
            [
                os.getenv("ETH_RPC_URL", ""),
                "https://eth-mainnet.public.blastapi.io",
                "https://eth.llamarpc.com",
                "https://rpc.flashbots.net",
            ]
        )
    seen = set()
    out: list[str] = []
    for u in urls:
        if not u:
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def _run_subprocess(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 600,
) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        return proc.returncode, out
    except subprocess.TimeoutExpired:
        return -1, f"Timeout after {timeout}s: {' '.join(cmd)}"
    except Exception as e:  # noqa: BLE001
        return -1, f"Execution error: {e}"


def get_latest_block_number(rpc_url: str) -> int | None:
    code, out = _run_subprocess(["cast", "block-number", "--rpc-url", rpc_url], timeout=60)
    if code != 0:
        return None
    s = out.strip().splitlines()
    if not s:
        return None
    try:
        return int(s[-1].strip())
    except Exception:
        return None


def run_quimera_once(
    root: Path,
    finding: Finding,
    rpc_url: str,
    block_number: int,
    model: str,
    iterations: int,
    timeout: int,
    quimera_root: Path,
    venv_python: Path,
    run_dir: Path,
) -> tuple[int, str]:
    helper = root / "scripts" / "quimera_headless_once.py"
    target = finding.target_address
    chain = _chain_for_quimera(finding.chain)

    env = os.environ.copy()
    if not env.get("OPENAI_API_KEY") and env.get("LLM_API_KEY"):
        env["OPENAI_API_KEY"] = env["LLM_API_KEY"]
    if not env.get("OPENAI_BASE_URL") and env.get("LLM_API_URL"):
        env["OPENAI_BASE_URL"] = env["LLM_API_URL"]
    env["FOUNDRY_RPC_URL"] = rpc_url
    env["FOUNDRY_FORK_BLOCK_NUMBER"] = str(block_number)

    cmd = [
        str(venv_python),
        str(helper),
        "--quimera-root",
        str(quimera_root),
        "--target",
        target,
        "--chain",
        chain,
        "--block-number",
        str(block_number),
        "--model",
        model,
        "--iterations",
        str(iterations),
        "--working-dir",
        str(run_dir),
    ]
    return _run_subprocess(cmd=cmd, timeout=timeout, env=env)


def locate_quimera_iteration(run_dir: Path) -> tuple[Path | None, Path | None, int]:
    session_root = run_dir / "quimera_foundry_sessions"
    if not session_root.exists():
        return None, None, -1
    addr_dirs = [p for p in session_root.iterdir() if p.is_dir()]
    if not addr_dirs:
        return None, None, -1
    addr_dir = max(addr_dirs, key=lambda p: p.stat().st_mtime)
    iter_dirs = [p for p in addr_dir.iterdir() if p.is_dir() and p.name.isdigit()]
    if not iter_dirs:
        return addr_dir, None, -1
    iter_dir = max(iter_dirs, key=lambda p: int(p.name))
    return addr_dir, iter_dir, int(iter_dir.name)


def evaluate_quimera_test(
    iter_dir: Path,
    rpc_candidates: list[str],
    timeout: int,
    network_retries: int,
) -> dict:
    test_file = iter_dir / "test" / "Test.t.sol"
    if not test_file.exists():
        return {
            "compile_pass": False,
            "evm_pass": False,
            "oracle_pass": False,
            "compile_exit_code": -1,
            "evm_exit_code": -1,
            "compile_log": "Missing generated test/Test.t.sol",
            "evm_log": "Skipped",
            "oracle_log": "Skipped",
        }

    compile_code, compile_log = _run_subprocess(
        ["forge", "build"],
        cwd=iter_dir,
        timeout=timeout,
    )
    compile_pass = compile_code == 0
    if not compile_pass:
        return {
            "compile_pass": False,
            "evm_pass": False,
            "oracle_pass": False,
            "compile_exit_code": compile_code,
            "evm_exit_code": -1,
            "compile_log": compile_log,
            "evm_log": "Skipped",
            "oracle_log": "Skipped",
        }

    # EVM/oracle evaluation with RPC fallback and network retries.
    evm_code = -1
    evm_log = "Skipped"
    for rpc_url in rpc_candidates:
        attempts = max(1, network_retries)
        for _ in range(attempts):
            code, log = _run_subprocess(
                ["forge", "test", "--fork-url", rpc_url, "-vvv"],
                cwd=iter_dir,
                timeout=timeout,
            )
            evm_code, evm_log = code, log
            if code == 0:
                break
            if not _is_network_failure_text(log):
                break
        if evm_code == 0:
            break
        if not _is_network_failure_text(evm_log):
            break

    evm_pass = evm_code == 0
    oracle_pass = evm_pass  # Quimera oracle is embedded in testFlaw() assertions.
    return {
        "compile_pass": compile_pass,
        "evm_pass": evm_pass,
        "oracle_pass": oracle_pass,
        "compile_exit_code": compile_code,
        "evm_exit_code": evm_code,
        "compile_log": compile_log,
        "evm_log": evm_log,
        "oracle_log": evm_log,
    }


def write_summary_markdown(rows: list[dict], path: Path) -> None:
    total = len(rows)
    logicgap_success = sum(1 for r in rows if r["logicgap_success"] == "1")
    ran = sum(1 for r in rows if r["quimera_ran"] == "1")
    compile_ok = sum(1 for r in rows if r["quimera_compile_pass"] == "1")
    evm_ok = sum(1 for r in rows if r["quimera_evm_pass"] == "1")
    oracle_ok = sum(1 for r in rows if r["quimera_oracle_pass"] == "1")

    def pct(num: int, den: int) -> str:
        return f"{(100.0 * num / den):.1f}%" if den else "n/a"

    lines = [
        "# Quimera vs Logicgap (Complex Dataset)",
        "",
        f"- Total findings: {total}",
        f"- Logicgap success: {logicgap_success}/{total} ({pct(logicgap_success, total)})",
        f"- Quimera executed: {ran}/{total} ({pct(ran, total)})",
        f"- Quimera Compile Pass (CSR-like): {compile_ok}/{ran} ({pct(compile_ok, ran)})",
        f"- Quimera EVM Pass (ERR-like): {evm_ok}/{ran} ({pct(evm_ok, ran)})",
        f"- Quimera Oracle Pass (VPR-like): {oracle_ok}/{ran} ({pct(oracle_ok, ran)})",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_legacy_metrics_table(rows: list[dict], csv_path: Path, md_path: Path) -> None:
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
        compiled = r.get("quimera_compile_pass") == "1"
        evm_ok = r.get("quimera_evm_pass") == "1"
        oracle_ok = r.get("quimera_oracle_pass") == "1"
        ran = r.get("quimera_ran") == "1"
        timeout_flag = r.get("quimera_timeout") == "1"

        if oracle_ok:
            final_status = "🟢 SUCCESS"
            fail_reason = "-"
        else:
            final_status = "🔴 FAILED"
            if timeout_flag:
                fail_reason = "TIMEOUT"
            elif not ran:
                fail_reason = "SKIPPED"
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
                "Attempts": r.get("attempts", "1 / 1"),
                "Compiled?": "✅ Yes" if compiled else "❌ No",
                "Revert Free?": "✅ Yes" if evm_ok else "❌ No",
                "Oracle Passed?": "✅ Yes" if oracle_ok else "❌ No",
                "Tokens Used": "0",
                "Est. Cost ($)": "$0.0000",
                "Time (s)": r.get("elapsed_seconds", "0.0"),
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

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(table_rows)
        writer.writerow({k: "" for k in keys} | {"Project": "--- SUMMARY ---"})
        writer.writerow({k: "" for k in keys} | {"Project": "CSR (Compilation Success Rate)", "Vuln Category": csr})
        writer.writerow({k: "" for k in keys} | {"Project": "ERR (EVM Interaction Pass Rate)", "Vuln Category": err})
        writer.writerow({k: "" for k in keys} | {"Project": "VPR (Oracle Verification Pass Rate)", "Vuln Category": vpr})

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
        description="Run Quimera baseline on Logicgap complex_dataset."
    )
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--quimera-root", default="/Users/carl/quimera")
    parser.add_argument(
        "--venv-python",
        default=sys.executable,
        help="Python executable used to invoke quimera_headless_once.py",
    )
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0, help="0 means all findings")
    parser.add_argument("--timeout", type=int, default=1200, help="Quimera run timeout per sample")
    parser.add_argument("--eval-timeout", type=int, default=600, help="Evaluation timeout per sample")
    parser.add_argument(
        "--network-retries",
        type=int,
        default=3,
        help="Retries per RPC candidate when network failures are detected",
    )
    parser.add_argument(
        "--only-economic",
        action="store_true",
        help="Only include findings with ECONOMIC category/economic oracle",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "results" / "quimera_complex"),
    )
    parser.add_argument("--clean-runs", action="store_true", help="Delete old per-sample run dirs before execution")
    parser.add_argument(
        "--legacy-prefix",
        default="quimera_complex",
        help="Prefix for legacy metrics files under repo root, e.g. '<prefix>_metrics.csv'",
    )
    parser.add_argument(
        "--retry-csv",
        default="",
        help="Optional previous detailed CSV path; restrict execution to listed samples",
    )
    parser.add_argument(
        "--retry-network-only",
        action="store_true",
        help="When --retry-csv is set, only keep rows with quimera_network_error=1",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    quimera_root = Path(args.quimera_root).resolve()
    # Keep virtualenv interpreter symlink path intact; resolving may collapse it
    # to base Python and drop virtualenv site-packages.
    venv_python = Path(args.venv_python).expanduser()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    load_dotenv(root / ".env", override=False)
    if not os.getenv("ETHERSCAN_API_KEY"):
        print("ERROR: ETHERSCAN_API_KEY is required.")
        return 2

    # Quimera needs an LLM key. Reuse OPENAI_API_KEY or fallback to LLM_API_KEY.
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")):
        print("ERROR: Missing OPENAI_API_KEY/LLM_API_KEY for Quimera model calls.")
        return 2

    findings = discover_complex_findings(root)
    if args.only_economic:
        findings = [
            f
            for f in findings
            if f.violation_category == "ECONOMIC" or f.has_economic_oracle
        ]
    if args.retry_csv:
        retry_path = Path(args.retry_csv).expanduser()
        allowed: set[tuple[str, int]] = set()
        if retry_path.exists():
            with retry_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    if args.retry_network_only and str(r.get("quimera_network_error", "0")) != "1":
                        continue
                    project = str(r.get("project", "")).strip()
                    fid_raw = str(r.get("finding_id", "")).strip()
                    if not project or not fid_raw:
                        continue
                    try:
                        fid = int(fid_raw)
                    except Exception:
                        continue
                    allowed.add((project, fid))
        findings = [f for f in findings if (f.project, f.finding_id) in allowed]
    if args.limit and args.limit > 0:
        findings = findings[: args.limit]
    if not findings:
        print("No findings found in complex_dataset.")
        return 1

    # Resolve chain-level RPC candidates.
    rpc_candidates_by_chain: dict[str, list[str]] = {}
    for chain in ("eth", "bsc"):
        candidates: list[str] = []
        try:
            preferred = get_rpc_url(chain)
            if preferred:
                candidates.append(preferred)
        except Exception:
            pass
        candidates.extend(_rpc_candidates_from_env(chain))
        dedup: list[str] = []
        seen = set()
        for url in candidates:
            if not url or url in seen:
                continue
            seen.add(url)
            dedup.append(url)
        rpc_candidates_by_chain[chain] = dedup

    rows: list[dict] = []
    started = time.time()

    logs_dir = out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    for idx, finding in enumerate(findings, start=1):
        print(f"[{idx}/{len(findings)}] {finding.project}/finding_{finding.finding_id}")
        chain = finding.chain if finding.chain in ("eth", "bsc") else "bsc"
        rpc_candidates = rpc_candidates_by_chain.get(chain, [])
        used_rpc = ""
        used_block = ""
        row = {
            "dataset": finding.dataset,
            "project": finding.project,
            "finding_id": str(finding.finding_id),
            "target_address": finding.target_address,
            "chain_hint": chain,
            "vulnerability_type": finding.vulnerability_type,
            "logicgap_status": finding.logicgap_status,
            "logicgap_success": "1" if finding.logicgap_status == "SUCCESS" else "0",
            "result_json": str(finding.result_json),
            "data_json": str(finding.data_json) if finding.data_json else "",
            "attempts": f"{args.iterations} / {args.iterations}",
            "violation_category": finding.violation_category,
        }

        if not finding.target_address or not rpc_candidates:
            row |= {
                "quimera_ran": "0",
                "quimera_timeout": "0",
                "quimera_exit_code": "-1",
                "quimera_network_error": "0",
                "quimera_used_rpc": "",
                "quimera_used_block": "",
                "quimera_run_dir": "",
                "quimera_log_file": "",
                "quimera_session_dir": "",
                "quimera_iteration_dir": "",
                "quimera_iteration": "-1",
                "quimera_test_file": "",
                "quimera_response_file": "",
                "quimera_compile_pass": "0",
                "quimera_evm_pass": "0",
                "quimera_oracle_pass": "0",
                "quimera_compile_exit_code": "-1",
                "quimera_evm_exit_code": "-1",
                "elapsed_seconds": "0.0",
                "log_path": "",
            }
            rows.append(row)
            continue

        run_dir = out_dir / "runs" / finding.project / f"finding_{finding.finding_id}"
        if args.clean_runs and run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)

        t0 = time.time()
        exit_code = -1
        run_output = ""
        network_error = False
        # Retry with RPC fallback only for network failures.
        for rpc_url in rpc_candidates:
            retries = max(1, args.network_retries)
            for _ in range(retries):
                block_number = get_latest_block_number(rpc_url)
                if block_number is None:
                    exit_code = 1
                    run_output = f"Network error: failed to query block number from {rpc_url}"
                    network_error = True
                    continue

                used_rpc = rpc_url
                used_block = str(block_number)
                exit_code, run_output = run_quimera_once(
                    root=root,
                    finding=finding,
                    rpc_url=rpc_url,
                    block_number=block_number,
                    model=args.model,
                    iterations=args.iterations,
                    timeout=args.timeout,
                    quimera_root=quimera_root,
                    venv_python=venv_python,
                    run_dir=run_dir,
                )
                if exit_code == 0:
                    break
                network_error = _is_network_failure_text(run_output)
                if not network_error:
                    break
            if exit_code == 0:
                break
            if not network_error:
                break

        elapsed = time.time() - t0
        timeout_flag = exit_code == -1

        log_file = run_dir / "quimera.log"
        addr_dir, iter_dir, iter_id = locate_quimera_iteration(run_dir)
        test_file = (iter_dir / "test" / "Test.t.sol") if iter_dir else None
        response_file = (iter_dir / "response.txt") if iter_dir else None

        if iter_dir and iter_dir.exists():
            eval_rpcs = []
            if used_rpc:
                eval_rpcs.append(used_rpc)
            for u in rpc_candidates:
                if u not in eval_rpcs:
                    eval_rpcs.append(u)
            eval_result = evaluate_quimera_test(
                iter_dir=iter_dir,
                rpc_candidates=eval_rpcs,
                timeout=args.eval_timeout,
                network_retries=args.network_retries,
            )
        else:
            eval_result = {
                "compile_pass": False,
                "evm_pass": False,
                "oracle_pass": False,
                "compile_exit_code": -1,
                "evm_exit_code": -1,
                "compile_log": "No iteration directory produced by Quimera",
                "evm_log": "Skipped",
                "oracle_log": "Skipped",
            }

        per_sample_log = (
            logs_dir / finding.project / f"finding_{finding.finding_id}.log"
        )
        per_sample_log.parent.mkdir(parents=True, exist_ok=True)
        quimera_log_text = log_file.read_text(encoding="utf-8", errors="ignore") if log_file.exists() else ""
        merged = [
            f"# Sample: {finding.project}/finding_{finding.finding_id}",
            f"# Address: {finding.target_address}",
            f"# Chain: {chain}",
            f"# Quimera Exit: {exit_code}",
            "",
            "## Quimera stdout/stderr",
            run_output,
            "",
            "## quimera.log",
            quimera_log_text,
            "",
            "## Evaluation: Compile",
            eval_result["compile_log"],
            "",
            "## Evaluation: EVM/Oracle",
            eval_result["evm_log"],
            "",
        ]
        per_sample_log.write_text("\n".join(merged), encoding="utf-8")

        row |= {
            "quimera_ran": "1",
            "quimera_timeout": "1" if timeout_flag else "0",
            "quimera_exit_code": str(exit_code),
            "quimera_network_error": "1" if network_error else "0",
            "quimera_used_rpc": used_rpc,
            "quimera_used_block": used_block,
            "quimera_run_dir": str(run_dir),
            "quimera_log_file": str(log_file) if log_file.exists() else "",
            "quimera_session_dir": str(addr_dir) if addr_dir else "",
            "quimera_iteration_dir": str(iter_dir) if iter_dir else "",
            "quimera_iteration": str(iter_id),
            "quimera_test_file": str(test_file) if test_file and test_file.exists() else "",
            "quimera_response_file": str(response_file) if response_file and response_file.exists() else "",
            "quimera_compile_pass": "1" if eval_result["compile_pass"] else "0",
            "quimera_evm_pass": "1" if eval_result["evm_pass"] else "0",
            "quimera_oracle_pass": "1" if eval_result["oracle_pass"] else "0",
            "quimera_compile_exit_code": str(eval_result["compile_exit_code"]),
            "quimera_evm_exit_code": str(eval_result["evm_exit_code"]),
            "elapsed_seconds": f"{elapsed:.1f}",
            "log_path": str(per_sample_log),
        }
        rows.append(row)

    fieldnames = [
        "dataset",
        "project",
        "finding_id",
        "target_address",
        "chain_hint",
        "vulnerability_type",
        "violation_category",
        "logicgap_status",
        "logicgap_success",
        "result_json",
        "data_json",
        "attempts",
        "quimera_ran",
        "quimera_timeout",
        "quimera_exit_code",
        "quimera_network_error",
        "quimera_used_rpc",
        "quimera_used_block",
        "quimera_run_dir",
        "quimera_log_file",
        "quimera_session_dir",
        "quimera_iteration_dir",
        "quimera_iteration",
        "quimera_test_file",
        "quimera_response_file",
        "quimera_compile_pass",
        "quimera_evm_pass",
        "quimera_oracle_pass",
        "quimera_compile_exit_code",
        "quimera_evm_exit_code",
        "elapsed_seconds",
        "log_path",
    ]
    detailed_csv = out_dir / "quimera_vs_logicgap_complex.csv"
    with detailed_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    detailed_md = out_dir / "quimera_vs_logicgap_complex.md"
    write_summary_markdown(rows, detailed_md)

    legacy_csv = root / f"{args.legacy_prefix}_metrics.csv"
    legacy_md = root / f"{args.legacy_prefix}_metrics.md"
    write_legacy_metrics_table(rows, legacy_csv, legacy_md)

    elapsed_total = time.time() - started
    print(f"\nDone. {len(rows)} samples in {elapsed_total:.1f}s")
    print(f"Detailed CSV: {detailed_csv}")
    print(f"Detailed MD : {detailed_md}")
    print(f"Legacy CSV  : {legacy_csv}")
    print(f"Legacy MD   : {legacy_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
