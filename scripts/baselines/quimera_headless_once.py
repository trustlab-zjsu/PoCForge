#!/usr/bin/env python3
"""
Run Quimera once in headless mode (without TUI).

This wrapper directly invokes Quimera's MainTaskController.main() so it can be
automated by benchmark scripts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a single Quimera task without launching TUI."
    )
    parser.add_argument("--quimera-root", default="/Users/carl/quimera")
    parser.add_argument("--target", required=True, help="Contract address or local path.")
    parser.add_argument(
        "--chain",
        default="mainnet",
        help="Chain for on-chain target (mainnet/bsc/arbi/eth).",
    )
    parser.add_argument("--block-number", required=True, help="Fork block number.")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--working-dir", required=True)
    parser.add_argument("--contract", default="")
    parser.add_argument("--valuable-token", default="weth")
    parser.add_argument("--thinking-budget", type=int, default=0)
    parser.add_argument("--attachment", default="")
    return parser.parse_args()


def _normalize_chain(chain: str) -> str:
    chain = chain.lower().strip()
    if chain == "eth":
        return "mainnet"
    return chain


def _build_quimera_argv(args: argparse.Namespace) -> list[str]:
    target = args.target
    chain = _normalize_chain(args.chain)
    if target.startswith("0x") and ":" not in target:
        target = f"{chain}:{target}"

    argv = [
        "quimera",
        target,
        "--block-number",
        str(args.block_number),
        "--model",
        args.model,
        "--iterations",
        str(args.iterations),
        "--working-dir",
        str(args.working_dir),
        "--valuable-token",
        args.valuable_token,
        "--thinking-budget",
        str(args.thinking_budget),
    ]
    if args.contract:
        argv += ["--contract", args.contract]
    if args.attachment:
        argv += ["--attachment", args.attachment]
    return argv


def main() -> int:
    args = parse_args()
    quimera_root = Path(args.quimera_root).resolve()
    if not quimera_root.exists():
        print(f"ERROR: quimera root not found: {quimera_root}")
        return 2

    sys.path.insert(0, str(quimera_root))
    try:
        from quimera.__main__ import MainTaskController
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: failed to import Quimera: {e}")
        return 2

    Path(args.working_dir).mkdir(parents=True, exist_ok=True)
    sys.argv = _build_quimera_argv(args)

    controller = MainTaskController()
    try:
        controller.main()
        return 0
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 0
        return code
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: headless run failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
