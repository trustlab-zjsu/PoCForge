#!/usr/bin/env python3
"""
Run LogicGap ablation experiments over the finalized task list.

Task list source (baseline):
  - results/general_dataset/<project>/finding_<id>/result.json
  - results/complex_dataset/<project>/finding_<id>/result.json

Targets:
  - data/general_dataset/general_dataset/*.json
  - data/complex_dataset/*.json

Example:
  .venv/bin/python scripts/run_logicgap_ablation_replay.py \
    --mode m1 --model deepseek-chat --api-url https://api.deepseek.com/v1
"""

from __future__ import annotations

import argparse
import json
import os
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
    baseline_status: str


def normalize_name(text: str) -> str:
    value = text.strip().lower()
    for suffix in (".pdf.json", ".json", ".pdf"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return re.sub(r"[^a-z0-9]+", "", value)


def strip_pdf_suffix(name: str) -> str:
    return name[:-4] if name.endswith(".pdf") else name


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
            result_path = finding_dir / "result.json"
            if not result_path.exists():
                continue
            baseline_status = "UNKNOWN"
            try:
                data = json.loads(result_path.read_text(encoding="utf-8"))
                baseline_status = str(data.get("status", "UNKNOWN")).upper()
            except Exception:
                baseline_status = "UNREADABLE"

            tasks.append(
                Task(
                    dataset=dataset,
                    project=project_dir.name,
                    finding_id=int(m.group(1)),
                    baseline_status=baseline_status,
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
        stem = strip_pdf_suffix(path.stem)
        candidates = {
            name,
            path.stem,
            stem,
            re.sub(r"\.json$", "", name),
            re.sub(r"\.pdf\.json$", "", name),
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


def output_dir_for(dataset: str, results_root: Path, output_prefix: str, mode: str) -> Path:
    if dataset == "general_dataset":
        return results_root / f"{output_prefix}_{mode}_general"
    if dataset == "complex_dataset":
        return results_root / f"{output_prefix}_{mode}_complex"
    raise ValueError(f"Unknown dataset: {dataset}")


def result_path_for_candidates(output_dir: Path, finding_id: int, project_candidates: List[str]) -> Path | None:
    unique_candidates: List[str] = []
    for c in project_candidates:
        c = c.strip()
        if c and c not in unique_candidates:
            unique_candidates.append(c)

    for project in unique_candidates:
        rp = output_dir / project / f"finding_{finding_id}" / "result.json"
        if rp.exists():
            return rp

    wanted = {normalize_name(c) for c in unique_candidates if c}
    if not wanted or not output_dir.exists():
        return None

    for project_dir in sorted(p for p in output_dir.iterdir() if p.is_dir()):
        if normalize_name(project_dir.name) not in wanted:
            continue
        rp = project_dir / f"finding_{finding_id}" / "result.json"
        if rp.exists():
            return rp

    return None


def read_status_from_result(result_path: Path | None) -> str:
    if result_path is None or not result_path.exists():
        return "MISSING"
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception:
        return "UNREADABLE"
    return str(data.get("status", "UNKNOWN")).upper()


def attempts_for_task(task: Task, mode: str, max_attempts: int, m3_success_attempts: int, m3_fail_attempts: int) -> int:
    if mode != "m3":
        return max_attempts
    if task.baseline_status == "SUCCESS":
        return m3_success_attempts
    return m3_fail_attempts


def run_task(
    task: Task,
    target: Path,
    output_dir: Path,
    python_bin: str,
    task_max_attempts: int,
    mode: str,
    model: str,
    api_url: str,
    request_timeout: int,
    max_retries: int,
) -> int:
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
        str(task_max_attempts),
    ]

    env = os.environ.copy()
    env["ABLATION_MODE"] = mode
    env["LLM_MODEL"] = model
    env["LLM_API_URL"] = api_url
    env["LLM_REQUEST_TIMEOUT"] = str(request_timeout)
    env["LLM_MAX_RETRIES"] = str(max_retries)

    print(f"\n>>> [{task.dataset}] {task.project}#finding_{task.finding_id}")
    print(f"BASELINE_STATUS={task.baseline_status} | max_attempts={task_max_attempts}")
    print("CMD:", " ".join(cmd))
    proc = subprocess.run(cmd, env=env)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LogicGap ablation replay with baseline task list.")
    parser.add_argument("--mode", required=True, choices=["m1", "m2", "m3"], help="Ablation mode to run")
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["general_dataset", "complex_dataset"],
        choices=["general_dataset", "complex_dataset"],
        help="Datasets to replay",
    )
    parser.add_argument("--python-bin", default=".venv/bin/python", help="Python executable for main.py")
    parser.add_argument("--task-results-root", default="results", help="Root for baseline task list")
    parser.add_argument("--results-root", default="results", help="Root for ablation outputs")
    parser.add_argument("--output-prefix", default="deepseek", help="Output prefix")
    parser.add_argument("--model", default="deepseek-chat", help="LLM model name")
    parser.add_argument("--api-url", default="https://api.deepseek.com/v1", help="LLM API URL")
    parser.add_argument("--request-timeout", type=int, default=180, help="LLM request timeout seconds")
    parser.add_argument("--max-retries", type=int, default=2, help="LLM request max retries")
    parser.add_argument("--max-attempts", type=int, default=3, help="Default max attempts (M1/M2)")
    parser.add_argument("--m3-success-attempts", type=int, default=1, help="M3 attempts for baseline SUCCESS")
    parser.add_argument("--m3-fail-attempts", type=int, default=5, help="M3 attempts for baseline FAILED/ERROR")
    parser.add_argument("--limit", type=int, default=0, help="Optional max tasks to run")
    parser.add_argument("--no-resume", action="store_true", help="Do not skip existing outputs")
    parser.add_argument(
        "--rerun-statuses",
        nargs="+",
        default=[],
        help="When resuming, rerun tasks whose existing output status is in this list (e.g. ERROR MISSING).",
    )
    args = parser.parse_args()

    rerun_statuses = {s.upper() for s in args.rerun_statuses}

    results_root = Path(args.results_root)
    baseline_root = Path(args.task_results_root)

    tasks: List[Task] = []
    for ds in args.datasets:
        tasks.extend(collect_tasks(baseline_root, ds))

    tasks.sort(key=lambda t: (t.dataset, t.project.lower(), t.finding_id))
    if args.limit > 0:
        tasks = tasks[: args.limit]

    print(f"Collected {len(tasks)} tasks from datasets: {', '.join(args.datasets)}")
    print(f"Ablation mode:     {args.mode}")
    print(f"Model/API:         {args.model} @ {args.api_url}")
    print(f"Task source root:  {baseline_root}")
    print(f"Output root:       {results_root}")
    print(f"Output prefix:     {args.output_prefix}")
    if rerun_statuses:
        print(f"Rerun statuses:    {', '.join(sorted(rerun_statuses))}")
    if not tasks:
        return 0

    indexes: Dict[str, Tuple[Dict[str, List[Path]], Dict[str, List[Path]]]] = {}
    for ds in args.datasets:
        indexes[ds] = build_target_index(ds)

    missing_target = 0
    skipped = 0
    executed = 0
    success = 0
    failed = 0
    error_other = 0

    for i, task in enumerate(tasks, start=1):
        out_dir = output_dir_for(task.dataset, results_root, args.output_prefix, args.mode)
        out_dir.mkdir(parents=True, exist_ok=True)

        exact_idx, norm_idx = indexes[task.dataset]
        target = resolve_target(task.project, exact_idx, norm_idx)
        if target is None:
            missing_target += 1
            print(f"[{i}/{len(tasks)}] MISSING target for {task.dataset}/{task.project}")
            continue

        target_project = strip_pdf_suffix(target.stem)
        candidates = [task.project, target_project]
        existing_result = result_path_for_candidates(out_dir, task.finding_id, candidates)

        if not args.no_resume and existing_result is not None:
            existing_status = read_status_from_result(existing_result)
            if existing_status not in rerun_statuses:
                skipped += 1
                print(
                    f"[{i}/{len(tasks)}] SKIP existing: "
                    f"{task.dataset}/{task.project}/finding_{task.finding_id} "
                    f"(status={existing_status})"
                )
                continue
            print(
                f"[{i}/{len(tasks)}] RERUN existing: "
                f"{task.dataset}/{task.project}/finding_{task.finding_id} "
                f"(status={existing_status})"
            )

        task_max_attempts = attempts_for_task(
            task,
            args.mode,
            args.max_attempts,
            args.m3_success_attempts,
            args.m3_fail_attempts,
        )
        rc = run_task(
            task,
            target,
            out_dir,
            args.python_bin,
            task_max_attempts,
            args.mode,
            args.model,
            args.api_url,
            args.request_timeout,
            args.max_retries,
        )
        executed += 1

        latest_result = result_path_for_candidates(out_dir, task.finding_id, candidates)
        status = read_status_from_result(latest_result)
        print(f"RESULT: rc={rc} status={status}")

        if status == "SUCCESS":
            success += 1
        elif status == "FAILED":
            failed += 1
        else:
            error_other += 1

    print("\n===== Ablation Replay Summary =====")
    print(f"Mode:           {args.mode}")
    print(f"Total tasks:    {len(tasks)}")
    print(f"Executed:       {executed}")
    print(f"Skipped:        {skipped}")
    print(f"Missing target: {missing_target}")
    print(f"SUCCESS:        {success}")
    print(f"FAILED:         {failed}")
    print(f"ERROR/OTHER:    {error_other}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
