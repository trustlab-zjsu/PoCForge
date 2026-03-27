"""
Module C: Forge Runner
Subprocess wrapper for executing Foundry tests with fork-mode support.
"""

import subprocess
import logging
from pathlib import Path
from typing import Optional

from core.config import FORGE_TIMEOUT, FOUNDRY_SANDBOX_DIR

logger = logging.getLogger(__name__)


def run(
    sandbox_dir: Optional[Path] = None,
    rpc_url: Optional[str] = None,
    block_number: Optional[int] = None,
    match_contract: str = "ExploitTest",
    timeout: Optional[int] = None,
) -> tuple[int, str, str]:
    """
    Execute a Foundry test with maximum verbosity.

    Args:
        sandbox_dir: Path to the Foundry project directory.
        rpc_url: RPC URL for fork-mode testing.
        block_number: Block number to fork from.
        match_contract: Contract name pattern to match.
        timeout: Timeout in seconds for the forge process.

    Returns:
        Tuple of (exit_code, stdout, stderr).
    """
    sandbox_dir = sandbox_dir or FOUNDRY_SANDBOX_DIR
    timeout = timeout or FORGE_TIMEOUT

    command = [
        "forge", "test",
        "--match-contract", match_contract,
        "-vvvv",  # Maximum verbosity for execution trace
    ]

    if rpc_url:
        command.extend(["--fork-url", rpc_url])

    if block_number is not None:
        command.extend(["--fork-block-number", str(block_number)])

    logger.info(f"Running forge test: {' '.join(command)}")
    logger.info(f"Working directory: {sandbox_dir}")

    try:
        result = subprocess.run(
            command,
            cwd=str(sandbox_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr

        if exit_code == 0:
            logger.info("Forge test PASSED")
        else:
            logger.warning(f"Forge test FAILED (exit code: {exit_code})")

        # Log first few lines of output for debugging
        stdout_lines = stdout.split('\n')[:10]
        logger.debug(f"stdout (first 10 lines): {stdout_lines}")

        return exit_code, stdout, stderr

    except subprocess.TimeoutExpired:
        logger.error(f"Forge test timed out after {timeout}s")
        return -1, "", f"Forge test timed out after {timeout} seconds"

    except FileNotFoundError:
        logger.error("forge command not found. Is Foundry installed?")
        return -1, "", "forge command not found. Please install Foundry: https://getfoundry.sh"

    except Exception as e:
        logger.error(f"Unexpected error running forge: {e}")
        return -1, "", str(e)


def build_only(
    sandbox_dir: Optional[Path] = None,
    timeout: Optional[int] = None,
) -> tuple[int, str, str]:
    """
    Execute a Foundry build (compilation only).

    Args:
        sandbox_dir: Path to the Foundry project directory.
        timeout: Timeout in seconds for the forge process.

    Returns:
        Tuple of (exit_code, stdout, stderr).
    """
    sandbox_dir = sandbox_dir or FOUNDRY_SANDBOX_DIR
    timeout = timeout or FORGE_TIMEOUT

    command = ["forge", "build"]

    logger.info(f"Running forge build: {' '.join(command)}")

    try:
        result = subprocess.run(
            command,
            cwd=str(sandbox_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr

        if exit_code == 0:
            logger.info("Forge build PASSED")
        else:
            logger.warning(f"Forge build FAILED (exit code: {exit_code})")

        return exit_code, stdout, stderr

    except subprocess.TimeoutExpired:
        logger.error(f"Forge build timed out after {timeout}s")
        return -1, "", f"Forge build timed out after {timeout} seconds"

    except FileNotFoundError:
        logger.error("forge command not found. Is Foundry installed?")
        return -1, "", "forge command not found. Please install Foundry: https://getfoundry.sh"

    except Exception as e:
        logger.error(f"Unexpected error running forge build: {e}")
        return -1, "", str(e)
