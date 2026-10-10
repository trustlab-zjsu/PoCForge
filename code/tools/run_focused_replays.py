#!/usr/bin/env python3
"""Run the projects whose patched source changed in the second pass."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPLAY = ROOT / "code/tools/replay_patched_pocs.py"
PROJECTS = [
    ("D_mix", "2-babyape"),
    ("D_mix", "2-fit"),
    ("D_mix", "3-mdoge"),
    ("D_mix", "Axis_Token_Smart_Contract_Audit_Report_-_QuillAudits"),
    ("D_mix", "Binamon_Energy_Smart_Contract_Audit_Report_-_QuillAudits"),
    ("D_mix", "Soken-Sapphire_Dao"),
    ("D_mix", "ds"),
    ("D_mix", "memefarm"),
    ("D_mix", "milesinu"),
    ("D_mix", "tea-token"),
    ("D_log", "$xenox"),
    ("D_log", "1-lunainu"),
    ("D_log", "1-shf"),
    ("D_log", "1-vit"),
    ("D_log", "1shiba"),
    ("D_log", "2-ght"),
    ("D_log", "Big League Smart Contract Audit Report - QuillAudits"),
    ("D_log", "LoveDoge"),
    ("D_log", "MiniDOGE_Smart_Contract_Audit_Report_-_QuillAudits"),
    ("D_log", "PlentyCoin Smart Contract Audit Report - QuillAudits"),
]


def main() -> None:
    rows = []
    start = int(os.getenv("FOCUSED_SKIP", "0"))
    for dataset, project in PROJECTS[start:]:
        env = os.environ.copy()
        env["REPLAY_DATASET"] = dataset
        env["REPLAY_PROJECT"] = project
        env.setdefault("REPLAY_BATCH_TIMEOUT", "300")
        print(f"\n=== replay {dataset}/{project} ===", flush=True)
        subprocess.run(["python3", str(REPLAY)], cwd=ROOT, env=env, check=True)
        current = json.loads((ROOT / "experimental_artifact/results/patched_poc_replay/results.json").read_text())
        rows.extend(current)
        print(f"captured {len(current)} rows", flush=True)
    out = ROOT / "experimental_artifact/results/patched_poc_replay/focused_results.json"
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} focused rows to {out}")


if __name__ == "__main__":
    main()
