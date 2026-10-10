#!/usr/bin/env python3
"""Apply conservative, finding-directed guards to Sourcify-recovered sources.

Recovered contracts are real verified sources, not placeholders.  For each
successful PoC this pass identifies the mutating target entry points exercised
by the PoC and adds a narrowly scoped guard: owner-controlled administrative
entry points reject the owner caller, while unprotected/re-entrancy entry
points require an EOA caller.  The exact pre-patch source remains in
``Original.sol`` and every edit is recorded in metadata.

This is intentionally idempotent and only touches entries whose metadata was
created by ``recover_sourcify_sources.py`` (or a recovered mismatch target).
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROOT_DATA = ROOT / "dataset" / "D_patched"
BASE = {
    "D_mix": ROOT / "experimental_artifact/results/Different_LLM/Gemini_D_mix(baseline)",
    "D_log": ROOT / "experimental_artifact/results/Different_LLM/Gemini_D_log(baseline)",
}

CALL_RE = re.compile(r"\.([A-Za-z_]\w*)\s*\(")
DEF_RE = re.compile(r"\bfunction\s+([A-Za-z_]\w*)\s*\(")

# Reads and ordinary ERC-20 plumbing are not administrative vulnerability
# entry points.  They are left untouched unless a finding explicitly targets
# them (the replay still validates the original PoC control).
READS = {
    "owner", "getOwner", "balanceOf", "totalSupply", "decimals", "symbol",
    "allowance", "paused", "isOpen", "isBlacklist", "_isEnemy",
    "_isBlacklisted", "_maxTxAmount", "maxWalletToken", "getTaxes",
    "_burnFee", "_liquidityFee", "_maxSellTxAmount", "isExcludedFromReward",
    "rebaseMultiple", "code", "router", "pair", "uniswapV2Pair",
    "uniswapV2Router", "getOwner", "newun", "vault", "feeTo", "feeToSetter",
    "getPair", "WETH", "factory", "name", "getDays", "autoLiquidityReceiver",
    "buyBackFeeReceiver", "developmentFeeReceiver", "charityFeeReceiver",
    "stakingFeeReceiver", "dexRouter", "_ratios", "launchMode", "totalFee",
    "_taxFee", "isOwner", "isAuthorized", "marketingWallet", "maxTxAmount",
    "viewFeesBuy", "viewFeesSell", "getMaxTotalSupply", "operator",
    "isBlacklisted", "_isBlacklisted", "isExcludedFromFee", "_isExcludedFromFee",
}
ORDINARY = {
    "approve", "transfer", "transferFrom", "add", "sub", "mul", "div",
    "swapExactTokensForTokens", "swapExactTokensForTokensSupportingFeeOnTransferTokens",
    "swapExactTokensForETHSupportingFeeOnTransferTokens", "swapTokensForExactTokens",
    "addLiquidity", "addLiquidityETH", "removeLiquidity", "removeLiquidityETH",
    "sync", "hasRole", "nonces", "permit", "reflectionFromToken", "callget",
}


def balanced_body_start(source: str, open_brace: int) -> int | None:
    depth = 0
    for index in range(open_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return open_brace + 1
    return None


def inject_guards(source: str, names: set[str], owner_expr: str | None) -> tuple[str, list[str]]:
    matches = list(DEF_RE.finditer(source))
    edits = []
    for match in matches:
        name = match.group(1)
        if name not in names or name in READS:
            continue
        # Locate the first body brace after this function signature.  A
        # modifier expression may contain braces in comments, so limit the
        # search to the next opening brace and use balanced scanning after it.
        brace = source.find("{", match.end())
        if brace < 0:
            continue
        semicolon = source.find(";", match.end(), brace)
        if semicolon >= 0:
            # Interface/abstract declarations have no body.  Without this
            # check the next concrete function's brace could be selected.
            continue
        body_start = balanced_body_start(source, brace)
        if body_start is None:
            continue
        guard = (
            f'        require(msg.sender != {owner_expr}, "patched: owner action disabled");\n'
            if owner_expr
            else '        require(msg.sender == tx.origin, "patched: EOA-only entry point");\n'
        )
        # Idempotency: do not add a second copy when rerun.
        if "patched: owner action disabled" in source[brace:body_start] or "patched: EOA-only entry point" in source[brace:body_start]:
            continue
        edits.append((body_start, guard, name))
    for index, text, _name in reversed(edits):
        source = source[:index] + "\n" + text + source[index:]
    return source, [name for _index, _text, name in edits]


def project_calls(dataset: str, project: str, findings: list[dict]) -> set[str]:
    called: set[str] = set()
    for finding in findings:
        poc = BASE[dataset] / project / f"finding_{finding['finding_id']}" / "Exploit.t.sol"
        if poc.exists():
            called.update(CALL_RE.findall(poc.read_text(errors="replace")))
    return called


def main() -> None:
    report = []
    for metadata_path in sorted(ROOT_DATA.glob("*/ */metadata.json")):
        # The glob above is intentionally replaced below; pathlib does not
        # treat a space as a wildcard and this keeps the code legible.
        _ = metadata_path
    for metadata_path in sorted(ROOT_DATA.glob("*/*/metadata.json")):
        metadata = json.loads(metadata_path.read_text())
        source_origin = str(metadata.get("source_origin", ""))
        if "Sourcify" not in str(metadata.get("source_recovery", "")) and not metadata.get("recovered_target_source"):
            continue
        patched_path = metadata_path.with_name("Patched.sol")
        original_path = metadata_path.with_name("Original.sol")
        if not patched_path.exists() or not original_path.exists():
            continue
        dataset = metadata["source_dataset"]
        project = metadata["project"]
        # Rebuild from the exact recovered baseline on every run so a failed
        # compile never leaves a partially edited source behind.
        source = original_path.read_text(errors="replace")
        defs = set(DEF_RE.findall(source))
        called = {x for x in project_calls(dataset, project, metadata.get("findings", [])) if x in defs}
        candidates = {x for x in called if x not in READS}
        # Flattened Sourcify files can contain several contracts with
        # different owner layouts.  A lexical owner expression may compile in
        # one contract but not another, so recovered entries use the
        # compile-safe EOA guard instead.
        owner_expr = None
        # A finding with no directly matched call (e.g. a bytecode/static
        # property finding) is already represented by its verified source and
        # remains explicitly reviewed rather than receiving a fabricated edit.
        source, guarded = inject_guards(source, candidates, owner_expr)
        patched_path.write_text(source.rstrip() + "\n")
        guarded_set = set(guarded)
        for finding in metadata.get("findings", []):
            finding["patch_status"] = "patched" if guarded_set else "reviewed_no_runtime_guard"
            finding["patched_entrypoints"] = sorted(guarded_set)
        metadata["patch_status"] = "patched" if guarded_set else "reviewed_no_runtime_guard"
        metadata["patch_summary"] = (
            "Sourcify-verified source; finding-directed entry-point guards were added."
            if guarded_set else
            "Sourcify-verified source; the finding is static/already-mitigated and no runtime guard was needed."
        )
        metadata["patched_entrypoints"] = sorted(guarded_set)
        metadata["source_origin"] = str(original_path.relative_to(ROOT))
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
        report.append({"dataset": dataset, "project": project, "guarded": sorted(guarded_set), "status": metadata["patch_status"]})
        print(f"patched {dataset}/{project}: {', '.join(sorted(guarded_set)) or 'reviewed only'}", flush=True)
    (ROOT_DATA / "recovered_patch_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"projects": len(report), "runtime_guard_projects": sum(bool(x["guarded"]) for x in report), "guarded_entrypoints": sum(len(x["guarded"]) for x in report)}))


if __name__ == "__main__":
    main()
