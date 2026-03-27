"""
LogicGap CLI Entry Point
Automated smart contract vulnerability PoC generation and verification.

Usage:
    # Single target
    python main.py --target data/targets/1-aibabydoge.pdf.json --output results/

    # Batch processing
    python main.py --batch data/targets/ --output results/

    # With specific finding ID
    python main.py --target data/targets/sample.json --finding-id 10 --output results/
"""

import argparse
import json
import logging
import sys
import shutil
import time
from pathlib import Path
from datetime import datetime

from core.config import (
    get_rpc_url, MAX_ATTEMPTS, DEFAULT_OUTPUT_DIR, FOUNDRY_SANDBOX_DIR
)
from core.models import (
    TargetInput, PipelineResult, PipelineStatus
)
from core.formalizer import formalize, formalize_all_findings
from core.rag_extractor import extract_and_save_rag_knowledge
from core.tools.source_fetcher import fetch_contract_source
from core.agent_loop import run_agent


logger = logging.getLogger("logicgap")


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def load_target(target_path: str) -> TargetInput:
    """Load a target input from a .pdf.json file."""
    path = Path(target_path)
    if not path.exists():
        raise FileNotFoundError(f"Target file not found: {target_path}")

    with open(path) as f:
        data = json.load(f)

    return TargetInput(**data)


def save_result(
    result: PipelineResult,
    output_dir: Path,
    project_id: str,
    finding_id: int,
):
    """Save pipeline result to the output directory."""
    result_dir = output_dir / f"{project_id}" / f"finding_{finding_id}"
    result_dir.mkdir(parents=True, exist_ok=True)

    # Save result summary
    result_json = result_dir / "result.json"
    with open(result_json, "w") as f:
        json.dump(result.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

    # Save violation target
    if result.violation_target:
        vt_json = result_dir / "violation_target.json"
        with open(vt_json, "w") as f:
            json.dump(result.violation_target.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

    # Save final PoC
    if result.final_poc_code:
        poc_file = result_dir / "Exploit.t.sol"
        poc_file.write_text(result.final_poc_code)

    # Save unified attempt history instead of scattered traces
    if result.attempts:
        history_file = result_dir / "attempt_history.json"
        with open(history_file, "w") as f:
            attempts_dump = [a.model_dump(mode="json") for a in result.attempts]
            json.dump(attempts_dump, f, indent=2, ensure_ascii=False)

    logger.info(f"Results saved to {result_dir}")
    return result_dir


def run_single_target(
    target_path: str,
    output_dir: str,
    finding_id: int | None = None,
    severity_filter: list[str] | None = None,
    max_attempts: int | None = None,
    block_number: int | None = None,
):
    """Run the pipeline for a single target."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    # Load target
    target_input = load_target(target_path)
    project_id = Path(target_path).stem
    if project_id.endswith(".pdf"):
        project_id = project_id[:-4]
    
    chain = target_input.project_info.chain
    address = target_input.project_info.address

    logger.info(f"═══ Processing: {project_id} ═══")
    logger.info(f"Address: {address} | Chain: {chain}")

    # Step 1: Fetch contract source (API or Local)
    source_code = ""
    contract_info = {}
    
    # Try finding local .sol file first (Direct Input Mode)
    target_dir = Path(target_path).parent
    local_sol_files = list(target_dir.glob("*.sol"))
    
    # Fallback to FORGE-Artifacts dataset search
    if not local_sol_files and target_input.project_info.project_path:
        base_dataset = Path("/Users/carl/论文中的工具/FORGE-Artifacts/dataset")
        for contract, rel_path in target_input.project_info.project_path.items():
            parts = rel_path.split("/")
            if len(parts) >= 2:
                folder_name = parts[-2]
                found = list(base_dataset.glob(f"**/{folder_name}/*.sol"))
                if found:
                    local_sol_files.extend(found)
                    break
    
    if local_sol_files:
        logger.info(f"Found local source files: {[f.name for f in local_sol_files]}")
        # Combine all found sol files
        source_code = ""
        for sol_file in local_sol_files:
            with open(sol_file, "r", encoding="utf-8") as f:
                source_code += f"// ===== {sol_file.name} =====\n"
                source_code += f.read() + "\n\n"
        contract_info = {
            "source_code": source_code,
            "abi": [],  # We don't have ABI from local file, agent will need to write raw calls or generate it
            "contract_name": project_id,
            "compiler_version": target_input.project_info.compiler_version[0] if target_input.project_info.compiler_version else "0.8.20",
        }
    else:
        # Fallback to API
        try:
            contract_info = fetch_contract_source(address, chain)
            source_code = contract_info["source_code"]
            logger.info(f"Fetched source: {contract_info.get('contract_name', 'Unknown')} "
                         f"({len(source_code)} chars)")
        except Exception as e:
            logger.error(f"Failed to fetch source for {address}: {e}")
            result = PipelineResult(
                project_id=project_id,
                target_address=address,
                finding_id=finding_id or -1,
                status=PipelineStatus.ERROR,
                error_message=f"Source fetch failed: {e}",
            )
            save_result(result, output, project_id, finding_id or 0)
            return [result]

    # Step 2: Formalize vulnerabilities
    rpc_url = get_rpc_url(chain)
    results = []

    if finding_id is not None:
        # Single finding
        try:
            vt = formalize(target_input, source_code, finding_id=finding_id)
            violation_targets = [vt]
        except Exception as e:
            logger.error(f"Formalization failed for finding #{finding_id}: {e}")
            result = PipelineResult(
                project_id=project_id,
                target_address=address,
                finding_id=finding_id,
                status=PipelineStatus.ERROR,
                error_message=f"Formalization failed: {e}",
            )
            save_result(result, output, project_id, finding_id)
            return [result]
    else:
        # All high/medium findings
        severity_filter = severity_filter or ["high", "medium"]
        violation_targets = formalize_all_findings(
            target_input, source_code, severity_filter=severity_filter
        )

    if not violation_targets:
        logger.warning(f"No findings to process for {project_id}")
        return results

    # Step 3: Run agent for each violation target
    for vt in violation_targets:
        logger.info(f"─── Finding #{vt.finding_id}: {vt.vulnerability_type} ({vt.violation_category}) ───")

        try:
            start_t = time.time()
            result = run_agent(
                violation_target=vt,
                source_code=source_code,
                contract_info=contract_info,
                rpc_url=rpc_url,
                block_number=block_number,
                max_attempts=max_attempts,
            )
            # Record total telemetry for this finding
            result.total_duration_seconds = time.time() - start_t
            if result.attempts:
                result.total_prompt_tokens = sum(a.prompt_tokens for a in result.attempts)
                result.total_completion_tokens = sum(a.completion_tokens for a in result.attempts)
                result.total_cost = sum(a.total_cost for a in result.attempts)
        except Exception as e:
            logger.error(f"Agent loop crashed for finding #{vt.finding_id}: {e}")
            result = PipelineResult(
                project_id=project_id,
                target_address=address,
                finding_id=vt.finding_id,
                status=PipelineStatus.ERROR,
                violation_target=vt,
                error_message=str(e),
            )

        save_result(result, output, project_id, vt.finding_id)
        results.append(result)

        # Log summary
        status_icon = "✅" if result.status == PipelineStatus.SUCCESS else "❌"
        logger.info(f"{status_icon} Finding #{vt.finding_id}: {result.status} "
                     f"(attempts: {result.total_attempts})")

    return results


def run_batch(
    batch_dir: str,
    output_dir: str,
    severity_filter: list[str] | None = None,
    max_attempts: int | None = None,
    block_number: int | None = None,
):
    """Run the pipeline for all targets in a directory."""
    batch_path = Path(batch_dir)
    if not batch_path.exists():
        raise FileNotFoundError(f"Batch directory not found: {batch_dir}")

    # Find all .pdf.json files
    target_files = sorted(batch_path.glob("**/*.pdf.json"))
    if not target_files:
        logger.warning(f"No .pdf.json files found in {batch_dir}")
        return

    logger.info(f"Found {len(target_files)} target file(s) in {batch_dir}")

    all_results = []
    summary = {"total": len(target_files), "success": 0, "failed": 0, "error": 0, "skipped": 0}
    
    success_archive = Path("results/success_archive")
    success_archive.mkdir(parents=True, exist_ok=True)

    for i, target_file in enumerate(target_files):
        project_id = target_file.stem
        if project_id.endswith(".pdf"):
            project_id = project_id[:-4]
            
        # Clean up the project_id to only contain the actual project name
        # e.g., "Price_Oracle_and_Flashloan_ATHProtoco" -> "ATHProtoco"
        if "_" in project_id:
            project_id = project_id.split("_")[-1]

        logger.info(f"\n{'='*60}")
        logger.info(f"[{i+1}/{len(target_files)}] Processing: {target_file.name}")
        logger.info(f"{'='*60}")
        
        # Skip if already successfully verified in a previous run
        if (success_archive / project_id).exists():
            logger.info(f"⏭️ Skipping {project_id}: Already successfully exploited and archived!")
            summary["success"] += 1
            summary["skipped"] += 1
            continue

        try:
            results = run_single_target(
                target_path=str(target_file),
                output_dir=output_dir,
                severity_filter=severity_filter,
                max_attempts=max_attempts,
                block_number=block_number,
            )
            all_results.extend(results)

            has_success = False
            for r in results:
                if r.status == PipelineStatus.SUCCESS:
                    has_success = True
                    summary["success"] += 1
                    # Extract successful attempt into RAG knowledge base
                    extract_and_save_rag_knowledge(r, output_dir=Path(output_dir))
                elif r.status == PipelineStatus.FAILED:
                    summary["failed"] += 1
                else:
                    summary["error"] += 1
                    
            if has_success:
                logger.info(f"🏆 Project {project_id} achieved SUCCESS! Saving to persistent archive: {success_archive / project_id}")
                src_dir = Path(output_dir) / project_id
                dst_dir = success_archive / project_id
                if src_dir.exists():
                    shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)

        except Exception as e:
            logger.error(f"Failed to process {target_file.name}: {e}")
            summary["error"] += 1

    # Save batch summary
    output_path = Path(output_dir)
    summary_file = output_path / "batch_summary.json"
    summary["timestamp"] = datetime.now().isoformat()
    summary["results"] = [
        {
            "project_id": r.project_id,
            "finding_id": r.finding_id,
            "status": r.status.value,
            "attempts": r.total_attempts,
            "duration_seconds": round(r.total_duration_seconds, 2),
            "cost_usd": round(r.total_cost, 4),
        }
        for r in all_results
    ]

    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    total_batch_cost = sum(r.total_cost for r in all_results)

    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info(f"BATCH COMPLETE")
    logger.info(f"  Total targets: {summary['total']}")
    logger.info(f"  ✅ Success: {summary['success']} (Skipped {summary['skipped']} from archive)")
    logger.info(f"  ❌ Failed: {summary['failed']}")
    logger.info(f"  ⚠️  Error: {summary['error']}")
    logger.info(f"  💸 LLM Cost: ${total_batch_cost:.4f}")
    logger.info(f"  Results saved to: {output_path}")
    logger.info(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="LogicGap: Automated Smart Contract Vulnerability PoC Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single target
  python main.py --target data/targets/1-aibabydoge.pdf.json

  # Batch processing
  python main.py --batch data/targets/

  # With specific finding ID and output directory
  python main.py --target data/targets/sample.json --finding-id 10 --output results/experiment1/

  # Custom severity filter
  python main.py --batch data/targets/ --severity high medium critical
        """,
    )

    # Input modes (mutually exclusive)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--target", type=str, help="Path to a single .pdf.json target file")
    group.add_argument("--batch", type=str, help="Path to directory containing .pdf.json files")

    # Options
    parser.add_argument("--output", "-o", type=str, default=str(DEFAULT_OUTPUT_DIR),
                        help=f"Output directory for results (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--finding-id", type=int, default=None,
                        help="Specific finding ID to process (single target mode only)")
    parser.add_argument("--severity", nargs="+", default=["high", "medium"],
                        help="Severity levels to process (default: high medium)")
    parser.add_argument("--max-attempts", type=int, default=None,
                        help=f"Max agent attempts per finding (default: {MAX_ATTEMPTS})")
    parser.add_argument("--block-number", type=int, default=None,
                        help="Fork block number (default: latest)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.target:
        run_single_target(
            target_path=args.target,
            output_dir=args.output,
            finding_id=args.finding_id,
            severity_filter=args.severity,
            max_attempts=args.max_attempts,
            block_number=args.block_number,
        )
    elif args.batch:
        run_batch(
            batch_dir=args.batch,
            output_dir=args.output,
            severity_filter=args.severity,
            max_attempts=args.max_attempts,
            block_number=args.block_number,
        )


if __name__ == "__main__":
    main()
