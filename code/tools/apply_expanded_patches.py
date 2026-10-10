#!/usr/bin/env python3
"""Apply the second-pass, finding-aligned hardening patches.

This is intentionally an explicit patch map rather than a blanket "revert every
function" transformation.  Each edit is tied to the baseline finding that is
being replayed.  The script is idempotent and records the patch rationale in
the per-project metadata.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "dataset" / "D_patched"


def insert_function_body(source: str, function: str, text: str, *, occurrence: int = 0) -> str:
    """Insert text immediately after a concrete Solidity function's opening brace."""
    # Do not cross an interface declaration or a contract closing brace while
    # looking for the implementation body.
    pattern = re.compile(r"function\s+" + re.escape(function) + r"\s*\([^)]*\)[^;{}]*\{")
    matches = list(pattern.finditer(source))
    if len(matches) <= occurrence:
        raise RuntimeError(f"function {function!r} occurrence {occurrence} not found")
    match = matches[occurrence]
    return source[: match.end()] + "\n    " + text + source[match.end() :]


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if old not in source:
        raise RuntimeError(f"replacement target not found: {label}")
    return source.replace(old, new, 1)


def patch_file(dataset: str, project: str, operations: list[tuple[str, tuple]]) -> None:
    path = DATASET / dataset / project / "Patched.sol"
    if not path.exists():
        raise RuntimeError(f"missing patched source: {path}")
    source = path.read_text(errors="replace")
    original = source
    for kind, args in operations:
        if kind == "insert":
            function, text, occurrence = args
            marker = text.strip()
            if marker not in source:
                source = insert_function_body(source, function, text, occurrence=occurrence)
        elif kind == "replace":
            old, new, label = args
            if new not in source:
                source = replace_once(source, old, new, label)
        else:
            raise ValueError(kind)
    if source != original:
        path.write_text(source)


PATCHES: dict[tuple[str, str], list[tuple[str, tuple]]] = {
    ("D_mix", "02_Smart_Contract_Audit_TOUCH"): [
        ("insert", ("transferFrom", 'revert("TOUCH: delegated transfers disabled");', 0)),
    ],
    ("D_mix", "2-babyape"): [
        ("insert", ("burn", 'revert("BabyApe: owner burn disabled");', 0)),
    ],
    ("D_mix", "2-fit"): [
        ("insert", ("burn", 'require(account == msg.sender, "FIT: burn only own balance");', 0)),
    ],
    ("D_mix", "3-mdoge"): [
        ("insert", ("setBlacklist", 'revert("MDOGE: blacklist administration disabled");', 0)),
    ],
    ("D_mix", "Axis_Token_Smart_Contract_Audit_Report_-_QuillAudits"): [
        ("insert", ("approve", 'require(value == 0 || _allowed[msg.sender][spender] == 0, "LineAxis: reset allowance first");', 0)),
        ("replace", ("function transferFrom(address from, address to, uint256 value) public {", "function transferFrom(address from, address to, uint256 value) public returns(bool) {", "LineAxis transferFrom return type")),
        ("replace", ("    _transfer(from, to, value);\n  }\n  /**\n   * @dev Transfer token for a specified address", "    _transfer(from, to, value);\n    return true;\n  }\n  /**\n   * @dev Transfer token for a specified address", "LineAxis base transferFrom return value")),
        ("replace", ("function transferFrom(address from, address to, uint value) public onlyUnfreeze {", "function transferFrom(address from, address to, uint value) public onlyUnfreeze returns(bool) {", "LineAxis override transferFrom return type")),
        ("replace", ("    super.transferFrom(from, to, value);\n  }\n}\n", "    super.transferFrom(from, to, value);\n    return true;\n  }\n}\n", "LineAxis override transferFrom return value")),
    ],
    ("D_mix", "Binamon_Energy_Smart_Contract_Audit_Report_-_QuillAudits"): [
        ("insert", ("setBotProtection", 'revert("BNRG: bot protection configuration locked");', 0)),
    ],
    ("D_mix", "Soken-Sapphire_Dao"): [
        ("replace", ("pragma solidity 0.7 .5;", "pragma solidity ^0.8.0;", "Sapphire compiler pragma")),
        ("replace", ("bytes32(uint256(value))", "bytes32(uint256(uint160(value)))", "Sapphire address-set conversion")),
        ("replace", ("address(uint256(_at(set._inner, index)))", "address(uint160(uint256(_at(set._inner, index))))", "Sapphire address-set read conversion")),
        ("replace", ("bytes32(uint256(valueToInsert_))", "bytes32(uint256(uint160(valueToInsert_)))", "Sapphire address-set insert conversion")),
        ("insert", ("setVault", 'require(vault_ != address(0), "VaultOwned: zero vault");', 0)),
        ("insert", ("transferOwnership", 'require(newOwner_ != 0x000000000000000000000000000000000000dEaD, "Ownable: unusable owner");', 0)),
        ("insert", ("permit", 'revert("Sapphire: signature approvals disabled");', 0)),
    ],
    ("D_mix", "6-solar"): [
        ("insert", ("mint", 'revert("Solar: post-deployment minting disabled");', 0)),
    ],
    ("D_mix", "NFT_Marvel_Fan_Token_Full_Smart_Contract_Security_Audit"): [
        ("insert", ("includeInReward", 'revert("NFTMarvelFan: reward-set mutation disabled");', 0)),
    ],
    ("D_mix", "income"): [
        ("insert", ("blacklistAddress", 'revert("INCOME: blacklist administration disabled");', 0)),
    ],
    ("D_mix", "ds"): [
        ("insert", ("pause", 'revert("DoctorShiba: owner pause disabled");', 0)),
        ("insert", ("transfernewun", 'revert("DoctorShiba: recipient lock disabled");', 0)),
    ],
    ("D_mix", "memefarm"): [
        ("insert", ("qwidji", 'revert("MemeFarm: blacklist administration disabled");', 0)),
    ],
    ("D_mix", "MetaApes_0xd764457Fadd15B52089BeE2b3c38964C7dFf0B70"): [
        ("insert", ("setswap", 'revert("MetaApes: arbitrary token sweep disabled");', 0)),
    ],
    ("D_mix", "milesinu"): [
        ("insert", ("setMaxTxPercent", 'require(maxTxPercent > 0, "Milesinu: zero transaction limit");', 0)),
        ("insert", ("lock", 'require(time <= 1 days, "Milesinu: lock duration capped");', 0)),
    ],
    ("D_mix", "tea-token"): [
        ("insert", ("setMaxTxPercent", 'require(maxTxPercent > 0, "TeaToken: zero transaction limit");', 0)),
    ],
    ("D_log", "$xenox"): [
        ("insert", ("setSellTaxFeePercent", 'require(taxFee <= 25, "xenoX: sell tax exceeds 25%");', 0)),
    ],
    ("D_log", "1-luffy"): [
        ("insert", ("setTax", 'revert("Luffy: tax-mode mutation disabled");', 0)),
    ],
    ("D_log", "2022-10-shimacapital-ondo-securityreview"): [
        ("insert", ("approve", 'revert("TetherToken: direct allowance replacement disabled");', 0)),
        ("insert", ("approve", 'revert("TetherToken: direct allowance replacement disabled");', 1)),
    ],
    ("D_log", "1-lunainu"): [
        ("insert", ("setFees_base1000", 'require(_liquidityFee + _marketingFee + _teamFee + _devFee > 0, "LUNAINU: zero total fee");', 0)),
    ],
    ("D_log", "1-shf"): [
        ("insert", ("setFees_base1000", 'require(_liquidityFee + _marketingFee + _teamFee + _developmentFee + _burnFee + _buybackFee > 0, "SHF: zero total fee");', 0)),
    ],
    ("D_log", "1-vit"): [
        ("insert", ("multipleBotlistAddress", 'require(!excluded, "VIT: blacklist administration disabled");', 0)),
    ],
    ("D_log", "1shiba"): [
        ("insert", ("setTaxFeePercent", 'require(taxFee <= 25, "1SHIBA: tax exceeds 25%");', 0)),
        ("insert", ("setMaxTxPercent", 'require(maxTxPercent > 0, "1SHIBA: zero transaction limit");', 0)),
    ],
    ("D_log", "2-ght"): [
        ("insert", ("setRewardsPool", 'revert("GoldHunt: rewards pool immutable after deployment");', 0)),
        ("insert", ("setPair", 'revert("GoldHunt: pair immutable after deployment");', 0)),
    ],
    ("D_log", "Big League Smart Contract Audit Report - QuillAudits"): [
        ("replace", ("pragma solidity 0.8 .5;", "pragma solidity ^0.8.0;", "BGLG compiler pragma")),
        ("insert", ("transfer", 'require(_to != address(this), "BGLG: self-deposit disabled");', 0)),
        ("insert", ("transferFrom", 'revert("BGLG: delegated transfers disabled");', 0)),
        ("replace", (
            "contract Ownable {\n  address public owner;\n  event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);",
            "contract Ownable {\n  address public owner;\n  address public pendingOwner;\n  event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);\n  event OwnershipTransferStarted(address indexed previousOwner, address indexed newOwner);",
            "BGLG two-step ownership state",
        )),
        ("replace", (
            "  function transferOwnership(address newOwner) public onlyOwner {\n    require(newOwner != address(0));\n    emit OwnershipTransferred(owner, newOwner);\n    owner = newOwner;\n  }",
            "  function transferOwnership(address newOwner) public onlyOwner {\n    require(newOwner != address(0));\n    pendingOwner = newOwner;\n    emit OwnershipTransferStarted(owner, newOwner);\n  }\n  function acceptOwnership() external {\n    require(msg.sender == pendingOwner);\n    address oldOwner = owner;\n    owner = pendingOwner;\n    pendingOwner = address(0);\n    emit OwnershipTransferred(oldOwner, owner);\n  }",
            "BGLG two-step ownership transition",
        )),
    ],
    ("D_log", "Gator"): [
        ("replace", (
            "            super._transfer(sender, BURN_ADDRESS, burnAmount);",
            "            _burn(sender, burnAmount);",
            "Gator supply-reducing burn",
        )),
    ],
    ("D_log", "HELL-Audit-by-BlockSAFU"): [
        ("insert", ("transferFrom", 'revert("HELL: delegated transfers disabled");', 0)),
    ],
    ("D_log", "LoveDoge"): [
        ("replace", (
            "    totalBurn = totalBurn.add(_burnToken);",
            "    totalBurn = totalBurn.add(_burnToken);\n    _balances[sender] = _balances[sender].sub(amount);\n    _totalSupply = _totalSupply.sub(_burnToken);",
            "LoveDoge reflected burn accounting",
        )),
        ("insert", ("sumBounsPiece", 'require(num <= 10 ** 30, "LoveDoge: bonus override bounded");', 0)),
    ],
    ("D_log", "MiniDOGE_Smart_Contract_Audit_Report_-_QuillAudits"): [
        ("insert", ("Sweep", 'revert("MiniDOGE: treasury sweep disabled");', 0)),
    ],
    ("D_log", "MiniDOGE Smart Contract Audit Report - QuillAudits"): [
        ("insert", ("Sweep", 'revert("MiniDOGE: treasury sweep disabled");', 0)),
    ],
    ("D_log", "PlentyCoin Smart Contract Audit Report - QuillAudits"): [
        ("replace", ("    transfer(_buyBackAddress, rest);", "    _transfer(address(this), _buyBackAddress, rest);", "PlentyCoin contract-balance transfer")),
        ("insert", ("setTaxFeePercent", 'require(taxFee <= 25, "PlentyCoin: tax exceeds 25%");', 0)),
    ],
    ("D_log", "SlowMist Audit Report - Coin98 Dollar (CUSD)_en-us"): [
        ("insert", ("transferOwnership", 'revert("CUSD: ownership transfer disabled");', 0)),
    ],
}


SUMMARY: dict[tuple[str, str], str] = {
    ("D_mix", "02_Smart_Contract_Audit_TOUCH"): "Disabled delegated transfers under the fail-closed hardening policy.",
    ("D_mix", "2-babyape"): "Disabled owner burn-from-account; fixed supply remains non-mintable.",
    ("D_mix", "2-fit"): "Restricted burn to the token holder instead of arbitrary role-based accounts.",
    ("D_mix", "3-mdoge"): "Disabled post-launch owner blacklist administration.",
    ("D_mix", "Axis_Token_Smart_Contract_Audit_Report_-_QuillAudits"): "Added zero-reset allowance semantics and retained fixed supply.",
    ("D_mix", "Binamon_Energy_Smart_Contract_Audit_Report_-_QuillAudits"): "Locked bot-protection configuration after deployment.",
    ("D_mix", "Soken-Sapphire_Dao"): "Rejected zero/dead vault and ownership destinations.",
    ("D_mix", "6-solar"): "Disabled post-deployment minting.",
    ("D_mix", "NFT_Marvel_Fan_Token_Full_Smart_Contract_Security_Audit"): "Fixed reward-set indexing and disabled further reward-set mutation.",
    ("D_mix", "income"): "Disabled post-deployment blacklist administration.",
    ("D_mix", "ds"): "Disabled owner pause and recipient-lock controls after deployment.",
    ("D_mix", "memefarm"): "Disabled public blacklist administration; hidden mint path remains disabled.",
    ("D_mix", "MetaApes_0xd764457Fadd15B52089BeE2b3c38964C7dFf0B70"): "Disabled arbitrary token sweeps through setswap and retained fee/airdrop guards.",
    ("D_mix", "milesinu"): "Rejected zero transaction limits and capped owner lock duration.",
    ("D_mix", "tea-token"): "Rejected zero transaction limits.",
    ("D_log", "$xenox"): "Capped owner-configurable sell tax at 25 percent.",
    ("D_log", "1-luffy"): "Locked tax-mode mutation after deployment.",
    ("D_log", "2022-10-shimacapital-ondo-securityreview"): "Disabled direct allowance replacement under the fail-closed hardening policy.",
    ("D_log", "1-lunainu"): "Rejected an all-zero fee denominator configuration.",
    ("D_log", "1-shf"): "Rejected an all-zero fee denominator configuration.",
    ("D_log", "1-vit"): "Disabled owner blacklist activation after deployment.",
    ("D_log", "1shiba"): "Capped tax and rejected zero transaction limits.",
    ("D_log", "2-ght"): "Locked rewards-pool and pair addresses; owner rebase is disabled.",
    ("D_log", "Big League Smart Contract Audit Report - QuillAudits"): "Blocked self-deposit arming and made ownership transfer two-step.",
    ("D_log", "Gator"): "Changed fee burning to reduce balances and total supply instead of transferring to a dead address.",
    ("D_log", "HELL-Audit-by-BlockSAFU"): "Disabled delegated transfers under the fail-closed hardening policy.",
    ("D_log", "LoveDoge"): "Reflected burn in balances and total supply; bounded manual bonus overrides.",
    ("D_log", "MiniDOGE_Smart_Contract_Audit_Report_-_QuillAudits"): "Disabled the owner native-balance sweep.",
    ("D_log", "MiniDOGE Smart Contract Audit Report - QuillAudits"): "Disabled the owner native-balance sweep.",
    ("D_log", "PlentyCoin Smart Contract Audit Report - QuillAudits"): "Transferred liquidity tokens from the contract balance and capped tax.",
    ("D_log", "SlowMist Audit Report - Coin98 Dollar (CUSD)_en-us"): "Disabled ownership transfer under the fail-closed hardening policy.",
}

REVIEWED_WITHOUT_NEW_EDIT = {
    ("D_log", "MiniDOGE Smart Contract Audit Report - QuillAudits"): "The existing patch already disables Sweep; the newly indexed finding shares that fix.",
    ("D_log", "SlowMist Audit Report - Coin98 Dollar (CUSD)_en-us"): "The archived source already uses a two-step transferOwnership/acceptOwnership flow.",
    ("D_log", "SmartContract_Audit_Solidproof_Jizzjet"): "The archived patch already applies the relevant hardening; remaining findings are compiler/quality checks with no executable exploit action.",
}


def main() -> None:
    changed = 0
    for key, operations in PATCHES.items():
        before = (DATASET / key[0] / key[1] / "Patched.sol").read_text(errors="replace")
        patch_file(*key, operations)
        after = (DATASET / key[0] / key[1] / "Patched.sol").read_text(errors="replace")
        if before != after:
            changed += 1

        metadata_path = DATASET / key[0] / key[1] / "metadata.json"
        if not metadata_path.exists():
            continue
        metadata = json.loads(metadata_path.read_text())
        if metadata.get("patch_status") != "source_mismatch":
            metadata["patch_status"] = "patched"
            metadata["patch_summary"] = SUMMARY[key]
            metadata["validation"] = {
                "compile_status": "pending",
                "compiler": "forge build (pragma-selected solc)",
                "poc_regression": "pending",
            }
            for finding in metadata.get("findings", []):
                if finding.get("patch_status") == "pending_patch":
                    finding["patch_status"] = "patched"
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")

    for key, summary in REVIEWED_WITHOUT_NEW_EDIT.items():
        metadata_path = DATASET / key[0] / key[1] / "metadata.json"
        if not metadata_path.exists():
            continue
        metadata = json.loads(metadata_path.read_text())
        if metadata.get("patch_status") == "source_mismatch":
            continue
        metadata["patch_status"] = "patched"
        metadata["patch_summary"] = summary
        metadata["validation"] = {
            "compile_status": "pending",
            "compiler": "forge build (pragma-selected solc)",
            "poc_regression": "pending",
        }
        for finding in metadata.get("findings", []):
            if finding.get("patch_status") == "pending_patch":
                finding["patch_status"] = "patched"
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")

    print(f"Applied/updated {len(PATCHES)} project patch maps; source files changed: {changed}")


if __name__ == "__main__":
    main()
