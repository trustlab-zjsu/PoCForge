#!/usr/bin/env python3
"""Expand ``D_patched`` to every baseline-success case with archived source.

The first version of the patched dataset was indexed by PoCForge successes.
This pass uses the Gemini baseline result directories as the population being
replayed.  A Quimera prompt is required to provide the flattened source; cases
without one remain explicitly out of scope instead of receiving a fabricated
patch.  Existing reviewed ``Patched.sol`` files are never overwritten.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "dataset" / "D_patched"
BASELINES = {
    "D_mix": (
        ROOT / "experimental_artifact/Statistical Results/Different_LLM/Gemini_D_mix(baseline).csv",
        ROOT / "experimental_artifact/results/Different_LLM/Gemini_D_mix(baseline)",
        ROOT / "experimental_artifact/results/Comparison/quimera_D_mix/runs",
        ROOT / "dataset/D_mix",
    ),
    "D_log": (
        ROOT / "experimental_artifact/Statistical Results/Different_LLM/Gemini_D_log(baseline).csv",
        ROOT / "experimental_artifact/results/Different_LLM/Gemini_D_log(baseline)",
        ROOT / "experimental_artifact/results/Comparison/quimera_D_log/runs",
        ROOT / "dataset/D_log",
    ),
}
SOURCE_RE = re.compile(r"# Code to review\s*```(?:solidity)?\s*\n(.*?)\n```", re.DOTALL)

# These are known source/target mismatches.  They are retained as metadata by
# the original builder, but must not be reclassified as patched contracts.
SOURCE_MISMATCH = {
    ("D_mix", "Hacken-FOTA"),
    ("D_log", "2022-10-shimacapital-ondo-securityreview"),
    ("D_log", "PeckShield-Arche"),
    ("D_log", "SlowMist Audit Report - InsurAce_en-us"),
    ("D_log", "SlowMist Audit Report - Shield_en-us"),
}


def source_from_prompt(path: Path) -> str:
    match = SOURCE_RE.search(path.read_text(errors="replace"))
    if not match:
        raise ValueError(f"source block not found: {path}")
    return re.sub(r":\s+=", ":=", match.group(1)).rstrip() + "\n"


def dataset_json(dataset_dir: Path, project: str) -> Path | None:
    exact = dataset_dir / f"{project}.json"
    if exact.exists():
        return exact
    pdf = dataset_dir / f"{project}.pdf.json"
    if pdf.exists():
        return pdf
    normalized = project.removesuffix(".pdf")
    for candidate in sorted(dataset_dir.glob("*.json")):
        if candidate.stem.removesuffix(".pdf") == normalized:
            return candidate
    return None


def finding_details(path: Path | None, finding_id: int) -> dict:
    if path is None:
        return {}
    data = json.loads(path.read_text())
    return next(
        (f for f in data.get("findings", []) if str(f.get("id")) == str(finding_id)),
        {},
    )


def baseline_findings(result_root: Path, project: str) -> list[tuple[int, dict]]:
    rows = []
    for result_dir in sorted((result_root / project).glob("finding_*")):
        result_json = result_dir / "result.json"
        if not result_json.exists():
            continue
        result = json.loads(result_json.read_text())
        if result.get("status") != "SUCCESS":
            continue
        rows.append((int(result_dir.name.split("_", 1)[1]), result))
    return rows


def prompt_for_project(prompt_root: Path, project: str, finding_id: int) -> Path | None:
    project_root = prompt_root / project
    candidates = []
    preferred = project_root / f"finding_{finding_id}"
    if preferred.exists():
        candidates.extend(sorted(preferred.glob("quimera_foundry_sessions/*/*/prompt.txt")))
    for finding_root in sorted(project_root.glob("finding_*")):
        candidates.extend(sorted(finding_root.glob("quimera_foundry_sessions/*/*/prompt.txt")))
    for candidate in candidates:
        try:
            source_from_prompt(candidate)
        except ValueError:
            continue
        return candidate
    return None


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    expanded = []
    skipped = []

    for dataset, (csv_path, baseline_root, prompt_root, dataset_dir) in BASELINES.items():
        projects = sorted(
            {
                row["Project"]
                for row in csv.DictReader(csv_path.open(newline=""))
                if row.get("Final Status", "").strip() == "🟢 SUCCESS"
            }
        )
        for project in projects:
            baseline = baseline_findings(baseline_root, project)
            if not baseline:
                continue
            prompt = prompt_for_project(prompt_root, project, baseline[0][0])
            key = (dataset, project)
            metadata_path = OUTPUT / dataset / project / "metadata.json"
            contract_path = metadata_path.with_name("Patched.sol")
            if prompt is None:
                skipped.append({"dataset": dataset, "project": project, "reason": "no_archived_source"})
                continue

            project_dir = metadata_path.parent
            project_dir.mkdir(parents=True, exist_ok=True)
            previous = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
            if not contract_path.exists():
                contract_path.write_text(source_from_prompt(prompt))

            first_result = baseline[0][1]
            target_address = first_result.get("target_address") or first_result.get("violation_target", {}).get("target_address")
            chain = previous.get("chain", "")
            if not chain:
                for row in csv.DictReader(csv_path.open(newline="")):
                    if row.get("Project") == project and row.get("Final Status", "").strip() == "🟢 SUCCESS":
                        target_address = target_address or row.get("target_address")
                        chain = row.get("chain_hint", "")
                        break

            findings = []
            old_by_id = {int(f["finding_id"]): f for f in previous.get("findings", [])}
            data_path = dataset_json(dataset_dir, project)
            for finding_id, result in baseline:
                violation = result.get("violation_target") or {}
                detail = finding_details(data_path, finding_id)
                old = old_by_id.get(finding_id, {})
                finding = {
                    "project": project,
                    "finding_id": finding_id,
                    "vulnerability_type": violation.get("vulnerability_type") or old.get("vulnerability_type"),
                    "title": detail.get("title") or old.get("title"),
                    "description": detail.get("description") or old.get("description"),
                    "location": detail.get("location") or old.get("location"),
                    "pocforge_status": old.get("pocforge_status", "BASELINE_SUCCESS"),
                    "quimera_oracle_pass": old.get("quimera_oracle_pass", False),
                    "dataset_json": str(data_path.relative_to(ROOT)) if data_path else old.get("dataset_json"),
                }
                # Preserve a reviewed status; newly discovered baseline cases
                # are deliberately marked pending until patched and compiled.
                finding["patch_status"] = old.get("patch_status", "pending_patch")
                findings.append(finding)

            status = previous.get("patch_status")
            if not status or status == "pending_review":
                status = "source_mismatch" if key in SOURCE_MISMATCH else "pending_patch"
            metadata = {
                "source_dataset": dataset,
                "project": project,
                "target_address": target_address,
                "chain": chain,
                "source_origin": previous.get("source_origin", str(prompt.relative_to(ROOT))),
                "selection": "Gemini baseline Final Status == SUCCESS",
                "patch_status": status,
                "findings": findings,
            }
            for field in ("patch_summary", "validation", "original_source_sha256", "patched_source_sha256"):
                if field in previous:
                    metadata[field] = previous[field]
            metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
            expanded.append({
                "source_dataset": dataset,
                "project": project,
                "target_address": target_address,
                "contract": str(contract_path.relative_to(ROOT)),
                "metadata": str(metadata_path.relative_to(ROOT)),
                "patch_status": status,
                "finding_ids": [f["finding_id"] for f in findings],
            })

    (OUTPUT / "manifest.json").write_text(json.dumps(expanded, indent=2, ensure_ascii=False) + "\n")
    report = {"expanded": expanded, "skipped": skipped}
    (OUTPUT / "coverage.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"Expanded {len(expanded)} source-backed projects; skipped {len(skipped)} projects without archived source")
    print(f"Baseline cases represented: {sum(len(x['finding_ids']) for x in expanded)}")


if __name__ == "__main__":
    main()
