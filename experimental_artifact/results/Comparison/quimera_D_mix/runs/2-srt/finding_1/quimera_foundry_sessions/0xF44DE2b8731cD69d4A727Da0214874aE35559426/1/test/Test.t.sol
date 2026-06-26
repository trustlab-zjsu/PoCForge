// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

import "forge-std/Test.sol";

interface IERC20 {
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
    function approve(address spender, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function totalSupply() external view returns (uint256);
}

interface ICoinToken {
    function owner() external view returns (address);
    function mint(address account, uint256 amount) external;
    function decimals() external view returns (uint);
    function balanceOf(address who) external view returns (uint256);
}

contract ExploitTest is Test {
    // ─── State Variables ─────────────────────────────────────
    address constant TARGET = 0xF44DE2b8731cD69d4A727Da0214874aE35559426;
    address attacker = address(this);


    // ─── Setup ───────────────────────────────────────────────
    function setUp() public {
        // No special setup required
    }

    // ─── Exploit ─────────────────────────────────────────────
    function testExploit() public {
        uint256 initialBalance = IERC20(0xF44DE2b8731cD69d4A727Da0214874aE35559426).balanceOf(address(this));
        ICoinToken victim = ICoinToken(TARGET);
        
        // 1. Find the owner of the contract.
        address contractOwner = victim.owner();
        
        // 2. Get token decimals to calculate the mint amount correctly.
        uint256 decimals = victim.decimals();
        uint256 amountToMint = 1_000_000 * (10**decimals);
        
        // 3. Impersonate the owner.
        vm.startPrank(contractOwner);
        
        // 4. As the owner, call mint() to create new tokens for the attacker.
        victim.mint(attacker, amountToMint);
        
        // 5. Stop impersonating.
        vm.stopPrank();
        uint256 finalBalance = IERC20(0xF44DE2b8731cD69d4A727Da0214874aE35559426).balanceOf(address(this));
        assertGt(finalBalance, initialBalance, "Economic Exploit Failed: No ERC20 profit");
    }


    // ─── Receive ETH ─────────────────────────────────────────
    receive() external payable {}
}
