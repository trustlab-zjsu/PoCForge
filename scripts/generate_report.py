import json
import csv
import glob
from pathlib import Path
from collections import defaultdict

def create_report(results_dir: str, output_csv: str, output_md: str):
    base_path = Path(results_dir)
    result_files = list(base_path.glob("**/*/result.json"))
    
    table_data = []
    
    for res_file in result_files:
        try:
            with open(res_file, "r") as f:
                data = json.load(f)
            
            project_id = data.get("project_id", "Unknown")
            # Strip verbose prefixes for a cleaner report
            prefixes_to_strip = [
                "Accounting_and_State_Desync_",
                "Math_and_Integer_Issues_",
                "Price_Oracle_and_Flashloan_",
                "Reentrancy_"
            ]
            for p in prefixes_to_strip:
                if project_id.startswith(p):
                    project_id = project_id[len(p):]
                    break
            if project_id.endswith(".pdf"):
                project_id = project_id[:-4]
                    
            vt = data.get("violation_target") or {}
            vuln_cat = f"{vt.get('vulnerability_type', 'Unknown')} ({vt.get('violation_category', 'Unknown')})"
            
            attempts = data.get("attempts") or []
            total_attempts = data.get("total_attempts", 0)
            status = data.get("status") or "ERROR"
            
            # Analyze attempts to find out exactly where it failed/succeeded
            compiled = False
            revert_free = False
            oracle_passed = False
            fail_reason = "-"
            
            total_tokens = 0
            total_cost = 0.0
            total_time = 0.0
            
            for att in attempts:
                total_tokens += att.get("prompt_tokens", 0) + att.get("completion_tokens", 0)
                total_cost += att.get("total_cost", 0.0)
                total_time += att.get("duration_seconds", 0.0)
                
                err = att.get("error")
                if err is None:
                    # No error means test passed
                    compiled = True
                    revert_free = True
                    oracle_passed = True
                else:
                    err_type = err.get("error_type")
                    if err_type == "COMPILE_ERROR":
                        pass # Still false
                    elif err_type == "EVM_REVERT":
                        compiled = True
                    elif err_type == "ASSERTION_FAILED":
                        compiled = True
                        revert_free = True
            
            if status == "FAILED" and attempts:
                last_err = attempts[-1].get("error", {})
                fail_reason = f"{last_err.get('error_type', 'Unknown')}: {last_err.get('reason', '')[:50]}..."
                
            status_icon = "🟢 SUCCESS" if status == "SUCCESS" else "🔴 FAILED"
            
            table_data.append({
                "Project": project_id,
                "Vuln Category": vuln_cat,
                "Attempts": f"{len(attempts)} / 3",
                "Compiled?": "✅ Yes" if compiled else "❌ No",
                "Revert Free?": "✅ Yes" if revert_free else "❌ No",
                "Oracle Passed?": "✅ Yes" if oracle_passed else "❌ No",
                "Tokens Used": total_tokens,
                "Est. Cost ($)": f"${total_cost:.4f}",
                "Time (s)": f"{total_time:.1f}",
                "Final Status": status_icon,
                "Fail Reason": fail_reason
            })
            
        except Exception as e:
            print(f"Error parsing {res_file}: {e}")
            
    # Sort by project
    table_data.sort(key=lambda x: x["Project"])

    total_findings = len(table_data)
    compiled_pass = sum(1 for row in table_data if row["Compiled?"].startswith("✅"))
    evm_pass = sum(1 for row in table_data if row["Revert Free?"].startswith("✅"))
    verify_pass = sum(1 for row in table_data if row["Oracle Passed?"].startswith("✅"))

    def pct(n: int, d: int) -> str:
        return f"{(n / d * 100):.1f}%" if d else "0.0%"

    csr = f"{compiled_pass}/{total_findings} = {pct(compiled_pass, total_findings)}"
    err = f"{evm_pass}/{total_findings} = {pct(evm_pass, total_findings)}"
    vpr = f"{verify_pass}/{total_findings} = {pct(verify_pass, total_findings)}"

    keys = [
        "Project",
        "Vuln Category",
        "Attempts",
        "Compiled?",
        "Revert Free?",
        "Oracle Passed?",
        "Tokens Used",
        "Est. Cost ($)",
        "Time (s)",
        "Final Status",
        "Fail Reason",
    ]
    
    # Write CSV
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(table_data)
        writer.writerow({k: "" for k in keys} | {"Project": "--- SUMMARY ---"})
        writer.writerow({k: "" for k in keys} | {"Project": "CSR (Compilation Success Rate)", "Vuln Category": csr})
        writer.writerow({k: "" for k in keys} | {"Project": "ERR (EVM Interaction Pass Rate)", "Vuln Category": err})
        writer.writerow({k: "" for k in keys} | {"Project": "VPR (Oracle Verification Pass Rate)", "Vuln Category": vpr})
    print(f"CSV generated at {output_csv}")
        
    # Write Markdown
    with open(output_md, "w", encoding="utf-8") as f:
        f.write("| Project | Vuln Category | Attempts | Compiled? | Revert Free? | Oracle Passed? | Tokens Used | Cost | Time (s) | Final Status | Fail Reason |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for row in table_data:
            f.write(f"| {row['Project']} | {row['Vuln Category']} | {row['Attempts']} | {row['Compiled?']} | {row['Revert Free?']} | {row['Oracle Passed?']} | {row['Tokens Used']} | {row['Est. Cost ($)']} | {row['Time (s)']} | {row['Final Status']} | {row['Fail Reason']} |\n")
        f.write("| --- SUMMARY --- |  |  |  |  |  |  |  |  |  |  |\n")
        f.write(f"| CSR (Compilation Success Rate) | {csr} |  |  |  |  |  |  |  |  |  |\n")
        f.write(f"| ERR (EVM Interaction Pass Rate) | {err} |  |  |  |  |  |  |  |  |  |\n")
        f.write(f"| VPR (Oracle Verification Pass Rate) | {vpr} |  |  |  |  |  |  |  |  |  |\n")
    print(f"Markdown generated at {output_md}")

if __name__ == "__main__":
    import sys
    import os
    res_dir = sys.argv[1] if len(sys.argv) > 1 else "results/run_samples_batch"
    
    # Deriving output name based on the result directory name
    dir_name = os.path.basename(res_dir.rstrip('/\\'))
    if not dir_name:
        dir_name = "evaluation"
        
    create_report(res_dir, f"{dir_name}_metrics.csv", f"{dir_name}_metrics.md")
