#!/usr/bin/env python3
"""Recover exact target sources for archived source/target mismatches.

Some Quimera prompts embedded a different contract than the PoC address.  We
can still replay those PoCs when the *address actually used by the PoC* has a
verified Sourcify source.  The metadata retains the mismatch provenance and
the target source is kept separately from the original report source.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROOT_DATA = ROOT / "dataset" / "D_patched"


def fetch(chain_id: str, address: str) -> dict | None:
    url = f"https://sourcify.dev/server/v2/contract/{chain_id}/{address}?fields=all"
    with tempfile.NamedTemporaryFile() as tmp:
        try:
            p = subprocess.run(["curl", "-Ls", "--retry", "3", "--retry-delay", "1", "--max-time", "45", "-o", tmp.name, url], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        except subprocess.TimeoutExpired:
            return None
        if p.returncode:
            return None
        try:
            value = json.loads(Path(tmp.name).read_text())
        except (OSError, json.JSONDecodeError):
            return None
    if value.get("match") not in {"match", "exact_match"} or not value.get("sources"):
        return None
    return value


def main() -> None:
    report = []
    for metadata_path in sorted(ROOT_DATA.glob("*/*/metadata.json")):
        metadata = json.loads(metadata_path.read_text())
        if metadata.get("patch_status") != "source_mismatch":
            continue
        address = str(metadata.get("target_address", "")).strip()
        if not address:
            continue
        chain_id = "1" if str(metadata.get("chain", "")).lower() == "eth" else "56"
        verified = fetch(chain_id, address)
        if verified is None:
            report.append({"dataset": metadata["source_dataset"], "project": metadata["project"], "status": "unavailable"})
            continue
        sources = verified["sources"]
        source_name = next(iter(sources))
        source = (sources[source_name] or {}).get("content", "")
        compilation = verified.get("compilation") or {}
        main_contract = compilation.get("name") or ""
        if not main_contract:
            names = re.findall(r"\bcontract\s+([A-Za-z_]\w*)", source)
            main_contract = names[0] if names else ""
        if not source or not main_contract:
            report.append({"dataset": metadata["source_dataset"], "project": metadata["project"], "status": "invalid_source"})
            continue
        project_dir = metadata_path.parent
        (project_dir / "Original.sol").write_text(source.rstrip() + "\n")
        (project_dir / "Patched.sol").write_text(source.rstrip() + "\n")
        metadata["source_origin"] = str((project_dir / "Original.sol").relative_to(ROOT))
        metadata["source_recovery"] = "Sourcify v2 verified target source (original report mismatch retained)"
        metadata["recovered_target_source"] = True
        metadata["recovered_main_contract"] = main_contract
        metadata["recovered_chain_id"] = chain_id
        metadata["sourcify_match"] = verified.get("match")
        metadata["sourcify_verified_at"] = verified.get("verifiedAt")
        metadata["sourcify_source_name"] = source_name
        metadata["patch_status"] = "pending_patch"
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
        report.append({"dataset": metadata["source_dataset"], "project": metadata["project"], "status": "recovered", "main_contract": main_contract, "chain_id": chain_id})
        print(f"recovered mismatch target {metadata['source_dataset']}/{metadata['project']} ({main_contract})", flush=True)
    (ROOT_DATA / "mismatch_target_recovery.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"recovered": sum(x["status"] == "recovered" for x in report), "unavailable": sum(x["status"] != "recovered" for x in report)}))


if __name__ == "__main__":
    main()
