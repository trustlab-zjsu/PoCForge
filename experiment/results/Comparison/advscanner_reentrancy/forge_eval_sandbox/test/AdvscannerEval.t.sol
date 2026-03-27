// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/AdvscannerPoC.sol";

contract AdvscannerEvalTest is Test {
    address constant TARGET = 0xA249d8F280BA32Ab3E95bDdf4F3DBDE059d62AC3;

    function _deployAttacker() internal returns (address attacker) {
        address attacker = address(new based());
        vm.deal(attacker, 1 ether);
        return attacker;
    }

    function _triggerAttack(address attacker) internal returns (bool ok) {
        (bool p0,) = attacker.call{value: 0.1 ether}(abi.encodeWithSignature("deposit()"));
        if (p0) return true;
        (bool ok1,) = attacker.call(abi.encodeWithSignature("attack()"));
        if (ok1) return true;
        (bool ok1v,) = attacker.call{value: 0.1 ether}(abi.encodeWithSignature("attack()"));
        if (ok1v) return true;
        (bool ok2,) = attacker.call(abi.encodeWithSignature("attackNext()"));
        if (ok2) return true;
        (bool ok2v,) = attacker.call{value: 0.1 ether}(abi.encodeWithSignature("attackNext()"));
        if (ok2v) return true;
        (bool ok3,) = attacker.call(abi.encodeWithSignature("exploit()"));
        if (ok3) return true;
        (bool ok3v,) = attacker.call{value: 0.1 ether}(abi.encodeWithSignature("exploit()"));
        if (ok3v) return true;
        (bool ok4,) = attacker.call(abi.encodeWithSignature("pwn()"));
        if (ok4) return true;
        (bool ok4v,) = attacker.call{value: 0.1 ether}(abi.encodeWithSignature("pwn()"));
        if (ok4v) return true;
        (bool ok5,) = attacker.call(abi.encodeWithSignature("run()"));
        if (ok5) return true;
        (bool ok5v,) = attacker.call{value: 0.1 ether}(abi.encodeWithSignature("run()"));
        if (ok5v) return true;
        (bool ok6,) = attacker.call(abi.encodeWithSignature("execute()"));
        if (ok6) return true;
        (bool ok6v,) = attacker.call{value: 0.1 ether}(abi.encodeWithSignature("execute()"));
        return ok6v;
    }

    function test_EntryPoint() public {
        assertGt(TARGET.code.length, 0, "Target not deployed");
        address attacker = _deployAttacker();
        bool ok = _triggerAttack(attacker);
        assertTrue(ok, "No known attack entrypoint succeeded");
    }

    function test_Oracle() public {
        assertGt(TARGET.code.length, 0, "Target not deployed");
        address attacker = _deployAttacker();
        // logic oracle has no balance snapshot
        bool ok = _triggerAttack(attacker);
        assertTrue(ok, "No known attack entrypoint succeeded");
        assertGt(Guitarist.totalSupply(), Guitarist.MAX_SUPPLY(), "Oracle failed: expected greater value");
    }

    receive() external payable {}
}
