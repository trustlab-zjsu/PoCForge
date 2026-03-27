import json
from pathlib import Path
import argparse
import sys
from collections import defaultdict

def evaluate_results(results_dir: str):
    base_dir = Path(results_dir)
    if not base_dir.exists():
        print(f"Error: Directory {results_dir} does not exist.")
        sys.exit(1)

    # Metrics accumulators
    total_findings = 0
    verification_passed = 0
    compiled_successfully = 0
    evm_execution_reached = 0
    
    total_tokens = 0
    total_cost = 0.0
    total_time = 0.0
    total_attempts = 0

    # Look for all attempt_history.json files (New Format)
    history_files = list(base_dir.rglob("attempt_history.json"))
    
    # Also look for the old format to support `success_archive` (traces/attempt_X.json)
    legacy_files = list(base_dir.rglob("traces/attempt_*.json"))
    
    # We will group files by finding directory
    finding_dirs = set()
    for f in history_files + legacy_files:
        finding_dirs.add(f.parent if f.name == "attempt_history.json" else f.parent.parent)

    if not finding_dirs:
        print(f"No result traces found in {results_dir}")
        sys.exit(0)

    for finding_dir in finding_dirs:
        total_findings += 1
        attempts = []
        
        # Try loading new format
        history_file = finding_dir / "attempt_history.json"
        if history_file.exists():
            with open(history_file, 'r', encoding='utf-8') as f:
                attempts = json.load(f)
        else:
            # Fallback to old format
            trace_dir = finding_dir / "traces"
            if trace_dir.exists():
                for trace_file in sorted(trace_dir.glob("attempt_*.json")):
                    with open(trace_file, 'r', encoding='utf-8') as f:
                        attempts.append(json.load(f))
                        
        if not attempts:
            continue

        finding_compiled = False
        finding_executed = False
        finding_passed = False
        
        for attempt in attempts:
            total_attempts += 1
            total_tokens += attempt.get('prompt_tokens', 0) + attempt.get('completion_tokens', 0)
            total_cost += attempt.get('total_cost', 0.0)
            total_time += attempt.get('duration_seconds', 0.0)
            
            err = attempt.get('error') or {}
            exit_code = attempt.get('exit_code', -1)
            
            if err:
                err_type = err.get('error_type', '')
                if err_type != 'COMPILE_ERROR':
                    finding_compiled = True
                    finding_executed = True
            elif exit_code == 0:
                finding_compiled = True
                finding_executed = True
                finding_passed = True
            
        if finding_compiled:
            compiled_successfully += 1
        if finding_executed:
            evm_execution_reached += 1
        if finding_passed:
            verification_passed += 1

    # Print Summary
    print("\n" + "="*50)
    print("📊 LOGICGAP EVALUATION REPORT 📊")
    print("="*50)
    print(f"Total Targets Evaluated: {total_findings}")
    print(f"Average Attempts per Target: {total_attempts / total_findings if total_findings else 0:.1f}")
    print("-" * 50)
    
    # Paper Metrics
    comp_rate = (compiled_successfully / total_findings * 100) if total_findings else 0
    exec_rate = (evm_execution_reached / total_findings * 100) if total_findings else 0
    pass_rate = (verification_passed / total_findings * 100) if total_findings else 0
    
    print(f"1. Compilation Success Rate (CSR): {comp_rate:.1f}% ({compiled_successfully}/{total_findings})")
    print(f"   (PoC compiled successfully at least once)")
    print(f"2. Execution Reach Rate (ERR):     {exec_rate:.1f}% ({evm_execution_reached}/{total_findings})")
    print(f"   (PoC successfully executed on EVM Fork)")
    print(f"3. Verification Pass Rate (VPR):   {pass_rate:.1f}% ({verification_passed}/{total_findings})")
    print(f"   (PoC passed logic/economic assert verification)")
    print("-" * 50)
    
    # Resource Metrics
    print(f"Total LLM Tokens Used: {total_tokens:,}")
    print(f"Total LLM API Cost:    ${total_cost:.4f}")
    if verification_passed > 0:
        print(f"Avg Cost per Success:  ${total_cost / verification_passed:.4f}")
    print(f"Total Compute Time:    {total_time/60:.1f} minutes")
    print("="*50 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate LogicGap Batch Results")
    parser.add_argument("results_dir", help="Path to the results directory (e.g., results/run1)")
    args = parser.parse_args()
    evaluate_results(args.results_dir)
