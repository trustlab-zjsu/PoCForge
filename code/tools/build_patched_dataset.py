#!/usr/bin/env python3
"""Build the source skeleton for the patched-contract dataset.

The comparison CSVs are the canonical index of PoCForge-validated findings in
this artifact.  Quimera's saved prompts contain the verified, flattened source
that was shown to the comparison system.  This script extracts one source per
target address and groups every successful finding for that source in a small
metadata file.  It intentionally never overwrites an existing contract so
that hand-reviewed patches are preserved on subsequent runs.
"""

from __future__ import annotations

import csv
import json
import re
from collections import OrderedDict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "dataset" / "D_patched"

INPUTS = (
    (
        "D_mix",
        ROOT
        / "experimental_artifact"
        / "results"
        / "Comparison"
        / "quimera_D_mix"
        / "quimera_vs_pocforge_general.csv",
        ROOT / "dataset" / "D_mix",
    ),
    (
        "D_log",
        ROOT
        / "experimental_artifact"
        / "results"
        / "Comparison"
        / "quimera_D_log"
        / "quimera_vs_pocforge_complex.csv",
        ROOT / "dataset" / "D_log",
    ),
)

SOURCE_RE = re.compile(
    r"# Code to review\s*```(?:solidity)?\s*\n(.*?)\n```", re.DOTALL
)


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


def finding_record(dataset_path: Path | None, finding_id: str) -> dict:
    if dataset_path is None:
        return {}
    data = json.loads(dataset_path.read_text())
    return next(
        (
            finding
            for finding in data.get("findings", [])
            if str(finding.get("id")) == finding_id
        ),
        {},
    )


def source_from_run(csv_path: Path, project: str, finding_id: str) -> tuple[str, Path]:
    run_dir = csv_path.parent / "runs" / project / f"finding_{finding_id}"
    prompts = sorted(run_dir.glob("quimera_foundry_sessions/*/*/prompt.txt"))
    for prompt in reversed(prompts):
        match = SOURCE_RE.search(prompt.read_text(errors="replace"))
        if match:
            # Some saved prompts contain a formatter artifact in Yul assignments
            # (`name: = value`).  Restore the Solidity/Yul token before emitting
            # the standalone source.
            source = re.sub(r":\s+=", ":=", match.group(1))
            return source.rstrip() + "\n", prompt
    raise FileNotFoundError(f"no saved source block for {project} finding {finding_id}")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []

    for dataset_name, csv_path, dataset_dir in INPUTS:
        successful = [
            row
            for row in csv.DictReader(csv_path.open(newline=""))
            if row["pocforge_success"] == "1"
        ]

        grouped: OrderedDict[str, list[dict]] = OrderedDict()
        for row in successful:
            grouped.setdefault(row["target_address"].lower(), []).append(row)

        for address, rows in grouped.items():
            canonical = rows[0]
            project = canonical["project"]
            project_dir = OUTPUT / dataset_name / project
            project_dir.mkdir(parents=True, exist_ok=True)

            source, prompt = source_from_run(
                csv_path, project, canonical["finding_id"]
            )
            contract_path = project_dir / "Patched.sol"
            if not contract_path.exists():
                contract_path.write_text(source)

            findings = []
            for row in rows:
                data_path = dataset_json(dataset_dir, row["project"])
                finding = finding_record(data_path, row["finding_id"])
                findings.append(
                    {
                        "project": row["project"],
                        "finding_id": int(row["finding_id"]),
                        "vulnerability_type": row["vulnerability_type"],
                        "title": finding.get("title"),
                        "description": finding.get("description"),
                        "location": finding.get("location"),
                        "pocforge_status": row["pocforge_status"],
                        "quimera_oracle_pass": row["quimera_oracle_pass"] == "1",
                        "dataset_json": (
                            str(data_path.relative_to(ROOT)) if data_path else None
                        ),
                    }
                )

            metadata_path = project_dir / "metadata.json"
            previous_metadata = (
                json.loads(metadata_path.read_text())
                if metadata_path.exists()
                else {}
            )
            metadata = {
                "source_dataset": dataset_name,
                "project": project,
                "target_address": canonical["target_address"],
                "chain": canonical["chain_hint"],
                "source_origin": str(prompt.relative_to(ROOT)),
                "selection": "pocforge_status == SUCCESS",
                "patch_status": "pending_review",
                "findings": findings,
            }
            # Preserve review/validation fields produced after manual patching.
            for key in (
                "patch_status",
                "patch_summary",
                "validation",
                "original_source_sha256",
                "patched_source_sha256",
            ):
                if key in previous_metadata:
                    metadata[key] = previous_metadata[key]
            previous_findings = {
                item["finding_id"]: item
                for item in previous_metadata.get("findings", [])
            }
            for finding in metadata["findings"]:
                old_finding = previous_findings.get(finding["finding_id"], {})
                if "patch_status" in old_finding:
                    finding["patch_status"] = old_finding["patch_status"]

            metadata_path.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False) + "\n"
            )
            manifest.append(
                {
                    "source_dataset": dataset_name,
                    "project": project,
                    "target_address": canonical["target_address"],
                    "contract": str(contract_path.relative_to(ROOT)),
                    "metadata": str(metadata_path.relative_to(ROOT)),
                    "patch_status": metadata["patch_status"],
                    "finding_ids": [item["finding_id"] for item in findings],
                }
            )

    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    print(
        f"Prepared {len(manifest)} address-deduplicated contracts under "
        f"{OUTPUT.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
