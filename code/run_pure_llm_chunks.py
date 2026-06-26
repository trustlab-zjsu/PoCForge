"""
Resumable chunk runner for the pure LLM baseline.

The default pure_llm_baseline batch command writes a final summary after a full
dataset pass. This runner records progress after every finding and groups work
by target chunks so long experiments can be resumed without losing completed
results.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from core.main import load_target
from core.pure_llm_baseline import (
    COMPARISON_RESULTS_DIR,
    COMPARISON_STATS_DIR,
    run_pure_llm_baseline,
    write_metrics_csv,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUN_LOG_DIR = PROJECT_ROOT / "experimental_artifact" / "run_logs" / "pure_llm"

logger = logging.getLogger("pure_llm_chunk_runner")


def parse_dataset_spec(spec: str) -> tuple[Path, str]:
    if ":" in spec:
        path, run_name = spec.rsplit(":", 1)
        return Path(path), run_name
    path = Path(spec)
    normalized = str(path).lower()
    if "d_mix" in normalized or "dmix" in normalized:
        return path, "pure_llm_D_mix"
    if "d_log" in normalized or "dlog" in normalized:
        return path, "pure_llm_D_log"
    return path, f"pure_llm_{path.name}"


def discover_targets(dataset_dir: Path) -> list[Path]:
    return sorted({
        *dataset_dir.glob("**/*.pdf.json"),
        *dataset_dir.glob("**/*.json"),
    })


def selected_finding_ids(target_path: Path, severities: set[str]) -> list[int]:
    target = load_target(str(target_path))
    return [
        finding.id
        for finding in target.findings
        if finding.severity.lower() in severities
    ]


def result_path(output_dir: Path, target_path: Path, finding_id: int) -> Path:
    project_id = target_path.stem
    if project_id.endswith(".pdf"):
        project_id = project_id[:-4]
    return output_dir / project_id / f"finding_{finding_id}" / "result.json"


def load_existing_result(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def append_event(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def collect_results(output_dir: Path) -> list[dict]:
    results: list[dict] = []
    for path in sorted(output_dir.glob("*/finding_*/result.json")):
        result = load_existing_result(path)
        if result:
            results.append(result)
    return results


def summarize(results: list[dict]) -> dict:
    return {
        "total_findings": len(results),
        "success": sum(1 for item in results if item.get("status") == "SUCCESS"),
        "failed": sum(1 for item in results if item.get("status") == "FAILED"),
        "error": sum(1 for item in results if item.get("status") == "ERROR"),
        "compiled": sum(1 for item in results if item.get("compiled")),
        "oracle_passed": sum(1 for item in results if item.get("oracle_passed")),
        "tokens": sum(
            int(item.get("prompt_tokens", 0) or 0) + int(item.get("completion_tokens", 0) or 0)
            for item in results
        ),
        "estimated_cost_usd": round(sum(float(item.get("total_cost", 0.0) or 0.0) for item in results), 6),
    }


def run_dataset(
    dataset_dir: Path,
    run_name: str,
    severities: set[str],
    chunk_size: int,
    block_number: int | None,
    log_dir: Path,
    dry_run: bool,
) -> dict:
    output_dir = COMPARISON_RESULTS_DIR / run_name
    metrics_csv = COMPARISON_STATS_DIR / f"{run_name}_metrics.csv"
    events_path = log_dir / f"{run_name}_events.jsonl"
    progress_path = log_dir / f"{run_name}_progress.json"

    targets = discover_targets(dataset_dir)
    dataset_summary = {
        "dataset_dir": str(dataset_dir),
        "run_name": run_name,
        "output_dir": str(output_dir),
        "metrics_csv": str(metrics_csv),
        "target_count": len(targets),
        "chunk_size": chunk_size,
        "severity": sorted(severities),
        "started_at": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(progress_path, dataset_summary | {"status": "started"})

    logger.info("Dataset %s: %s targets", run_name, len(targets))
    if dry_run:
        total_findings = 0
        for target in targets:
            total_findings += len(selected_finding_ids(target, severities))
        dataset_summary["selected_findings"] = total_findings
        write_json(progress_path, dataset_summary | {"status": "dry_run"})
        return dataset_summary

    for chunk_start in range(0, len(targets), chunk_size):
        chunk_targets = targets[chunk_start:chunk_start + chunk_size]
        chunk_index = chunk_start // chunk_size + 1
        total_chunks = (len(targets) + chunk_size - 1) // chunk_size
        logger.info("[%s] chunk %s/%s: targets %s-%s", run_name, chunk_index, total_chunks, chunk_start + 1, chunk_start + len(chunk_targets))

        for target_path in chunk_targets:
            try:
                finding_ids = selected_finding_ids(target_path, severities)
            except Exception as exc:
                append_event(events_path, {
                    "time": datetime.now().isoformat(timespec="seconds"),
                    "run_name": run_name,
                    "target": str(target_path),
                    "status": "LOAD_ERROR",
                    "error": str(exc),
                })
                continue

            if not finding_ids:
                append_event(events_path, {
                    "time": datetime.now().isoformat(timespec="seconds"),
                    "run_name": run_name,
                    "target": str(target_path),
                    "status": "SKIPPED_NO_FINDINGS",
                })
                continue

            for finding_id in finding_ids:
                existing = load_existing_result(result_path(output_dir, target_path, finding_id))
                if existing:
                    append_event(events_path, {
                        "time": datetime.now().isoformat(timespec="seconds"),
                        "run_name": run_name,
                        "target": str(target_path),
                        "finding_id": finding_id,
                        "status": "SKIPPED_EXISTING",
                        "result_status": existing.get("status"),
                    })
                    continue

                started = time.time()
                append_event(events_path, {
                    "time": datetime.now().isoformat(timespec="seconds"),
                    "run_name": run_name,
                    "target": str(target_path),
                    "finding_id": finding_id,
                    "status": "STARTED",
                    "chunk": chunk_index,
                })

                try:
                    result = run_pure_llm_baseline(
                        target_path=str(target_path),
                        output_dir=str(output_dir),
                        finding_id=finding_id,
                        block_number=block_number,
                    )
                    append_event(events_path, {
                        "time": datetime.now().isoformat(timespec="seconds"),
                        "run_name": run_name,
                        "target": str(target_path),
                        "finding_id": finding_id,
                        "status": "FINISHED",
                        "result_status": result.get("status"),
                        "compiled": result.get("compiled"),
                        "oracle_passed": result.get("oracle_passed"),
                        "duration_seconds": round(time.time() - started, 2),
                    })
                except Exception as exc:
                    append_event(events_path, {
                        "time": datetime.now().isoformat(timespec="seconds"),
                        "run_name": run_name,
                        "target": str(target_path),
                        "finding_id": finding_id,
                        "status": "ERROR",
                        "error": str(exc),
                        "duration_seconds": round(time.time() - started, 2),
                    })

                results = collect_results(output_dir)
                write_metrics_csv(results, metrics_csv)
                write_json(progress_path, dataset_summary | {
                    "status": "running",
                    "last_target": str(target_path),
                    "last_finding_id": finding_id,
                    "last_update": datetime.now().isoformat(timespec="seconds"),
                    "summary": summarize(results),
                })

    results = collect_results(output_dir)
    write_metrics_csv(results, metrics_csv)
    final_summary = dataset_summary | {
        "status": "complete",
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "summary": summarize(results),
    }
    write_json(progress_path, final_summary)
    return final_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run pure LLM baseline in resumable chunks")
    parser.add_argument(
        "--dataset",
        action="append",
        required=True,
        help="Dataset directory, optionally suffixed with :run_name. Can be repeated.",
    )
    parser.add_argument("--chunk-size", type=int, default=5)
    parser.add_argument("--severity", nargs="+", default=["critical", "high", "medium"])
    parser.add_argument("--block-number", type=int, default=None)
    parser.add_argument("--log-dir", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log_dir = Path(args.log_dir) if args.log_dir else RUN_LOG_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "chunk_size": args.chunk_size,
        "severity": args.severity,
        "datasets": args.dataset,
        "dry_run": args.dry_run,
        "log_dir": str(log_dir),
    }
    write_json(log_dir / "manifest.json", manifest)

    summaries = []
    severities = {item.lower() for item in args.severity}
    for spec in args.dataset:
        dataset_dir, run_name = parse_dataset_spec(spec)
        summaries.append(run_dataset(
            dataset_dir=dataset_dir,
            run_name=run_name,
            severities=severities,
            chunk_size=args.chunk_size,
            block_number=args.block_number,
            log_dir=log_dir,
            dry_run=args.dry_run,
        ))

    write_json(log_dir / "summary.json", {
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "summaries": summaries,
    })
    logger.info("Pure LLM chunk run complete. Logs: %s", log_dir)


if __name__ == "__main__":
    main()
