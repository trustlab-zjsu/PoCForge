#!/usr/bin/env python3
"""Fill missing chain hints for generated patched metadata."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

for path in sorted((ROOT / "dataset" / "D_patched").glob("*/*/metadata.json")):
    data = json.loads(path.read_text())
    if data.get("chain"):
        continue
    # All currently blank recovered report addresses are BSC token deployments.
    # Mismatch targets carry an explicit recovered_chain_id and are preserved.
    if data.get("recovered_chain_id"):
        data["chain"] = "eth" if str(data["recovered_chain_id"]) == "1" else "bsc"
    else:
        data["chain"] = "bsc"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(path.relative_to(ROOT), data["chain"])
