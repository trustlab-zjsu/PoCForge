#!/usr/bin/env python3
"""Finalize patch metadata after manual review and compilation."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "dataset" / "D_patched"
SOURCE_RE = re.compile(
    r"# Code to review\s*```(?:solidity)?\s*\n(.*?)\n```", re.DOTALL
)

SOURCE_MISMATCH = {
    ("D_mix", "Hacken-FOTA"),
    ("D_log", "2022-10-shimacapital-ondo-securityreview"),
    ("D_log", "PeckShield-Arche"),
    ("D_log", "SlowMist Audit Report - InsurAce_en-us"),
    ("D_log", "SlowMist Audit Report - Shield_en-us"),
}

ALREADY_MITIGATED = {
    ("D_mix", "02_Smart_Contract_Audit_TOUCH"),
    ("D_mix", "6-solar"),
}

PATCH_SUMMARIES = {
    "1-kln": "Disabled post-deployment owner minting.",
    "2-babyape": "Kept constructor issuance internal and disabled post-deployment minting.",
    "2-mojo": "Validated pair bytecode, tokens, and factory registration before accepting a pair.",
    "2-srt": "Disabled post-deployment owner minting.",
    "3-mdoge": "Disabled the privileged token-claim drain path.",
    "Axis_Token_Smart_Contract_Audit_Report_-_QuillAudits": "Disabled post-deployment owner minting.",
    "Binamon_Energy_Smart_Contract_Audit_Report_-_QuillAudits": "Added zero-reset approval semantics, one-time staking setup, and disabled direct minting.",
    "CatVerse_0x89031AaFA457245469E9641387aa94BFB51cB964": "Locked blacklist and tax administration once trading/liquidity is live.",
    "Catboy_0x39C3F75B837EAE0d6d0eA87425Ac99bD646a7B1E": "Disabled the owner native-balance sweep.",
    "Crucifearous_Finance_Full_Smart_Contract_Security_Audit": "Made mint/burn update reflected and token supply accounting consistently.",
    "DogBoss_0x86C86FfDC0482D8DD918FC657c3FC51C4a1E3e5C": "Disabled post-deployment owner minting.",
    "FoundationToken_Comprehensive_Smart_Contract_Audit": "Checked low-level call success and locked privileged withdrawals/configuration after launch.",
    "HubGame_0x46bCBBB0D888dF90Eda86c9CA159C7727a8731D5": "Disabled arbitrary admin balance insertion and restricted game initialization to the owner.",
    "ImperialFinance_0x889e8cD93Be2FDF4CCc649Ba9D51e61CFD8C930f": "Disabled the owner-wide asset withdrawal path.",
    "MetaApes_0xd764457Fadd15B52089BeE2b3c38964C7dFf0B70": "Locked fee recipients after launch, bound airdrops to the caller, and disabled arbitrary approvals/sweeps.",
    "NFT_Marvel_Fan_Token_Full_Smart_Contract_Security_Audit": "Updated the moved account's index when removing an excluded reward account.",
    "OukaInu_0x4A33D3ea4B30228C363222746939562FbAba2f01": "Disabled privileged balance drains and locked fee receivers after trading starts.",
    "Powabit_0x5FDa925294F9e5B31b7c0e81Bad6BAD5b5E792eE": "Disabled post-deployment owner minting.",
    "ShibaZilla_AuditReport_InterFi": "Disabled the privileged native-balance sweep.",
    "Shibtoro_0x8AeB7C2D4758eb51080493E2Cb290d62510659C7": "Locked blacklist and tax controls after trading starts.",
    "Soken-Sapphire_Dao": "Made the EIP-712 domain separator chain-aware to prevent cross-chain replay.",
    "ds": "Disabled post-deployment owner minting.",
    "memefarm": "Disabled the hidden mint path in the router-change function.",
    "mybricks": "Disabled operator minting and the owner path that forcibly transferred holder balances.",
    "1-luffy": "Debited and transferred the liquidity-fee component so transfer accounting balances.",
    "1-lunainu": "Disabled privileged token/native-balance drains and the owner burn-from-contract path.",
    "1-sgrok": "Restricted manual swapping and disabled the privileged native-balance drain.",
    "1-shf": "Required the declared sender to authorize batch transfers.",
    "1-vit": "Capped configurable buy and sell fees at 25 percent.",
    "2-babydoge2": "Made the marketing wallet immutable after deployment.",
    "2-ght": "Disabled the privileged supply-rebase path.",
    "2-marvin": "Capped fees, locked fee wallets after launch, and prohibited owner-enabled LP burning.",
    "3-ccg": "Added five-percent slippage bounds to automatic liquidity provision.",
    "3-honey": "Removed precision-losing intermediate fee allocation and validated its denominator.",
    "AnySniperEscrow_0x89d7c52b999DE0f2D862eD944203BFA0526AE973": "Added reentrancy guards and exact msg.value accounting before external sends.",
    "Big League Smart Contract Audit Report - QuillAudits": "Always decremented transferFrom allowance, including max-uint allowances.",
    "Engos_0x5548498f6Ae923f590cD1A1cec8D39E1f9363104": "Disabled the privileged native-balance withdrawal.",
    "HELL-Audit-by-BlockSAFU": "Moved allowance consumption before the externally interacting transfer path.",
    "Honey": "Made mint/burn update reflected and token supply accounting consistently.",
    "LoveDoge": "Disabled owner overrides of reward-pool accounting while retaining internal automatic updates.",
    "MiniDOGE Smart Contract Audit Report - QuillAudits": "Applied checks-effects-interactions, blocked transfer reentry during swaps, capped global/per-address fees, and made the router and drain destinations immutable.",
    "Nomos_0xF7B7Db914e8Fd226f5648CebDc7464D1aC4f6AFc": "Applied checks-effects-interactions, blocked transfer reentry during swaps, capped fees, and disabled mutable drain destinations/withdrawals.",
    "PlentyCoin Smart Contract Audit Report - QuillAudits": "Persisted _lockedAmount additions/subtractions across every lock and unlock path.",
    "SlowMist Audit Report - Coin98 Dollar (CUSD)_en-us": "Added a deployment-configured immutable mint cap and disabled owner NFT extraction.",
    "SmartContract_Audit_Solidproof_BGLToken": "Disabled the owner native-balance withdrawal path.",
    "SmartContract_Audit_Solidproof_Jizzjet": "Applied checks-effects-interactions, bounded fees, blocked swap-time reentry, made router/receiver immutable, and transferred only fresh swap proceeds.",
}

STATUS_SUMMARIES = {
    ("D_mix", "02_Smart_Contract_Audit_TOUCH"): "The archived source already enforces zero-reset approvals and SafeMath allowance updates.",
    ("D_mix", "6-solar"): "The archived source already caps minting at the declared maximum supply.",
    ("D_mix", "Hacken-FOTA"): "PoC targets a proxy-upgrade surface, but the archived prompt source is an unrelated SeedSale contract.",
    ("D_log", "2022-10-shimacapital-ondo-securityreview"): "PoC targets upgradeability, but the archived prompt source is the unrelated USDT token.",
    ("D_log", "PeckShield-Arche"): "PoC targets D_Swap, but the archived prompt source is an unrelated FFI ERC-20.",
    ("D_log", "SlowMist Audit Report - InsurAce_en-us"): "PoC targets StakersPool, but the archived prompt source is UniswapV2Router02.",
    ("D_log", "SlowMist Audit Report - Shield_en-us"): "PoCs target a DDS oracle, but the archived prompt source is WBTC.",
}

FINDING_OVERRIDES = {
    ("D_log", "SmartContract_Audit_Solidproof_Jizzjet", 5): "not_present_in_source",
    ("D_log", "SmartContract_Audit_Solidproof_Jizzjet", 6): "not_present_in_source",
}


def normalized_prompt_source(prompt_path: Path) -> str:
    match = SOURCE_RE.search(prompt_path.read_text(errors="replace"))
    if not match:
        raise ValueError(f"no source block in {prompt_path}")
    return re.sub(r":\s+=", ":=", match.group(1)).rstrip() + "\n"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def main() -> None:
    manifest = []
    counts: Counter[str] = Counter()

    for metadata_path in sorted(OUTPUT.glob("*/*/metadata.json")):
        metadata = json.loads(metadata_path.read_text())
        dataset = metadata["source_dataset"]
        project = metadata["project"]
        key = (dataset, project)
        contract_path = metadata_path.with_name("Patched.sol")

        original_source = normalized_prompt_source(ROOT / metadata["source_origin"])
        patched_source = contract_path.read_text()

        if key in SOURCE_MISMATCH:
            status = "source_mismatch"
            validation = {
                "compile_status": "skipped",
                "reason": "PoC target and archived source do not match",
                "poc_regression": "not_run",
            }
        elif key in ALREADY_MITIGATED:
            status = "already_mitigated"
            validation = {
                "compile_status": "passed",
                "compiler": (
                    "solc 0.4.26"
                    if project == "02_Smart_Contract_Audit_TOUCH"
                    else "forge build (pragma-selected solc)"
                ),
                "poc_regression": "not_run",
            }
        else:
            status = "patched"
            validation = {
                "compile_status": "passed",
                "compiler": "forge build (pragma-selected solc)",
                "poc_regression": "not_run",
            }

        metadata["patch_status"] = status
        metadata["patch_summary"] = STATUS_SUMMARIES.get(
            key, PATCH_SUMMARIES.get(project)
        )
        if metadata["patch_summary"] is None:
            raise KeyError(f"missing patch summary for {key}")
        metadata["validation"] = validation
        metadata["original_source_sha256"] = digest(original_source)
        metadata["patched_source_sha256"] = digest(patched_source)

        for finding in metadata["findings"]:
            finding["patch_status"] = FINDING_OVERRIDES.get(
                (dataset, project, finding["finding_id"]), status
            )

        metadata_path.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n"
        )
        counts[status] += 1
        manifest.append(
            {
                "source_dataset": dataset,
                "project": project,
                "target_address": metadata["target_address"],
                "contract": str(contract_path.relative_to(ROOT)),
                "metadata": str(metadata_path.relative_to(ROOT)),
                "patch_status": status,
                "compile_status": validation["compile_status"],
                "finding_ids": [item["finding_id"] for item in metadata["findings"]],
            }
        )

    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    print(f"Finalized {len(manifest)} contracts: {dict(sorted(counts.items()))}")


if __name__ == "__main__":
    main()
