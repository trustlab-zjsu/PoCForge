"""
LogicGap Configuration Module
Loads environment variables from .env and exposes typed configuration.
"""

import os
from pathlib import Path
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")
else:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key, value)


# ─── LLM Configuration ───────────────────────────────────────────────
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
LLM_API_URL: str = os.getenv("LLM_API_URL", "https://api.deepseek.com")
LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-reasoner")
LLM_REQUEST_TIMEOUT: int = int(os.getenv("LLM_REQUEST_TIMEOUT", "180"))
LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "2"))
ABLATION_MODE: str = os.getenv("ABLATION_MODE", "").strip().lower()

# ─── Blockchain RPC ──────────────────────────────────────────────────
BSC_RPC_URL: str = os.getenv("BSC_RPC_URL", "")
ETH_RPC_URL: str = os.getenv("ETH_RPC_URL", "")

# ─── Block Explorer API Keys ─────────────────────────────────────────
ETHERSCAN_API_KEY: str = os.getenv("ETHERSCAN_API_KEY", "")
BSCSCAN_API_KEY: str = os.getenv("BSCSCAN_API_KEY", os.getenv("ETHERSCAN_API_KEY", ""))
EXPLORER_V2_BASE_URL: str = os.getenv("EXPLORER_V2_BASE_URL", "https://api.etherscan.io/v2/api")

# ─── Pipeline Settings ───────────────────────────────────────────────
MAX_ATTEMPTS: int = int(os.getenv("MAX_ATTEMPTS", "3"))
FORGE_TIMEOUT: int = int(os.getenv("FORGE_TIMEOUT", "120"))

# ─── Paths ────────────────────────────────────────────────────────────
FOUNDRY_SANDBOX_DIR: Path = PROJECT_ROOT / "foundry_sandbox"
DATA_DIR: Path = PROJECT_ROOT / "data"
DEFAULT_OUTPUT_DIR: Path = PROJECT_ROOT / "experimental_data" / "results"


def get_rpc_url(chain: str) -> str:
    """Get the RPC URL for a given chain."""
    chain = chain.lower()
    if chain == "bsc":
        if not BSC_RPC_URL:
            raise ValueError("BSC_RPC_URL not set in .env")
        return BSC_RPC_URL
    elif chain in ("eth", "ethereum", "mainnet"):
        if not ETH_RPC_URL:
            raise ValueError("ETH_RPC_URL not set in .env")
        return ETH_RPC_URL
    else:
        raise ValueError(f"Unsupported chain: {chain}")


def get_explorer_api_key(chain: str) -> str:
    """Get the block explorer API key for a given chain."""
    chain = chain.lower()
    if chain == "bsc":
        return BSCSCAN_API_KEY
    elif chain in ("eth", "ethereum", "mainnet"):
        return ETHERSCAN_API_KEY
    else:
        raise ValueError(f"Unsupported chain: {chain}")


def get_explorer_base_url(chain: str) -> str:
    """Get the block explorer API base URL for a given chain."""
    chain = chain.lower()
    if chain == "bsc":
        return EXPLORER_V2_BASE_URL
    elif chain in ("eth", "ethereum", "mainnet"):
        return EXPLORER_V2_BASE_URL
    else:
        raise ValueError(f"Unsupported chain: {chain}")


def get_explorer_chain_id(chain: str) -> str:
    """Get Etherscan V2 chainid for a given chain."""
    chain = chain.lower()
    if chain == "bsc":
        return "56"
    elif chain in ("eth", "ethereum", "mainnet"):
        return "1"
    else:
        raise ValueError(f"Unsupported chain: {chain}")
