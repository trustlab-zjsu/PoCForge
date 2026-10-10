#!/usr/bin/env python3
"""Recover missing baseline-success sources from Sourcify v2.

The archived Quimera prompt is absent for a subset of Gemini-success cases,
but many of those deployed addresses have a verified source in Sourcify.  This
script copies that source into ``dataset/D_patched`` together with an explicit
``Original.sol`` snapshot, so subsequent patching/replay remains auditable.
No source is fabricated: an entry is written only when Sourcify returns a
verified source and the source contains the expected main contract.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "dataset" / "D_patched"
BASE = {
    "D_mix": ROOT / "experimental_artifact/results/Different_LLM/Gemini_D_mix(baseline)",
    "D_log": ROOT / "experimental_artifact/results/Different_LLM/Gemini_D_log(baseline)",
}
CSV = {
    ds: ROOT / f"experimental_artifact/Statistical Results/Different_LLM/Gemini_{ds}(baseline).csv"
    for ds in BASE
}


def projects(dataset: str) -> list[str]:
    seen: set[str] = set()
    rows = csv.DictReader(CSV[dataset].open(newline=""))
    result = []
    for row in rows:
        project = row.get("Project", "")
        if project and project not in seen and row.get("Final Status", "").strip() == "🟢 SUCCESS":
            seen.add(project)
            result.append(project)
    return result


def dataset_json(dataset: str, project: str) -> Path | None:
    direct = ROOT / "dataset" / dataset
    exact = direct / f"{project}.json"
    if exact.exists():
        return exact
    exact_pdf = direct / f"{project}.pdf.json"
    if exact_pdf.exists():
        return exact_pdf
    # Some report names contain a trailing space or differ only by the .pdf
    # suffix; match by the project-info address-bearing JSON instead.
    normalized = project.removesuffix(".pdf").strip()
    for candidate in sorted(direct.glob("*.json")):
        if candidate.name in {"dataset_info.json"}:
            continue
        if candidate.stem.removesuffix(".pdf").strip() == normalized:
            return candidate
    return None


def successful_findings(dataset: str, project: str) -> list[tuple[int, dict]]:
    rows = []
    for result_json in sorted((BASE[dataset] / project).glob("finding_*/result.json")):
        result = json.loads(result_json.read_text())
        if result.get("status") == "SUCCESS":
            rows.append((int(result_json.parent.name.split("_", 1)[1]), result))
    return rows


def source_detail(data_path: Path | None, finding_id: int) -> dict:
    if data_path is None:
        return {}
    data = json.loads(data_path.read_text())
    return next((x for x in data.get("findings", []) if str(x.get("id")) == str(finding_id)), {})


def fetch(address: str, chain: str) -> dict | None:
    chain_id = "1" if str(chain).lower() == "eth" else "56"
    url = f"https://sourcify.dev/server/v2/contract/{chain_id}/{address}?fields=all"
    with tempfile.NamedTemporaryFile() as tmp:
        cmd = [
            "curl", "-Ls", "--retry", "3", "--retry-delay", "1",
            "--max-time", "45", "-o", tmp.name, url,
        ]
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        except subprocess.TimeoutExpired:
            return None
        if proc.returncode != 0:
            return None
        try:
            value = json.loads(Path(tmp.name).read_text())
        except (OSError, json.JSONDecodeError):
            return None
    if value.get("match") not in {"match", "exact_match"}:
        return None
    sources = value.get("sources") or {}
    if not sources:
        return None
    return value


def main() -> None:
    recovered = []
    unavailable = []
    for dataset in ("D_mix", "D_log"):
        for project in projects(dataset):
            project_dir = OUT / dataset / project
            patched_path = project_dir / "Patched.sol"
            if patched_path.exists():
                continue
            details = dataset_json(dataset, project)
            if details is None:
                unavailable.append({"dataset": dataset, "project": project, "reason": "dataset_json_missing"})
                continue
            project_info = json.loads(details.read_text()).get("project_info", {})
            address = project_info.get("address", "").strip()
            if not address:
                unavailable.append({"dataset": dataset, "project": project, "reason": "address_missing"})
                continue
            verified = fetch(address, project_info.get("chain", "bsc"))
            if verified is None:
                unavailable.append({"dataset": dataset, "project": project, "address": address, "reason": "sourcify_unavailable"})
                continue
            main_contract = next(iter((project_info.get("project_path") or {}).keys()), "")
            sources = verified.get("sources") or {}
            # Sourcify normally returns a single flattened source for these
            # reports.  Prefer a source whose basename is the project contract,
            # then fall back to the first source while retaining an explicit
            # warning in metadata if names differ.
            source_name = next(
                (name for name in sources if Path(name).stem == main_contract),
                next(iter(sources)),
            )
            source = (sources[source_name] or {}).get("content", "")
            if not source or not re.search(rf"\b(contract|library|abstract\s+contract)\s+{re.escape(main_contract)}\b", source):
                unavailable.append({"dataset": dataset, "project": project, "address": address, "reason": "main_contract_not_in_source", "source_name": source_name})
                continue
            project_dir.mkdir(parents=True, exist_ok=True)
            # Keep both names: Patched.sol is the user-facing artifact and
            # Original.sol is the exact recovered baseline used for controls.
            patched_path.write_text(source.rstrip() + "\n")
            original_path = project_dir / "Original.sol"
            original_path.write_text(source.rstrip() + "\n")
            old_metadata = json.loads((project_dir / "metadata.json").read_text()) if (project_dir / "metadata.json").exists() else {}
            findings = []
            for finding_id, result in successful_findings(dataset, project):
                violation = result.get("violation_target") or {}
                detail = source_detail(details, finding_id)
                old = next((x for x in old_metadata.get("findings", []) if int(x.get("finding_id", -1)) == finding_id), {})
                findings.append({
                    "project": project,
                    "finding_id": finding_id,
                    "vulnerability_type": violation.get("vulnerability_type") or old.get("vulnerability_type"),
                    "title": detail.get("title") or old.get("title"),
                    "description": detail.get("description") or old.get("description"),
                    "location": detail.get("location") or old.get("location"),
                    "pocforge_status": old.get("pocforge_status", "BASELINE_SUCCESS"),
                    "quimera_oracle_pass": old.get("quimera_oracle_pass", False),
                    "dataset_json": str(details.relative_to(ROOT)),
                    "patch_status": "pending_patch",
                })
            metadata = {
                "source_dataset": dataset,
                "project": project,
                "target_address": address,
                "chain": project_info.get("chain", "bsc"),
                "source_origin": str(original_path.relative_to(ROOT)),
                "source_recovery": "Sourcify v2 verified source",
                "sourcify_match": verified.get("match"),
                "sourcify_verified_at": verified.get("verifiedAt"),
                "sourcify_source_name": source_name,
                "selection": "Gemini baseline Final Status == SUCCESS",
                "patch_status": "pending_patch",
                "findings": findings,
            }
            (project_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
            recovered.append({"dataset": dataset, "project": project, "address": address, "findings": [x[0] for x in successful_findings(dataset, project)], "source": str(patched_path.relative_to(ROOT))})
            print(f"recovered {dataset}/{project} ({len(findings)} findings)", flush=True)
    report = {"recovered": recovered, "unavailable": unavailable}
    (OUT / "sourcify_recovery.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"recovered_projects": len(recovered), "recovered_findings": sum(len(x["findings"]) for x in recovered), "unavailable_projects": len(unavailable)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
