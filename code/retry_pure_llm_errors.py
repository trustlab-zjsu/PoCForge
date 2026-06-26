"""
Retry unresolved pure LLM ERROR cases until every selected finding has a result.

Unresolved means an event log contains a target/finding ERROR but the expected
Comparison result.json is still missing. Successful and failed Forge outcomes
are not rerun; only missing results are retried.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from core.pure_llm_baseline import (
    COMPARISON_RESULTS_DIR,
    COMPARISON_STATS_DIR,
    run_pure_llm_baseline,
    write_metrics_csv,
)
from run_pure_llm_chunks import collect_results, summarize


PROJECT_ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger("pure_llm_error_retry")


def project_id_for_target(target_path: str | Path) -> str:
    project_id = Path(target_path).stem
    if project_id.endswith(".pdf"):
        project_id = project_id[:-4]
    return project_id


def result_path(run_name: str, target_path: str | Path, finding_id: int) -> Path:
    return (
        COMPARISON_RESULTS_DIR
        / run_name
        / project_id_for_target(target_path)
        / f"finding_{finding_id}"
        / "result.json"
    )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def append_event(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def parse_error_events(events_path: Path) -> dict[tuple[str, int], dict]:
    errors: dict[tuple[str, int], dict] = {}
    if not events_path.exists():
        return errors
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("status") != "ERROR":
            continue
        target = event.get("target")
        finding_id = event.get("finding_id")
        if target is None or finding_id is None:
            continue
        errors[(target, int(finding_id))] = event
    return errors


def unresolved_errors(run_name: str, source_events: list[Path], retry_events: Path) -> list[dict]:
    merged: dict[tuple[str, int], dict] = {}
    for path in [*source_events, retry_events]:
        merged.update(parse_error_events(path))

    unresolved = []
    for (target, finding_id), event in sorted(merged.items()):
        if not result_path(run_name, target, finding_id).exists():
            unresolved.append({
                "target": target,
                "finding_id": finding_id,
                "last_error": event.get("error", ""),
            })
    return unresolved


def refresh_metrics(run_name: str) -> dict:
    output_dir = COMPARISON_RESULTS_DIR / run_name
    metrics_csv = COMPARISON_STATS_DIR / f"{run_name}_metrics.csv"
    results = collect_results(output_dir)
    write_metrics_csv(results, metrics_csv)
    return summarize(results)


def run_retry_loop(
    run_name: str,
    source_events: list[Path],
    retry_log_dir: Path,
    sleep_seconds: int,
    block_number: int | None,
) -> dict:
    retry_events = retry_log_dir / f"{run_name}_retry_events.jsonl"
    progress_path = retry_log_dir / f"{run_name}_retry_progress.json"
    round_num = 0

    while True:
        round_num += 1
        pending = unresolved_errors(run_name, source_events, retry_events)
        summary = refresh_metrics(run_name)
        write_json(progress_path, {
            "run_name": run_name,
            "status": "running" if pending else "complete",
            "round": round_num,
            "pending_errors": len(pending),
            "last_update": datetime.now().isoformat(timespec="seconds"),
            "summary": summary,
        })

        if not pending:
            logger.info("[%s] no unresolved errors remain", run_name)
            return {
                "run_name": run_name,
                "status": "complete",
                "rounds": round_num - 1,
                "summary": summary,
            }

        logger.info("[%s] retry round %s: %s unresolved errors", run_name, round_num, len(pending))
        for item in pending:
            target = item["target"]
            finding_id = int(item["finding_id"])
            if result_path(run_name, target, finding_id).exists():
                continue

            started = time.time()
            append_event(retry_events, {
                "time": datetime.now().isoformat(timespec="seconds"),
                "run_name": run_name,
                "target": target,
                "finding_id": finding_id,
                "status": "RETRY_STARTED",
                "round": round_num,
            })
            try:
                result = run_pure_llm_baseline(
                    target_path=target,
                    output_dir=str(COMPARISON_RESULTS_DIR / run_name),
                    finding_id=finding_id,
                    block_number=block_number,
                )
                append_event(retry_events, {
                    "time": datetime.now().isoformat(timespec="seconds"),
                    "run_name": run_name,
                    "target": target,
                    "finding_id": finding_id,
                    "status": "RETRY_FINISHED",
                    "result_status": result.get("status"),
                    "compiled": result.get("compiled"),
                    "oracle_passed": result.get("oracle_passed"),
                    "duration_seconds": round(time.time() - started, 2),
                    "round": round_num,
                })
            except Exception as exc:
                append_event(retry_events, {
                    "time": datetime.now().isoformat(timespec="seconds"),
                    "run_name": run_name,
                    "target": target,
                    "finding_id": finding_id,
                    "status": "ERROR",
                    "error": str(exc),
                    "duration_seconds": round(time.time() - started, 2),
                    "round": round_num,
                })

            summary = refresh_metrics(run_name)
            pending_count = len(unresolved_errors(run_name, source_events, retry_events))
            write_json(progress_path, {
                "run_name": run_name,
                "status": "running",
                "round": round_num,
                "last_target": target,
                "last_finding_id": finding_id,
                "pending_errors": pending_count,
                "last_update": datetime.now().isoformat(timespec="seconds"),
                "summary": summary,
            })

        remaining = unresolved_errors(run_name, source_events, retry_events)
        if remaining:
            logger.info("[%s] round %s complete: %s still unresolved; sleeping %ss", run_name, round_num, len(remaining), sleep_seconds)
            time.sleep(sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Retry unresolved pure LLM ERROR cases")
    parser.add_argument("--source-log-dir", required=True)
    parser.add_argument("--run-name", action="append", required=True)
    parser.add_argument("--log-dir", default=None)
    parser.add_argument("--sleep-seconds", type=int, default=60)
    parser.add_argument("--block-number", type=int, default=None)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    source_log_dir = Path(args.source_log_dir)
    retry_log_dir = Path(args.log_dir) if args.log_dir else (
        PROJECT_ROOT / "experimental_artifact" / "run_logs" / "pure_llm" / f"retry_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    retry_log_dir.mkdir(parents=True, exist_ok=True)
    write_json(retry_log_dir / "manifest.json", {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "source_log_dir": str(source_log_dir),
        "run_names": args.run_name,
        "sleep_seconds": args.sleep_seconds,
    })

    summaries = []
    for run_name in args.run_name:
        source_events = [source_log_dir / f"{run_name}_events.jsonl"]
        summaries.append(run_retry_loop(
            run_name=run_name,
            source_events=source_events,
            retry_log_dir=retry_log_dir,
            sleep_seconds=args.sleep_seconds,
            block_number=args.block_number,
        ))

    write_json(retry_log_dir / "summary.json", {
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "summaries": summaries,
    })
    logger.info("Retry run complete. Logs: %s", retry_log_dir)


if __name__ == "__main__":
    main()
