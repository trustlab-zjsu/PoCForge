#!/usr/bin/env python3
"""Replay finding-aligned successful Gemini baseline PoCs against patched runtime bytecode.

The original PoCs hard-code deployed addresses and use fork state.  For each
address/finding pair listed in patched metadata, this runner compiles both the
patched source and archived original source, runs an original-runtime control,
then etches the patched runtime at the target before the patched PoC executes.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import tempfile
import os
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "dataset" / "D_patched" / "manifest.json"
OUTPUT = Path(os.getenv("REPLAY_OUTPUT", str(ROOT / "experimental_artifact" / "results" / "patched_poc_replay")))
FORGE_STD = ROOT / "foundry_sandbox" / "lib" / "forge-std"
FORK_URLS = {
    "bsc": "https://bsc-mainnet.public.blastapi.io",
    "eth": "https://eth-mainnet.public.blastapi.io",
}
FORK_BLOCKS = {"bsc": 126387568, "eth": 26145568}
# These baseline PoCs can finish successfully without observing any patched
# target effect: they only perform a reachability/read-only check, directly
# mutate storage with a test cheatcode, call an unrelated fallback, or deploy
# and exercise a fresh contract inside the test.  A passing Forge test is not
# evidence that the patched target remains vulnerable in these cases.
NO_IMPACT_OVERRIDES: dict[tuple[str, str, int], str] = {
    ("D_log", "1-bossbaby", 0): "read-only launch-state check",
    ("D_log", "1-bossbaby", 1): "read-only external-pair balance check",
    ("D_log", "3-karma", 1): "target-code reachability smoke check only",
    ("D_log", "Hacken-Mozart_Finance", 0): "target-code reachability smoke check only",
    ("D_log", "PeckShield-Arche", 4): "unrelated selector accepted by target fallback; no effect oracle",
    ("D_log", "QAP Token Full Smart Contract Security Audit", 0): "read-only assertion contradicts the reported finding",
    ("D_log", "SlowMist Audit Report - InsurAce_en-us", 1): "test uses vm.store directly and never calls the patched target",
    ("D_log", "SmartContract_Audit_Solidproof_Jizzjet", 0): "target-code reachability smoke check only",
    ("D_log", "SmartContract_Audit_Solidproof_Jizzjet", 5): "target-code reachability smoke check only",
    ("D_log", "SmartContract_Audit_Solidproof_Jizzjet", 6): "target-code reachability smoke check only",
    ("D_log", "SmartContract_Audit_Solidproof_Jizzjet", 7): "target-code reachability smoke check only",
    ("D_log", "SmartContract_Audit_Solidproof_Jizzjet", 8): "target-code reachability smoke check only",
    ("D_log", "SmartContract_Audit_Solidproof_Jizzjet", 9): "test deploys and exercises a fresh local contract instead of the patched target",
    ("D_log", "SmartContract_Audit_Solidproof_Jizzjet", 10): "target-code reachability smoke check only",
    ("D_log", "SmartContract_Audit_Solidproof_Jizzjet", 11): "target-code reachability smoke check only",
    ("D_log", "SmartContract_Audit_Solidproof_Jizzjet", 12): "target-code reachability smoke check only",
    ("D_mix", "1-world", 2): "unrelated selector accepted by target fallback; no effect oracle",
    ("D_mix", "Nugen_Token_Smart_Contract_Audit_Report_-_QuillAudits", 1): "explicit false-positive/safe-behavior check",
}
SOURCE_RE = re.compile(
    r"# Code to review\s*```(?:solidity)?\s*\n(.*?)\n```", re.DOTALL
)
CONTRACT_RE = re.compile(r"\bcontract\s+ExploitTest\b")
SETUP_RE = re.compile(r"(function\s+setUp\s*\([^)]*\)[^{]*\{)", re.DOTALL)


def run(cmd: list[str], cwd: Path, timeout: int = 180) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return p.returncode, p.stdout
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or b""
        if isinstance(partial, bytes):
            partial = partial.decode(errors="replace")
        return 124, partial + "\nTIMEOUT\n"


def normalize_source(text: str) -> str:
    text = re.sub(r":\s+=", ":=", text)
    # Some archived flattened prompts contain the malformed exact-version
    # pragma `0.7 .5`; normalize it for the available 0.8 compiler.
    text = re.sub(r"pragma solidity\s+0\.7\s+\.5\s*;", "pragma solidity ^0.8.0;", text)
    text = re.sub(r"pragma solidity\s+0\.8\s+\.5\s*;", "pragma solidity ^0.8.0;", text)
    # A recovered MiniDOGE flattening contains spaces around the version
    # separators (`^ 0.8 .4`); use the installed 0.8 toolchain for it.
    text = re.sub(r"pragma solidity\s*\^\s*0\.8\s*\.\s*4\s*;", "pragma solidity ^0.8.26;", text)
    # A few verified reports use a range whose upper bound is below the
    # newest local compiler.  Pin that legacy range to the installed 0.7.6
    # toolchain so Forge does not select 0.8.x and reject the source.
    text = re.sub(r"pragma solidity\s*>=\s*0\.6\.0\s*<\s*0\.8\.0\s*;", "pragma solidity ^0.7.6;", text)
    text = re.sub(r"\bnow\b", "block.timestamp", text)
    # Solidity 0.8 tightened address/integer conversions in the old
    # EnumerableSet helper embedded in the Sapphire source.
    text = text.replace("bytes32(uint256(value))", "bytes32(uint256(uint160(value)))")
    text = text.replace("address(uint256(_at(set._inner, index)))", "address(uint160(uint256(_at(set._inner, index))))")
    text = text.replace("bytes32(uint256(valueToInsert_))", "bytes32(uint256(uint160(valueToInsert_)))")
    # The flattened Gator source uses SafeMath methods in GatorToken but
    # omits the local using-directive (the deployed artifact was compiled with
    # it supplied by the original multi-file build).  Restore that directive
    # so the recovered source can be compiled for the control as well.
    text = re.sub(
        r"(contract\s+GatorToken\s+is\s+BEP20\s*\{)",
        r"\1\n    using SafeMath for uint256;",
        text,
        count=1,
    )
    return text.rstrip() + "\n"


def source_from_prompt(path: Path) -> str:
    # Sourcify-recovered entries keep an exact local Original.sol snapshot;
    # archived Quimera entries continue to use the prompt code block.
    if path.suffix == ".sol":
        return normalize_source(path.read_text(errors="replace"))
    match = SOURCE_RE.search(path.read_text(errors="replace"))
    if not match:
        raise ValueError(f"source block not found: {path}")
    return normalize_source(match.group(1))


def bytes_from_artifact(path: Path) -> tuple[bytes, dict]:
    data = json.loads(path.read_text())
    obj = data.get("deployedBytecode", {}).get("object") or ""
    if obj.startswith("0x"):
        obj = obj[2:]
    if not obj or "__$" in obj or len(obj) % 2:
        raise ValueError(f"unusable deployed bytecode in {path}")
    return bytes.fromhex(obj), data.get("deployedBytecode", {}).get("immutableReferences") or {}


def linked_runtime_from_artifact(path: Path, address: int) -> bytes:
    """Read a runtime artifact and resolve Solidity library placeholders."""
    data = json.loads(path.read_text())
    deployed = data.get("deployedBytecode", {})
    obj = deployed.get("object") or ""
    if obj.startswith("0x"):
        obj = obj[2:]
    if not obj or len(obj) % 2:
        raise ValueError(f"unusable deployed bytecode in {path}")
    address_hex = f"{address:040x}"
    for refs in (deployed.get("linkReferences") or {}).values():
        for entries in refs.values():
            for ref in entries:
                start = int(ref["start"]) * 2
                length = int(ref["length"]) * 2
                obj = obj[:start] + address_hex[:length] + obj[start + length:]
    if "__$" in obj:
        raise ValueError(f"unresolved library placeholder in {path}")
    return bytes.fromhex(obj)


def compile_runtime(
    source: str, source_name: str, main_contract: str, work: Path, force_old: bool
) -> tuple[bytes, dict, str]:
    root = work / source_name.replace(".sol", "")
    (root / "src").mkdir(parents=True)
    (root / "src" / source_name).write_text(source)
    cmd = ["forge", "build", "--root", str(root), "--contracts", "src", "--force"]
    if force_old:
        cmd += ["--use", "solc:0.4.26"]
    else:
        # Forge's ephemeral build root otherwise falls back to the newest
        # installed compiler even when a recovered source has a legacy pragma.
        # Select the matching local toolchain explicitly for 0.4--0.7 code.
        pragma = re.search(r"pragma\s+solidity[^0-9]*(\d+)\.(\d+)\.(\d+)", source)
        if pragma and int(pragma.group(1)) == 0 and int(pragma.group(2)) < 8:
            cmd += ["--use", f"solc:{pragma.group(1)}.{pragma.group(2)}.{pragma.group(3)}"]
    code, output = run(cmd, ROOT, timeout=180)
    artifact = root / "out" / source_name / f"{main_contract}.json"
    if not artifact.exists():
        raise RuntimeError(f"compile failed ({code}) for {source_name}:\n{output[-4000:]}")
    runtime, refs = bytes_from_artifact(artifact)
    return runtime, refs, output


def copy_immutables(
    patched: bytearray,
    patched_refs: dict,
    original: bytes,
    original_refs: dict,
) -> None:
    for key, refs in patched_refs.items():
        if key not in original_refs:
            continue
        for p_ref, o_ref in zip(refs, original_refs[key]):
            p_start, p_len = p_ref["start"], p_ref["length"]
            o_start, o_len = o_ref["start"], o_ref["length"]
            if p_len == o_len and p_start + p_len <= len(patched) and o_start + o_len <= len(original):
                patched[p_start : p_start + p_len] = original[o_start : o_start + o_len]


def dataset_info(metadata: dict) -> tuple[str, str]:
    if metadata.get("recovered_main_contract"):
        return metadata["recovered_main_contract"], metadata.get("chain", "")
    data = json.loads((ROOT / metadata["source_origin"]).read_text()) if False else None
    dataset_path = ROOT / metadata["findings"][0]["dataset_json"]
    target = json.loads(dataset_path.read_text())
    names = list(target["project_info"]["project_path"].keys())
    if not names:
        raise ValueError(f"no main contract name for {metadata['project']}")
    return names[0], target["project_info"].get("chain", "")


def patch_test(
    poc: str,
    suffix: str,
    runtime_name: str,
    contract_prefix: str,
    external_runtime_etches: list[tuple[str, str]] | None = None,
) -> str:
    poc = CONTRACT_RE.sub(f"contract {contract_prefix}_{suffix}", poc, count=1)
    match = SETUP_RE.search(poc)
    if not match:
        raise ValueError("PoC has no setUp function")
    injection = (
        f'\n        vm.etch(address(TARGET), '
        f'vm.readFileBinary("{runtime_name}"));'
    )
    poc = poc[: match.end()] + injection + poc[match.end() :]
    if external_runtime_etches:
        # Some findings exercise a separately deployed helper (DogeCake's
        # dividend tracker).  A patched main-token runtime alone cannot alter
        # that address, so etch the corresponding patched helper immediately
        # before the PoC body runs.  The original PoC source and assertions are
        # otherwise unchanged.
        exploit = re.search(r"(function\s+testExploit\s*\([^)]*\)[^{]*\{)", poc)
        if not exploit:
            raise ValueError("PoC has no testExploit function")
        extra = "".join(
            f'\n        vm.etch({address_expr}, vm.readFileBinary("{runtime_name}"));'
            for address_expr, runtime_name in external_runtime_etches
        )
        poc = poc[: exploit.end()] + extra + poc[exploit.end() :]
    return poc


def classify(output: str, exit_code: int) -> str:
    if "Compiler run failed" in output or "Error (" in output and "Compilation failed" in output:
        return "compile_error"
    if exit_code == 124 or "TIMEOUT" in output:
        return "timeout"
    if "[PASS]" in output and "Suite result: ok" in output:
        return "still_passed_validation"
    if "[FAIL:" not in output:
        return "harness_error"
    low = output.lower()
    if any(
        marker in low
        for marker in (
            "assert", "economic exploit failed", "logic exploit failed",
            "attacker balance should", "attacker should", "profit", "should increase",
        )
    ):
        return "no_reported_impact"
    return "stopped_at_patched_code"


def classify_patched_case(
    dataset: str, project: str, finding_id: int, output: str, exit_code: int
) -> tuple[str, str | None]:
    """Classify a patched replay and reject non-evidentiary passing oracles."""
    status = classify(output, exit_code)
    note = NO_IMPACT_OVERRIDES.get((dataset, project, finding_id))
    if status == "still_passed_validation" and note:
        return "no_reported_impact", note
    return status, None


def split_forge_tests(output: str, prefix: str) -> dict[int, str]:
    """Extract one forge test-suite section per generated finding test."""
    marker = re.compile(
        rf"(?m)^Ran \d+ test for test/{re.escape(prefix)}_(\d+)\.t\.sol:"
    )
    matches = list(marker.finditer(output))
    sections: dict[int, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(output)
        sections[int(match.group(1))] = output[match.start() : end]
    return sections


def csv_success_projects(dataset: str) -> dict[str, int]:
    name = "Gemini_D_mix(baseline).csv" if dataset == "D_mix" else "Gemini_D_log(baseline).csv"
    path = ROOT / "experimental_artifact" / "Statistical Results" / "Different_LLM" / name
    counts: Counter[str] = Counter()
    for row in csv.DictReader(path.open(newline="")):
        if row.get("Final Status", "").strip() == "🟢 SUCCESS":
            counts[row["Project"]] += 1
    return dict(counts)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    by_key = {(m["source_dataset"], m["project"]): m for m in manifest}
    all_rows = []

    for dataset in ("D_mix", "D_log"):
        only_dataset = os.getenv("REPLAY_DATASET")
        if only_dataset and dataset != only_dataset:
            continue
        success_counts = csv_success_projects(dataset)
        baseline_root = ROOT / "experimental_artifact" / "results" / "Different_LLM" / (
            "Gemini_D_mix(baseline)" if dataset == "D_mix" else "Gemini_D_log(baseline)"
        )
        for project, expected_count in sorted(success_counts.items()):
            only_project = os.getenv("REPLAY_PROJECT")
            if only_project and project != only_project:
                continue
            key = (dataset, project)
            metadata_path = ROOT / "dataset" / "D_patched" / dataset / project / "metadata.json"
            if key not in by_key or not metadata_path.exists():
                continue
            metadata = json.loads(metadata_path.read_text())
            if metadata["patch_status"] == "source_mismatch":
                continue
            patched_finding_ids = {
                int(f["finding_id"]) for f in metadata.get("findings", [])
            }
            result_dirs = sorted(
                p.parent
                for p in baseline_root.glob(f"{project}/finding_*/result.json")
                if json.loads(p.read_text()).get("status") == "SUCCESS"
                and int(p.parent.name.split("_")[1]) in patched_finding_ids
            )
            if not result_dirs:
                continue

            original_source = source_from_prompt(ROOT / metadata["source_origin"])
            patched_path = (
                ROOT / "dataset" / "D_patched" / dataset / project / "Patched.sol"
            )
            if not patched_path.exists():
                raise RuntimeError(f"patched source not found: {patched_path}")
            patched_source = normalize_source(patched_path.read_text(errors="replace"))
            main_contract, chain = dataset_info(metadata)
            with tempfile.TemporaryDirectory(prefix="patched-replay-build-") as build_tmp:
                build = Path(build_tmp)
                patched_runtime, patched_refs, patched_log = compile_runtime(
                    patched_source, "Patched.sol", main_contract, build, project == "02_Smart_Contract_Audit_TOUCH"
                )
                patched_external: dict[str, bytes] = {}
                patched_external_etches: list[tuple[str, str]] = []
                if dataset == "D_log" and project == "Gator":
                    # The finding calls the separately deployed Gator token
                    # returned by MasterChef.Gator().  Etching only MasterChef
                    # would leave the vulnerable token runtime unchanged.
                    token_artifact = build / "Patched" / "out" / "Patched.sol" / "GatorToken.json"
                    if not token_artifact.exists():
                        raise RuntimeError(f"patched Gator token artifact not found: {token_artifact}")
                    patched_external["patched_gator_runtime.bin"] = bytes_from_artifact(token_artifact)[0]
                    patched_external_etches = [
                        ("IMasterChef(TARGET).Gator()", "patched_gator_runtime.bin"),
                    ]
                elif dataset == "D_log" and project == "Doge Cake":
                    # The PoC calls the independently deployed dividend
                    # tracker returned by DogeCake.cakeDividendTracker().
                    # Compile its patched runtime as well; etching only the
                    # main DogeCake runtime would leave the vulnerable helper
                    # untouched and would not be a complete contract patch.
                    tracker_artifact = build / "Patched" / "out" / "Patched.sol" / "CakeDividendTracker.json"
                    if not tracker_artifact.exists():
                        raise RuntimeError(f"patched tracker artifact not found: {tracker_artifact}")
                    # CakeDividendTracker links IterableMapping.  Resolve the
                    # library to a private scratch address and etch that
                    # library too, so the helper runtime is executable.
                    library_address = 0x0000000000000000000000000000000000001001
                    tracker_runtime = linked_runtime_from_artifact(tracker_artifact, library_address)
                    patched_external["patched_tracker_runtime.bin"] = tracker_runtime
                    library_artifact = build / "Patched" / "out" / "Patched.sol" / "IterableMapping.json"
                    patched_external["patched_iterable_mapping_runtime.bin"] = bytes_from_artifact(library_artifact)[0]
                    patched_external_etches = [
                        ("address(IDogeCake(TARGET).cakeDividendTracker())", "patched_tracker_runtime.bin"),
                        (f"address(0x{library_address:040x})", "patched_iterable_mapping_runtime.bin"),
                    ]
                # Compile the archived source separately only to recover immutable values.
                original_runtime, original_refs, original_log = compile_runtime(
                    original_source, "Original.sol", main_contract, build, project == "02_Smart_Contract_Audit_TOUCH"
                )
                patched_bytes = bytearray(patched_runtime)
                copy_immutables(patched_bytes, patched_refs, original_runtime, original_refs)

                with tempfile.TemporaryDirectory(prefix="patched-replay-test-") as test_tmp:
                    test_root = Path(test_tmp)
                    (test_root / "test").mkdir()
                    (test_root / "src").mkdir()
                    (test_root / "lib").mkdir()
                    (test_root / "lib" / "forge-std").symlink_to(FORGE_STD)
                    (test_root / "patched_runtime.bin").write_bytes(patched_bytes)
                    for name, runtime in patched_external.items():
                        (test_root / name).write_bytes(runtime)
                    original_bytes = bytearray(original_runtime)
                    copy_immutables(original_bytes, original_refs, original_runtime, original_refs)
                    (test_root / "original_runtime.bin").write_bytes(original_bytes)
                    configs = (
                        '[profile.default]\n'
                        'src = "src"\n'
                        'test = "test"\n'
                        'out = "out"\n'
                        'libs = ["lib"]\n'
                        'remappings = ["forge-std/=lib/forge-std/src/"]\n'
                        'fs_permissions = [{ access = "read", path = "." }]\n'
                    )
                    (test_root / "foundry.toml").write_text(configs)
                    names = []
                    for result_dir in result_dirs:
                        finding_id = int(result_dir.name.split("_")[1])
                        suffix = f"{finding_id}"
                        poc = (result_dir / "Exploit.t.sol").read_text(errors="replace")
                        original_name = f"Original_{suffix}.t.sol"
                        patched_name = f"Patched_{suffix}.t.sol"
                        (test_root / "test" / original_name).write_text(
                            patch_test(poc, suffix, "original_runtime.bin", "ExploitOriginal")
                        )
                        (test_root / "test" / patched_name).write_text(
                            patch_test(
                                poc,
                                suffix,
                                "patched_runtime.bin",
                                "ExploitPatched",
                                patched_external_etches or None,
                            )
                        )
                        names.append((finding_id, original_name, patched_name))

                    chain_key = str(chain).lower()
                    rpc = FORK_URLS.get(chain_key, FORK_URLS["eth"])
                    if chain_key == "eth" and os.getenv("REPLAY_ETH_RPC"):
                        rpc = os.environ["REPLAY_ETH_RPC"]
                    if chain_key == "bsc" and os.getenv("REPLAY_BSC_RPC"):
                        rpc = os.environ["REPLAY_BSC_RPC"]
                    block_args = []
                    if os.getenv("REPLAY_USE_FIXED_BLOCK", "0") == "1":
                        block_args = ["--fork-block-number", str(FORK_BLOCKS.get(chain_key, FORK_BLOCKS["eth"]))]
                    # One fork per project/runtime group is materially faster
                    # than starting a fresh fork for every finding.
                    original_code, original_batch = run(
                        [
                            "forge", "test", "--root", str(test_root),
                            "--match-contract", "ExploitOriginal_",
                            "--fork-url", rpc,
                            *block_args,
                            "-vvv",
                        ],
                        ROOT,
                        timeout=int(os.getenv("REPLAY_BATCH_TIMEOUT", "300")),
                    )
                    patched_code, patched_batch = run(
                        [
                            "forge", "test", "--root", str(test_root),
                            "--match-contract", "ExploitPatched_",
                            "--fork-url", rpc,
                            *block_args,
                            "-vvv",
                        ],
                        ROOT,
                        timeout=int(os.getenv("REPLAY_BATCH_TIMEOUT", "300")),
                    )
                    original_sections = split_forge_tests(original_batch, "Original")
                    patched_sections = split_forge_tests(patched_batch, "Patched")
                    outputs = [
                        "===== original batch =====\n" + original_batch,
                        "===== patched batch =====\n" + patched_batch,
                    ]
                    per_test = []
                    for finding_id, _original_name, _patched_name in names:
                        original_output = original_sections.get(finding_id, original_batch)
                        patched_output = patched_sections.get(finding_id, patched_batch)
                        per_test.append(
                            (finding_id, original_code, original_output, patched_code, patched_output)
                        )
                    (OUTPUT / dataset).mkdir(exist_ok=True)
                    log_path = OUTPUT / dataset / f"{project}.log"
                    log_path.write_text("\n".join(outputs))
                    for finding_id, original_code, original_output, patched_code, patched_output in per_test:
                        original_status = classify(original_output, original_code)
                        status, classification_note = classify_patched_case(
                            dataset, project, finding_id, patched_output, patched_code
                        )
                        row = {
                                "dataset": dataset,
                                "project": project,
                                "finding_id": finding_id,
                                "status": status,
                                "original_status": original_status,
                                "original_exit_code": original_code,
                                "exit_code": patched_code,
                                "log": str(log_path.relative_to(ROOT)),
                                "chain": chain,
                            }
                        if classification_note:
                            row["classification_note"] = classification_note
                        all_rows.append(row)

    (OUTPUT / "results.json").write_text(json.dumps(all_rows, indent=2, ensure_ascii=False) + "\n")
    counts = Counter((r["dataset"], r["status"]) for r in all_rows)
    print(json.dumps({f"{d}:{s}": n for (d, s), n in sorted(counts.items())}, indent=2))
    print(f"Wrote {len(all_rows)} patched PoC replay records to {OUTPUT / 'results.json'}")


if __name__ == "__main__":
    main()
