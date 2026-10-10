#!/usr/bin/env python3
"""Reconstruct the complete replay table from per-project forge logs.

This is useful after a focused rerun: the runner writes one log per project,
while this script combines unchanged historical logs with the newly rerun
projects without inventing statuses.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from replay_patched_pocs import NO_IMPACT_OVERRIDES, classify, split_forge_tests


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "experimental_artifact/results/patched_poc_replay"


def baseline_ids(dataset: str, project: str) -> list[int]:
    root_name = "Gemini_D_mix(baseline)" if dataset == "D_mix" else "Gemini_D_log(baseline)"
    root = ROOT / "experimental_artifact/results/Different_LLM" / root_name / project
    ids = []
    for path in sorted(root.glob("finding_*/result.json")):
        try:
            if json.loads(path.read_text()).get("status") == "SUCCESS":
                ids.append(int(path.parent.name.split("_", 1)[1]))
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return ids


def project_chain(dataset: str, project: str) -> str:
    path = ROOT / "dataset/D_patched" / dataset / project / "metadata.json"
    return json.loads(path.read_text()).get("chain", "")


def parse_log(path: Path, finding_ids: list[int]) -> dict[int, tuple[str, int, str, int]]:
    text = path.read_text(errors="replace")
    parsed: dict[int, tuple[str, int, str, int]] = {}
    if "===== original batch =====" in text:
        original_batch, patched_batch = text.split("===== patched batch =====", 1)
        original_batch = original_batch.split("===== original batch =====", 1)[1]
        original_sections = split_forge_tests(original_batch, "Original")
        patched_sections = split_forge_tests(patched_batch, "Patched")
        for finding_id in finding_ids:
            original = original_sections.get(finding_id, original_batch)
            patched = patched_sections.get(finding_id, patched_batch)
            parsed[finding_id] = (
                classify(original, 0 if "Suite result: ok" in original else 1),
                0 if "Suite result: ok" in original else 1,
                classify(patched, 0 if "Suite result: ok" in patched else 1),
                0 if "Suite result: ok" in patched else 1,
            )
        return parsed

    pattern = re.compile(
        r"===== finding (\d+) original =====\n(.*?)\n===== finding \1 patched =====\n(.*?)(?=\n===== finding |\Z)",
        re.DOTALL,
    )
    for match in pattern.finditer(text):
        finding_id = int(match.group(1))
        original, patched = match.group(2), match.group(3)
        original_code = 0 if "Suite result: ok" in original else 1
        patched_code = 0 if "Suite result: ok" in patched else 1
        parsed[finding_id] = (
            classify(original, original_code),
            original_code,
            classify(patched, patched_code),
            patched_code,
        )
    return parsed


def main() -> None:
    rows = []
    missing = []
    for dataset in ("D_mix", "D_log"):
        csv_name = "Gemini_D_mix(baseline).csv" if dataset == "D_mix" else "Gemini_D_log(baseline).csv"
        csv_path = ROOT / "experimental_artifact/Statistical Results/Different_LLM" / csv_name
        projects = sorted({
            row["Project"] for row in csv.DictReader(csv_path.open(newline=""))
            if row.get("Final Status", "").strip() == "🟢 SUCCESS"
        })
        for project in projects:
            metadata_path = ROOT / "dataset/D_patched" / dataset / project / "metadata.json"
            if not metadata_path.exists():
                continue
            metadata = json.loads(metadata_path.read_text())
            if metadata.get("patch_status") == "source_mismatch":
                continue
            ids = baseline_ids(dataset, project)
            log_path = OUTPUT / dataset / f"{project}.log"
            if not log_path.exists():
                missing.append((dataset, project, ids))
                continue
            parsed = parse_log(log_path, ids)
            for finding_id in ids:
                if finding_id not in parsed:
                    missing.append((dataset, project, [finding_id]))
                    continue
                original_status, original_code, status, code = parsed[finding_id]
                classification_note = None
                if status == "still_passed_validation":
                    classification_note = NO_IMPACT_OVERRIDES.get((dataset, project, finding_id))
                    if classification_note:
                        status = "no_reported_impact"
                row = {
                    "dataset": dataset,
                    "project": project,
                    "finding_id": finding_id,
                    "status": status,
                    "original_status": original_status,
                    "original_exit_code": original_code,
                    "exit_code": code,
                    "log": str(log_path.relative_to(ROOT)),
                    "chain": project_chain(dataset, project),
                }
                if classification_note:
                    row["classification_note"] = classification_note
                rows.append(row)
    rows.sort(key=lambda row: (row["dataset"], row["project"], row["finding_id"]))
    (OUTPUT / "results.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    (OUTPUT / "rebuild_missing.json").write_text(json.dumps(missing, indent=2, ensure_ascii=False) + "\n")
    print(f"rebuilt {len(rows)} rows; missing {len(missing)} case groups")
    if missing:
        print(json.dumps(missing, ensure_ascii=False))


if __name__ == "__main__":
    main()
