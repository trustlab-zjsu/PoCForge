#!/usr/bin/env python3
"""Merge a focused replay run into a previously completed full run."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: merge_replay_results.py FULL CURRENT OUTPUT")
    full_path, current_path, output_path = map(Path, sys.argv[1:])
    full = json.loads(full_path.read_text())
    current = json.loads(current_path.read_text())
    replacements = {
        (r["dataset"], r["project"], r["finding_id"]): r for r in current
    }
    merged = []
    seen = set()
    for row in full:
        key = (row["dataset"], row["project"], row["finding_id"])
        merged.append(replacements.get(key, row))
        seen.add(key)
    for key, row in replacements.items():
        if key not in seen:
            merged.append(row)
    merged.sort(key=lambda r: (r["dataset"], r["project"], r["finding_id"]))
    output_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")
    print(f"merged {len(current)} focused records into {len(merged)} full records")


if __name__ == "__main__":
    main()
