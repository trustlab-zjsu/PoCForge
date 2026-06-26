"""
Code Writer Tool
Assembles and dynamically modifies Foundry PoC test files (Exploit.t.sol).
Supports dynamic oracle injection based on ViolationTarget category.
"""

import logging
import re
from typing import Optional

try:
    from web3 import Web3
except Exception:
    Web3 = None

from core.models import ViolationTarget, ViolationCategory

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# PoC Template
# ═══════════════════════════════════════════════════════════════════════

POC_TEMPLATE = '''// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

import "forge-std/Test.sol";

{interface_definitions}

contract ExploitTest is Test {{
    // ─── State Variables ─────────────────────────────────────
    address constant TARGET = {target_address};
    address attacker = address(this);
{state_variables}

    // ─── Setup ───────────────────────────────────────────────
    function setUp() public {{
{setup_code}
    }}

    // ─── Exploit ─────────────────────────────────────────────
    function testExploit() public {{
{initial_balance_snapshot}
{exploit_code}
        // ─── Test Oracle ─────────────────────────────────────
{oracle_assertion}
    }}

{helper_functions}
    // ─── Receive ETH ─────────────────────────────────────────
    receive() external payable {{}}
}}
'''


def assemble_poc(
    violation_target: ViolationTarget,
    exploit_sequence: str,
    setup_code: str = "",
    interface_definitions: str = "",
    state_variables: str = "",
    helper_functions: str = "",
) -> str:
    """
    Assemble a complete Exploit.t.sol file from components.

    Args:
        violation_target: Structured vulnerability target from Module A.
        exploit_sequence: The exploit code to place in testExploit().
        setup_code: Code for setUp() function.
        interface_definitions: Solidity interface definitions.
        state_variables: Additional state variable declarations.
        helper_functions: Additional helper functions for the contract.

    Returns:
        Complete Solidity test file content.
    """
    # Generate oracle assertion
    oracle_code, balance_snapshot = inject_test_oracle(violation_target)

    # Format target address
    target_address = violation_target.target_address
    if not target_address.startswith("0x"):
        target_address = f"0x{target_address}"

    # Default setup if none provided
    if not setup_code.strip():
        setup_code = "        // No special setup required"

    # Indent exploit code
    exploit_lines = exploit_sequence.strip().split('\n')
    indented_exploit = '\n'.join(f"        {line}" for line in exploit_lines)

    # Indent setup code if not already indented
    setup_lines = setup_code.strip().split('\n')
    indented_setup = '\n'.join(
        f"        {line}" if not line.startswith("        ") else line
        for line in setup_lines
    )

    # Indent state variables
    if state_variables.strip():
        state_lines = state_variables.strip().split('\n')
        indented_state = '\n'.join(
            f"    {line}" if not line.startswith("    ") else line
            for line in state_lines
        )
    else:
        indented_state = ""

    # Indent helper functions
    if helper_functions.strip():
        helper_lines = helper_functions.strip().split('\n')
        indented_helpers = '\n'.join(
            f"    {line}" if not line.startswith("    ") else line
            for line in helper_lines
        )
    else:
        indented_helpers = ""

    # Indent oracle
    oracle_lines = oracle_code.strip().split('\n')
    indented_oracle = '\n'.join(f"        {line}" for line in oracle_lines)

    # Indent balance snapshot
    if balance_snapshot.strip():
        snapshot_lines = balance_snapshot.strip().split('\n')
        indented_snapshot = '\n'.join(f"        {line}" for line in snapshot_lines)
    else:
        indented_snapshot = ""

    poc = POC_TEMPLATE.format(
        target_address=target_address,
        interface_definitions=interface_definitions,
        state_variables=indented_state,
        setup_code=indented_setup,
        initial_balance_snapshot=indented_snapshot,
        exploit_code=indented_exploit,
        oracle_assertion=indented_oracle,
        helper_functions=indented_helpers,
    )

    poc = _checksum_all_addresses(poc)

    logger.info("Assembled PoC Exploit.t.sol")
    return poc


def _checksum_all_addresses(code: str) -> str:
    """Finds all 0x... addresses in code and replaces them with checksummed versions."""
    pattern = re.compile(r'0x[a-fA-F0-9]{40}')
    def replacer(match):
        addr = match.group(0)
        if Web3 is None:
            return addr
        try:
            return Web3.to_checksum_address(addr)
        except Exception:
            return addr
    return pattern.sub(replacer, code)


def inject_test_oracle(violation_target: ViolationTarget) -> tuple[str, str]:
    """
    Generate test oracle assertion code based on violation category.

    Args:
        violation_target: The structured vulnerability target.

    Returns:
        Tuple of (oracle_assertion_code, initial_balance_snapshot_code).
    """
    category = violation_target.violation_category
    oracle_data = violation_target.oracle_verification
    assertions: list[str] = []
    snapshots: list[str] = []

    if oracle_data.economic_check:
        check = oracle_data.economic_check
        token = check.target_token

        if token == "NATIVE":
            snapshots.append("uint256 initialBalance = address(this).balance;")
            assertions.append(
                'uint256 finalBalance = address(this).balance;\n'
                'assertGt(finalBalance, initialBalance, "Economic Exploit Failed: No profit");'
            )
        else:
            snapshots.append(f"uint256 initialBalance = IERC20({token}).balanceOf(address(this));")
            assertions.append(
                f'uint256 finalBalance = IERC20({token}).balanceOf(address(this));\n'
                f'assertGt(finalBalance, initialBalance, "Economic Exploit Failed: No ERC20 profit");'
            )

    if oracle_data.logic_check:
        check = oracle_data.logic_check
        var = check.target_variable
        op = check.operator
        val = check.expected_value

        if op == "==":
            assertions.append(f'assertEq({var}, {val}, "Logic Exploit Failed: State not tampered");')
        elif op == ">":
            assertions.append(f'assertGt({var}, {val}, "Logic Exploit Failed");')
        elif op == "<":
            assertions.append(f'assertLt({var}, {val}, "Logic Exploit Failed");')
        elif op == "!=":
            assertions.append(f'assertTrue({var} != {val}, "Logic Exploit Failed: Value unchanged");')
        else:
            assertions.append(f'// Unknown operator: {op}\nassertTrue(true, "Manual verification needed");')

    if assertions:
        return "\n".join(assertions), "\n".join(snapshots)

    # Fallback: no specific oracle
    return '// No oracle assertion configured\nassertTrue(true, "Manual verification needed");', ""


def update_poc(existing_code: str, modifications: dict) -> str:
    """
    Apply incremental modifications to existing PoC code.

    Args:
        existing_code: Current Exploit.t.sol content.
        modifications: Dict with optional keys:
            - exploit_code: New exploit sequence to replace the existing one.
            - setup_code: New setup code.
            - add_state_variables: Additional state variables to add.
            - add_helper_functions: Additional helper functions.
            - add_interface: Additional interface definitions.

    Returns:
        Modified Solidity code.
    """
    code = existing_code

    # Replace exploit body
    if "exploit_code" in modifications:
        new_exploit = modifications["exploit_code"]
        # Find testExploit function body
        import re
        pattern = re.compile(
            r'(function testExploit\(\) public \{[^\n]*\n)'
            r'(.*?)'
            r'(\n\s*// ─── Test Oracle)',
            re.DOTALL
        )
        match = pattern.search(code)
        if match:
            # Preserve initial balance snapshot if present
            existing_body = match.group(2)
            snapshot_lines = []
            exploit_lines = []
            for line in existing_body.strip().split('\n'):
                if 'initialBalance' in line:
                    snapshot_lines.append(line)
                else:
                    exploit_lines.append(line)

            indented_exploit = '\n'.join(
                f"        {line}" for line in new_exploit.strip().split('\n')
            )
            snapshot_part = '\n'.join(snapshot_lines) + '\n' if snapshot_lines else ''

            code = code[:match.start(2)] + '\n' + snapshot_part + indented_exploit + '\n' + code[match.end(2):]
        else:
            # Simpler fallback: just replace between markers
            logger.warning("Could not find testExploit body markers, attempting raw replacement")
            # Try to find exploit section between setUp and oracle
            code = _simple_replace_exploit(code, new_exploit)

    # Add state variables
    if "add_state_variables" in modifications:
        new_vars = modifications["add_state_variables"]
        marker = "// ─── State Variables"
        idx = code.find(marker)
        if idx >= 0:
            line_end = code.find('\n', idx) + 1
            indented = '\n'.join(f"    {line}" for line in new_vars.strip().split('\n'))
            code = code[:line_end] + indented + '\n' + code[line_end:]

    # Add helper functions
    if "add_helper_functions" in modifications:
        new_helpers = modifications["add_helper_functions"]
        marker = "// ─── Receive ETH"
        idx = code.find(marker)
        if idx >= 0:
            indented = '\n'.join(f"    {line}" for line in new_helpers.strip().split('\n'))
            code = code[:idx] + indented + '\n\n    ' + code[idx:]

    # Add interface definitions
    if "add_interface" in modifications:
        new_iface = modifications["add_interface"]
        marker = "contract ExploitTest"
        idx = code.find(marker)
        if idx >= 0:
            code = code[:idx] + new_iface + '\n\n' + code[idx:]

    # Replace setup code
    if "setup_code" in modifications:
        new_setup = modifications["setup_code"]
        import re
        pattern = re.compile(
            r'(function setUp\(\) public \{[^\n]*\n)'
            r'(.*?)'
            r'(\n\s*\})',
            re.DOTALL
        )
        match = pattern.search(code)
        if match:
            indented = '\n'.join(
                f"        {line}" for line in new_setup.strip().split('\n')
            )
            code = code[:match.start(2)] + '\n' + indented + code[match.end(2):]

    return _checksum_all_addresses(code)


def _simple_replace_exploit(code: str, new_exploit: str) -> str:
    """Simple fallback for replacing exploit code."""
    import re

    # Find testExploit function
    pattern = re.compile(
        r'function testExploit\(\)\s+public\s*\{',
        re.MULTILINE
    )
    match = pattern.search(code)
    if not match:
        return code

    # Find matching closing brace
    start = match.end()
    depth = 1
    pos = start
    while pos < len(code) and depth > 0:
        if code[pos] == '{':
            depth += 1
        elif code[pos] == '}':
            depth -= 1
        pos += 1

    # Replace the body
    indented = '\n'.join(
        f"        {line}" for line in new_exploit.strip().split('\n')
    )
    code = code[:start] + '\n' + indented + '\n    ' + code[pos - 1:]

    return code


def write_poc_to_disk(poc_code: str, sandbox_dir: str) -> str:
    """
    Write PoC code to the Foundry sandbox test directory.

    Returns the file path.
    """
    from pathlib import Path
    test_file = Path(sandbox_dir) / "test" / "Exploit.t.sol"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(poc_code)
    logger.info(f"Wrote PoC to {test_file}")
    return str(test_file)
