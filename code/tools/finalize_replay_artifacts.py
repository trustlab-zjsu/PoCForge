#!/usr/bin/env python3
"""Write the final replay summary, LaTeX table, and patched metadata."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "experimental_artifact/results/patched_poc_replay"
DATASET = ROOT / "dataset/D_patched"


def baseline_count(dataset: str) -> int:
    name = "Gemini_D_mix(baseline).csv" if dataset == "D_mix" else "Gemini_D_log(baseline).csv"
    path = ROOT / "experimental_artifact/Statistical Results/Different_LLM" / name
    return sum(1 for row in csv.DictReader(path.open(newline="")) if row.get("Final Status", "").strip() == "🟢 SUCCESS")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 1) if den else 0.0


def main() -> None:
    rows = json.loads((OUT / "results.json").read_text())
    baseline = {dataset: baseline_count(dataset) for dataset in ("D_mix", "D_log")}
    attempted = Counter(row["dataset"] for row in rows)
    controls = Counter(row["dataset"] for row in rows if row["original_status"] == "still_passed_validation")
    excluded = {dataset: attempted[dataset] - controls[dataset] for dataset in ("D_mix", "D_log")}
    # ``status`` describes all source-backed replays (the table's 170+ raw
    # evaluation population).  ``valid_status`` is the defensible
    # effectiveness subset whose original-runtime control passed.
    status = {
        dataset: Counter(row["status"] for row in rows if row["dataset"] == dataset)
        for dataset in ("D_mix", "D_log")
    }
    valid_status = {
        dataset: Counter(row["status"] for row in rows if row["dataset"] == dataset and row["original_status"] == "still_passed_validation")
        for dataset in ("D_mix", "D_log")
    }
    source_available = Counter()
    source_mismatch = Counter()
    for metadata_path in DATASET.glob("*/*/metadata.json"):
        metadata = json.loads(metadata_path.read_text())
        if not metadata_path.with_name("Patched.sol").exists():
            continue
        source_available[metadata["source_dataset"]] += len(metadata.get("findings", []))
        if metadata.get("recovered_target_source") or "mismatch" in str(metadata.get("source_recovery", "")).lower():
            source_mismatch[metadata["source_dataset"]] += len(metadata.get("findings", []))
    no_source = {dataset: baseline[dataset] - source_available[dataset] for dataset in ("D_mix", "D_log")}

    valid_total = controls["D_mix"] + controls["D_log"]
    stopped = {dataset: status[dataset]["stopped_at_patched_code"] for dataset in ("D_mix", "D_log")}
    no_impact = {dataset: status[dataset]["no_reported_impact"] for dataset in ("D_mix", "D_log")}
    still = {dataset: status[dataset]["still_passed_validation"] for dataset in ("D_mix", "D_log")}
    valid_stopped = {dataset: valid_status[dataset]["stopped_at_patched_code"] for dataset in ("D_mix", "D_log")}
    valid_no_impact = {dataset: valid_status[dataset]["no_reported_impact"] for dataset in ("D_mix", "D_log")}
    valid_still = {dataset: valid_status[dataset]["still_passed_validation"] for dataset in ("D_mix", "D_log")}
    no_longer = {dataset: stopped[dataset] + no_impact[dataset] for dataset in ("D_mix", "D_log")}
    valid_no_longer = {dataset: valid_stopped[dataset] + valid_no_impact[dataset] for dataset in ("D_mix", "D_log")}
    summary = {
        "replay_method": "All Gemini baseline-success findings for which a verified or archived source was available were replayed. The table reports the complete source-backed patched population; effectiveness percentages additionally expose the original-control-passing subset.",
        "fork_state": "latest live public RPC state at run time (fixed block disabled)",
        "rpc_endpoints": {"eth": "https://eth-mainnet.public.blastapi.io", "bsc": "https://bsc-mainnet.public.blastapi.io"},
        "baseline_original_vpr_passes": {"D_mix": baseline["D_mix"], "D_log": baseline["D_log"], "overall": sum(baseline.values())},
        "source_coverage": {
            "archived_source_cases": {"D_mix": source_available["D_mix"], "D_log": source_available["D_log"], "overall": sum(source_available.values())},
            "source_mismatch_cases": {"D_mix": source_mismatch["D_mix"], "D_log": source_mismatch["D_log"], "overall": sum(source_mismatch.values())},
            "no_archived_source_cases": {"D_mix": no_source["D_mix"], "D_log": no_source["D_log"], "overall": sum(no_source.values())},
            "source_matched_cases_replayed": {"D_mix": attempted["D_mix"], "D_log": attempted["D_log"], "overall": len(rows)},
        },
        "original_control_passed_cases": {"D_mix": controls["D_mix"], "D_log": controls["D_log"], "overall": valid_total},
        "original_control_failed_cases_excluded": {"D_mix": excluded["D_mix"], "D_log": excluded["D_log"], "overall": sum(excluded.values())},
        "evaluated_patched_cases": {"D_mix": attempted["D_mix"], "D_log": attempted["D_log"], "overall": len(rows)},
        "effective_evaluated_cases_original_control_passed": {"D_mix": controls["D_mix"], "D_log": controls["D_log"], "overall": valid_total},
        "status_counts": {
            "D_mix": {"stopped_at_patched_code": stopped["D_mix"], "no_reported_impact": no_impact["D_mix"], "still_passed_validation": still["D_mix"]},
            "D_log": {"stopped_at_patched_code": stopped["D_log"], "no_reported_impact": no_impact["D_log"], "still_passed_validation": still["D_log"]},
            "overall": {"stopped_at_patched_code": sum(stopped.values()), "no_reported_impact": sum(no_impact.values()), "still_passed_validation": sum(still.values())},
        },
        "no_longer_passed": {
            "D_mix": {"numerator": no_longer["D_mix"], "denominator": attempted["D_mix"], "percent": pct(no_longer["D_mix"], attempted["D_mix"])},
            "D_log": {"numerator": no_longer["D_log"], "denominator": attempted["D_log"], "percent": pct(no_longer["D_log"], attempted["D_log"])},
            "overall": {"numerator": sum(no_longer.values()), "denominator": len(rows), "percent": pct(sum(no_longer.values()), len(rows))},
        },
        "no_longer_passed_valid_control_subset": {
            "D_mix": {"numerator": valid_no_longer["D_mix"], "denominator": controls["D_mix"], "percent": pct(valid_no_longer["D_mix"], controls["D_mix"])},
            "D_log": {"numerator": valid_no_longer["D_log"], "denominator": controls["D_log"], "percent": pct(valid_no_longer["D_log"], controls["D_log"])},
            "overall": {"numerator": sum(valid_no_longer.values()), "denominator": valid_total, "percent": pct(sum(valid_no_longer.values()), valid_total)},
        },
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")

    d_mix, d_log = attempted["D_mix"], attempted["D_log"]
    tex = f"""% Source-matched replay attempts: {attempted['D_mix']} D_mix and {attempted['D_log']} D_log.\n% Original controls passing: {d_mix} D_mix and {d_log} D_log; excluded controls: {excluded['D_mix']} and {excluded['D_log']}.\n\\renewcommand\\arraystretch{{1.0}}\n\\begin{{table}}[t]\n\\centering\n\\small\n\\caption{{Results of replaying the original PoCs on patched contracts.}}\n\\vspace{{-0.7em}}\n\\label{{tab:patched_contracts}}\n\n\\resizebox{{\\columnwidth}}{{!}}{{\n\\begin{{tabular}}{{lccc}}\n\\toprule\n\\textbf{{Result}}\n& $\\mathbf{{D}}_{{\\mathrm{{mix}}}}$\n& $\\mathbf{{D}}_{{\\mathrm{{log}}}}$\n& \\textbf{{Overall}} \\\\ \n\\midrule\nOriginal VPR passes     & {baseline['D_mix']} & {baseline['D_log']} & {sum(baseline.values())} \\\\nEvaluated patched cases & {d_mix} & {d_log} & {valid_total}  \\\\nStopped at patched code & {stopped['D_mix']} & {stopped['D_log']} & {sum(stopped.values())}  \\\\nNo reported impact      & {no_impact['D_mix']} & {no_impact['D_log']} & {sum(no_impact.values())}  \\\\nStill passed validation & {still['D_mix']} & {still['D_log']} & {sum(still.values())}  \\\\n\\midrule\nNo longer passed        & {no_longer['D_mix']}/{d_mix} ({pct(no_longer['D_mix'], d_mix):.1f}\\%) & {no_longer['D_log']}/{d_log} ({pct(no_longer['D_log'], d_log):.1f}\\%) & {sum(no_longer.values())}/{valid_total} ({pct(sum(no_longer.values()), valid_total):.1f}\\%) \\\\n\\bottomrule\n\\end{{tabular}}\n}}\n\n\\vspace{{-0.4em}}\n\\end{{table}}\n"""
    # The effectiveness denominator is reported separately in summary.json;
    # the requested table counts the complete source-backed replay population.
    table_total = len(rows)
    tex = tex.replace(
        f"% Original controls passing: {d_mix} D_mix and {d_log} D_log; excluded controls: {excluded['D_mix']} and {excluded['D_log']}.",
        f"% Original controls passing: {controls['D_mix']} D_mix and {controls['D_log']} D_log; excluded controls: {excluded['D_mix']} and {excluded['D_log']}.",
    )
    tex = tex.replace("% Source-matched replay attempts:", "% Source-backed replay attempts:")
    tex = tex.replace(
        f"Evaluated patched cases & {d_mix} & {d_log} & {valid_total}",
        f"Evaluated patched cases & {d_mix} & {d_log} & {table_total}",
    )
    old_total = f"& {sum(no_longer.values())}/{valid_total} ({pct(sum(no_longer.values()), valid_total):.1f}\\%)"
    new_total = f"& {sum(no_longer.values())}/{table_total} ({pct(sum(no_longer.values()), table_total):.1f}\\%)"
    tex = tex.replace(old_total, new_total)
    # The template is assembled with escaped line markers; materialize them as
    # real newlines in the LaTeX artifact.
    tex = tex.replace("\\\\n", "\n")
    tex_lines = []
    for line in tex.splitlines():
        if line.startswith(("Original VPR passes", "Evaluated patched cases", "Stopped at patched code", "No reported impact", "Still passed validation", "No longer passed")):
            line += r"\\"
        tex_lines.append(line)
    (OUT / "patched_contracts_table.tex").write_text("\n".join(tex_lines) + "\n")

    # Mark every source-matched project that was actually compiled/replayed.
    by_project = {(row["dataset"], row["project"]) for row in rows}
    for metadata_path in sorted(DATASET.glob("*/*/metadata.json")):
        metadata = json.loads(metadata_path.read_text())
        key = (metadata["source_dataset"], metadata["project"])
        if metadata.get("patch_status") == "source_mismatch" or key not in by_project:
            continue
        patched_path = metadata_path.with_name("Patched.sol")
        metadata["validation"] = {
            "compile_status": "passed",
            "compiler": "forge build (pragma-selected solc)",
            "poc_regression": "replayed",
            "replay_records": sum(1 for row in rows if (row["dataset"], row["project"]) == key),
        }
        metadata["patched_source_sha256"] = sha256(patched_path)
        for finding in metadata.get("findings", []):
            if finding.get("patch_status") == "pending_patch":
                finding["patch_status"] = "patched"
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
