"""
Compatibility package for the artifact layout.

The implementation lives directly under code/, while modules import core.*.
Extending this package search path keeps those imports working without
duplicating files.
"""

from pathlib import Path

_CODE_DIR = Path(__file__).resolve().parent.parent
if _CODE_DIR.exists():
    __path__.append(str(_CODE_DIR))
