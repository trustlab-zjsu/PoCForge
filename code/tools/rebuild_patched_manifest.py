#!/usr/bin/env python3
"""Re-index every source-backed entry under ``dataset/D_patched``."""

from __future__ import annotations

import json
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dataset" / "D_patched"


def main() -> None:
    manifest = []
    for metadata_path in sorted(DATA.glob("*/*/metadata.json")):
        metadata = json.loads(metadata_path.read_text())
        patched = metadata_path.with_name("Patched.sol")
        if not patched.exists():
            continue
        manifest.append({
            "source_dataset": metadata["source_dataset"],
            "project": metadata["project"],
            "target_address": metadata.get("target_address"),
            "contract": str(patched.relative_to(ROOT)),
            "metadata": str(metadata_path.relative_to(ROOT)),
            "patch_status": metadata.get("patch_status", "pending_patch"),
            "finding_ids": [int(f["finding_id"]) for f in metadata.get("findings", [])],
        })
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    baseline = {}
    for dataset in ("D_mix", "D_log"):
        path = ROOT / f"experimental_artifact/Statistical Results/Different_LLM/Gemini_{dataset}(baseline).csv"
        baseline[dataset] = sum(1 for row in csv.DictReader(path.open(newline="")) if row.get("Final Status", "").strip() == "🟢 SUCCESS")
    recovered = {dataset: sum(len(x["finding_ids"]) for x in manifest if x["source_dataset"] == dataset) for dataset in ("D_mix", "D_log")}
    mismatch = {dataset: 0 for dataset in ("D_mix", "D_log")}
    for item in manifest:
        metadata = json.loads((ROOT / item["metadata"]).read_text())
        if metadata.get("recovered_target_source") or "mismatch" in str(metadata.get("source_recovery", "")).lower():
            mismatch[item["source_dataset"]] += len(item["finding_ids"])
    skipped = {dataset: baseline[dataset] - recovered[dataset] for dataset in ("D_mix", "D_log")}
    (DATA / "coverage.json").write_text(json.dumps({
        "expanded": manifest,
        "skipped": [{"dataset": dataset, "reason": "source_unavailable", "finding_count": skipped[dataset]} for dataset in ("D_mix", "D_log") if skipped[dataset]],
        "source_coverage": {
            "source_backed_cases": {**recovered, "overall": sum(recovered.values())},
            "source_mismatch_cases": {**mismatch, "overall": sum(mismatch.values())},
            "no_archived_source_cases": {**skipped, "overall": sum(skipped.values())},
        },
    }, indent=2, ensure_ascii=False) + "\n")
    print(f"indexed {len(manifest)} projects and {sum(len(x['finding_ids']) for x in manifest)} findings")


if __name__ == "__main__":
    main()
