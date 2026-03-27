#!/usr/bin/env python3
"""
Replay LogicGap runs for the finalized dataset findings with a new LLM model.

Task list source:
  - results/general_dataset/<project>/finding_<id>/result.json
  - results/complex_dataset/<project>/finding_<id>/result.json

Target source:
  - data/general_dataset/general_dataset/*.json
  - data/complex_dataset/*.json

Outputs (default prefix):
  - results/deepseek_general
  - results/deepseek_complex
You can customize with --output-prefix, e.g.:
  - results/qwen_general
  - results/qwen_complex
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Task:
    dataset: str
    project: str
    finding_id: int


def normalize_name(text: str) -> str:
    value = text.strip().lower()
    for suffix in (".pdf.json", ".json", ".pdf"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return re.sub(r"[^a-z0-9]+", "", value)


def collect_tasks(results_root: Path, dataset: str) -> List[Task]:
    base = results_root / dataset
    tasks: List[Task] = []
    if not base.exists():
        return tasks

    for project_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        for finding_dir in sorted(project_dir.glob("finding_*")):
            m = re.match(r"finding_(\d+)$", finding_dir.name)
            if not m:
                continue
            if not (finding_dir / "result.json").exists():
                continue
            tasks.append(
                Task(
                    dataset=dataset,
                    project=project_dir.name,
                    finding_id=int(m.group(1)),
                )
            )
    return tasks


def build_target_index(dataset: str) -> Tuple[Dict[str, List[Path]], Dict[str, List[Path]]]:
    if dataset == "general_dataset":
        target_root = Path("data/general_dataset/general_dataset")
    elif dataset == "complex_dataset":
        target_root = Path("data/complex_dataset")
    else:
        raise ValueError(f"Unknown dataset: {dataset}")

    exact: Dict[str, List[Path]] = {}
    normalized: Dict[str, List[Path]] = {}
    for path in sorted(target_root.glob("*.json")):
        name = path.name
        candidates = {
            name,
            path.stem,
            re.sub(r"\.json$", "", name),
            re.sub(r"\.pdf\.json$", "", name),
            re.sub(r"\.pdf$", "", path.stem),
        }
        for key in candidates:
            if key:
                exact.setdefault(key, []).append(path)
        norm = normalize_name(path.name)
        if norm:
            normalized.setdefault(norm, []).append(path)

    return exact, normalized


def resolve_target(
    project: str,
    exact_index: Dict[str, List[Path]],
    normalized_index: Dict[str, List[Path]],
) -> Path | None:
    direct = exact_index.get(project, [])
    if len(direct) == 1:
        return direct[0]
    if len(direct) > 1:
        return sorted(direct, key=lambda p: p.name)[0]

    normalized = normalized_index.get(normalize_name(project), [])
    if len(normalized) == 1:
        return normalized[0]
    if len(normalized) > 1:
        return sorted(normalized, key=lambda p: p.name)[0]
    return None


def output_dir_for(dataset: str, results_root: Path, output_prefix: str) -> Path:
    if dataset == "general_dataset":
        return results_root / f"{output_prefix}_general"
    if dataset == "complex_dataset":
        return results_root / f"{output_prefix}_complex"
    raise ValueError(f"Unknown dataset: {dataset}")


def read_status(output_dir: Path, project: str, finding_id: int) -> str:
    result_path = output_dir / project / f"finding_{finding_id}" / "result.json"
    if not result_path.exists():
        return "MISSING"
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception:
        return "UNREADABLE"
    return str(data.get("status", "UNKNOWN"))


def run_task(task: Task, target: Path, output_dir: Path, python_bin: str, max_attempts: int) -> int:
    cmd = [
        python_bin,
        "main.py",
        "--target",
        str(target),
        "--finding-id",
        str(task.finding_id),
        "--output",
        str(output_dir),
        "--max-attempts",
        str(max_attempts),
    ]
    print(f"\n>>> [{task.dataset}] {task.project}#finding_{task.finding_id}")
    print("CMD:", " ".join(cmd))
    proc = subprocess.run(cmd)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay finalized LogicGap tasks with current model env.")
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["general_dataset", "complex_dataset"],
        choices=["general_dataset", "complex_dataset"],
        help="Datasets to replay.",
    )
    parser.add_argument("--python-bin", default=".venv/bin/python", help="Python executable for running main.py")
    parser.add_argument(
        "--task-results-root",
        default="results",
        help="Root directory used only for collecting finalized task list (general_dataset/complex_dataset).",
    )
    parser.add_argument("--results-root", default="results", help="Results root directory")
    parser.add_argument(
        "--output-prefix",
        default="deepseek",
        help="Prefix for output directories under results-root. Example: qwen -> qwen_general/qwen_complex",
    )
    parser.add_argument("--max-attempts", type=int, default=3, help="Max attempts per finding")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of tasks to run (0 = all)")
    parser.add_argument("--no-resume", action="store_true", help="Do not skip tasks that already have outputs")
    args = parser.parse_args()

    results_root = Path(args.results_root)
    task_results_root = Path(args.task_results_root)

    tasks: List[Task] = []
    for ds in args.datasets:
        tasks.extend(collect_tasks(task_results_root, ds))

    # Stable order: dataset, project, finding_id
    tasks.sort(key=lambda t: (t.dataset, t.project.lower(), t.finding_id))
    if args.limit > 0:
        tasks = tasks[: args.limit]

    print(f"Collected {len(tasks)} tasks from datasets: {', '.join(args.datasets)}")
    print(f"Task source root: {task_results_root}")
    print(f"Output root:      {results_root}")
    print(f"Output prefix:    {args.output_prefix}")
    if not tasks:
        return 0

    indexes: Dict[str, Tuple[Dict[str, List[Path]], Dict[str, List[Path]]]] = {}
    for ds in args.datasets:
        indexes[ds] = build_target_index(ds)

    missing = 0
    skipped = 0
    executed = 0
    success = 0
    failed = 0
    errored = 0

    for i, task in enumerate(tasks, start=1):
        out_dir = output_dir_for(task.dataset, results_root, args.output_prefix)
        out_dir.mkdir(parents=True, exist_ok=True)
        result_path = out_dir / task.project / f"finding_{task.finding_id}" / "result.json"
        if not args.no_resume and result_path.exists():
            skipped += 1
            print(f"[{i}/{len(tasks)}] SKIP existing: {task.dataset}/{task.project}/finding_{task.finding_id}")
            continue

        exact_idx, norm_idx = indexes[task.dataset]
        target = resolve_target(task.project, exact_idx, norm_idx)
        if target is None:
            missing += 1
            print(f"[{i}/{len(tasks)}] MISSING target for {task.dataset}/{task.project}")
            continue

        rc = run_task(task, target, out_dir, args.python_bin, args.max_attempts)
        executed += 1
        status = read_status(out_dir, task.project, task.finding_id)
        print(f"RESULT: rc={rc} status={status}")

        if status == "SUCCESS":
            success += 1
        elif status == "FAILED":
            failed += 1
        else:
            errored += 1

    print("\n===== Replay Summary =====")
    print(f"Total tasks:    {len(tasks)}")
    print(f"Executed:       {executed}")
    print(f"Skipped:        {skipped}")
    print(f"Missing target: {missing}")
    print(f"SUCCESS:        {success}")
    print(f"FAILED:         {failed}")
    print(f"ERROR/OTHER:    {errored}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
