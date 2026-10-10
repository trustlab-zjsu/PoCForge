#!/usr/bin/env python3
"""Replay only projects changed by the fail-closed third patch pass."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPLAY = ROOT / "code/tools/replay_patched_pocs.py"
PROJECTS = [
    ("D_mix", "02_Smart_Contract_Audit_TOUCH"),
    ("D_mix", "6-solar"),
    ("D_mix", "NFT_Marvel_Fan_Token_Full_Smart_Contract_Security_Audit"),
    ("D_mix", "Soken-Sapphire_Dao"),
    ("D_mix", "income"),
    ("D_log", "1-luffy"),
    ("D_log", "2022-10-shimacapital-ondo-securityreview"),
    ("D_log", "Big League Smart Contract Audit Report - QuillAudits"),
    ("D_log", "Gator"),
    ("D_log", "HELL-Audit-by-BlockSAFU"),
    ("D_log", "MiniDOGE Smart Contract Audit Report - QuillAudits"),
    ("D_log", "MiniDOGE_Smart_Contract_Audit_Report_-_QuillAudits"),
    ("D_log", "SlowMist Audit Report - Coin98 Dollar (CUSD)_en-us"),
]


def main() -> None:
    rows = []
    for index, (dataset, project) in enumerate(PROJECTS, 1):
        env = os.environ.copy()
        env["REPLAY_DATASET"] = dataset
        env["REPLAY_PROJECT"] = project
        env.setdefault("REPLAY_BATCH_TIMEOUT", "300")
        print(f"[{index}/{len(PROJECTS)}] replay {dataset}/{project}", flush=True)
        subprocess.run(["python3", str(REPLAY)], cwd=ROOT, env=env, check=True)
        current_path = ROOT / "experimental_artifact/results/patched_poc_replay/results.json"
        current = json.loads(current_path.read_text())
        rows.extend(current)
        print(f"  captured {len(current)} finding(s)", flush=True)
    output = ROOT / "experimental_artifact/results/patched_poc_replay/third_pass_results.json"
    output.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} third-pass rows to {output}")


if __name__ == "__main__":
    main()
