#!/usr/bin/env python3
"""Align Pure LLM metrics to the Table III evaluation target set."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAT_DIR = ROOT / "experimental_artifact" / "Statistical Results"
DIFF_LLM_DIR = STAT_DIR / "Different_LLM"
COMPARISON_DIR = STAT_DIR / "Comparison"

DATASETS = {
    "D_mix": {
        "canonical": DIFF_LLM_DIR / "Gemini_D_mix(baseline).csv",
        "pure": COMPARISON_DIR / "pure_llm_D_mix_metrics.csv",
        "output": COMPARISON_DIR / "pure_llm_D_mix_tableIII_metrics.csv",
    },
    "D_log": {
        "canonical": DIFF_LLM_DIR / "Gemini_D_log(baseline).csv",
        "pure": COMPARISON_DIR / "pure_llm_D_log_metrics.csv",
        "output": COMPARISON_DIR / "pure_llm_D_log_tableIII_metrics.csv",
    },
}


SUMMARY_PREFIXES = ("---", "CSR", "ERR", "VPR")


def is_summary_row(row: dict[str, str]) -> bool:
    project = (row.get("Project") or "").strip()
    return not project or project.startswith(SUMMARY_PREFIXES)


def load_data_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            if is_summary_row(row):
                break
            rows.append(row)
        return list(reader.fieldnames or []), rows


def norm_text(text: str) -> str:
    text = re.sub(r"\((economic|logic|unknown)\)", "", text, flags=re.I)
    text = text.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def norm_project(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def yes(row: dict[str, str], field: str) -> bool:
    return "yes" in (row.get(field) or "").lower()


def percent(count: int, total: int) -> float:
    return round(count * 100.0 / total, 1) if total else 0.0


def add_summary_rows(rows: list[dict[str, str]], fieldnames: list[str]) -> list[dict[str, str]]:
    total = len(rows)
    compiled = sum(yes(r, "Compiled?") for r in rows)
    revert_free = sum(yes(r, "Revert Free?") for r in rows)
    oracle = sum(yes(r, "Oracle Passed?") for r in rows)

    def empty_row() -> dict[str, str]:
        return {field: "" for field in fieldnames}

    out = list(rows)
    summary = empty_row()
    summary["Project"] = "--- SUMMARY ---"
    out.append(summary)

    csr = empty_row()
    csr["Project"] = "CSR (Compilation Success Rate)"
    csr["Vuln Category"] = f"{compiled}/{total} = {percent(compiled, total):.1f}%"
    out.append(csr)

    err = empty_row()
    err["Project"] = "ERR (EVM Interaction Pass Rate)"
    err["Vuln Category"] = f"{revert_free}/{total} = {percent(revert_free, total):.1f}%"
    out.append(err)

    vpr = empty_row()
    vpr["Project"] = "VPR (Oracle Verification Pass Rate)"
    vpr["Vuln Category"] = f"{oracle}/{total} = {percent(oracle, total):.1f}%"
    out.append(vpr)

    return out


def build_project_index(rows: list[dict[str, str]]) -> dict[str, str]:
    index: dict[str, str] = {}
    projects_by_key: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        projects_by_key[norm_project(row["Project"])].add(row["Project"])
    for key, projects in projects_by_key.items():
        if len(projects) == 1:
            index[key] = next(iter(projects))
    return index


def align_rows(
    canonical_rows: list[dict[str, str]], pure_rows: list[dict[str, str]]
) -> tuple[list[dict[str, str]], Counter]:
    pure_by_project: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in pure_rows:
        pure_by_project[row["Project"]].append(row)

    project_index = build_project_index(pure_rows)
    used_by_project: dict[str, set[int]] = defaultdict(set)
    cursors: dict[str, int] = defaultdict(int)
    stats: Counter = Counter()
    aligned = []

    for canonical in canonical_rows:
        project = canonical["Project"]
        pure_project = project if project in pure_by_project else project_index.get(norm_project(project))
        candidates = pure_by_project.get(pure_project or "", [])

        chosen_idx = None
        wanted_title = norm_text(canonical.get("Vuln Category", ""))
        if wanted_title:
            for idx, candidate in enumerate(candidates):
                if idx in used_by_project[pure_project or ""]:
                    continue
                candidate_title = norm_text(candidate.get("Vuln Category", ""))
                if candidate_title == wanted_title:
                    chosen_idx = idx
                    stats["title_match"] += 1
                    break

        if chosen_idx is None and candidates:
            cursor = cursors[pure_project or ""]
            while cursor < len(candidates) and cursor in used_by_project[pure_project or ""]:
                cursor += 1
            if cursor < len(candidates):
                chosen_idx = cursor
                cursors[pure_project or ""] = cursor + 1
                stats["order_match"] += 1

        if chosen_idx is None:
            chosen = {
                "Project": project,
                "Vuln Category": canonical.get("Vuln Category", ""),
                "Attempts": "0 / 1",
                "Compiled?": "No",
                "Revert Free?": "No",
                "Oracle Passed?": "No",
                "Tokens Used": "0",
                "Est. Cost ($)": "$0.0000",
                "Time (s)": "0.0",
                "Final Status": "FAILED",
                "Fail Reason": "MISSING_PURE_LLM_RESULT",
            }
            stats["missing"] += 1
        else:
            used_by_project[pure_project or ""].add(chosen_idx)
            chosen = dict(candidates[chosen_idx])
            chosen["Project"] = project
            chosen["Vuln Category"] = canonical.get("Vuln Category", chosen.get("Vuln Category", ""))

        aligned.append(chosen)

    return aligned, stats


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def main() -> None:
    for name, paths in DATASETS.items():
        canonical_fields, canonical_rows = load_data_rows(paths["canonical"])
        pure_fields, pure_rows = load_data_rows(paths["pure"])
        fieldnames = pure_fields or canonical_fields
        aligned, match_stats = align_rows(canonical_rows, pure_rows)
        with_summary = add_summary_rows(aligned, fieldnames)
        write_csv(paths["output"], fieldnames, with_summary)

        total = len(aligned)
        compiled = sum(yes(r, "Compiled?") for r in aligned)
        revert_free = sum(yes(r, "Revert Free?") for r in aligned)
        oracle = sum(yes(r, "Oracle Passed?") for r in aligned)
        print(
            f"{name}: #Report={total}, "
            f"CSR={compiled}/{total}={percent(compiled, total):.1f}%, "
            f"ERR={revert_free}/{total}={percent(revert_free, total):.1f}%, "
            f"VPR={oracle}/{total}={percent(oracle, total):.1f}%"
        )
        print(f"  output={paths['output']}")
        print(f"  matching={dict(match_stats)}")


if __name__ == "__main__":
    main()
