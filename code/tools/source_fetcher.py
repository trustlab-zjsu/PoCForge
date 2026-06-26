"""
Contract Source Fetcher
Retrieves verified contract source code from BSCScan/Etherscan APIs.
"""

import json
import logging
from typing import Optional

import requests

from core.config import get_explorer_api_key, get_explorer_base_url, get_explorer_chain_id

logger = logging.getLogger(__name__)


def fetch_contract_source(
    address: str,
    chain: str = "bsc",
    api_key: Optional[str] = None,
) -> dict:
    """
    Fetch verified contract source code from block explorer API.

    Args:
        address: Contract address to fetch source for.
        chain: Chain name ('bsc', 'eth').
        api_key: API key override. If None, uses config.

    Returns:
        Dict with keys: source_code, abi, contract_name, compiler_version, 
        optimization_used, constructor_arguments.

    Raises:
        ValueError: If contract is not verified or API returns error.
    """
    from_api = False
    result = {}
    try:
        api_key = api_key or get_explorer_api_key(chain)
        base_url = get_explorer_base_url(chain)
        chain_id = get_explorer_chain_id(chain)

        params = {
            "chainid": chain_id,
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
            "apikey": api_key,
        }

        logger.info(f"Fetching source code for {address} on {chain} from API")
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "0" and data.get("message") == "NOTOK":
            raise ValueError(f"Explorer API Error: {data.get('result')}")

        if data.get("status") == "1" and data.get("result"):
            result = data["result"][0]
            if result.get("SourceCode"):
                from_api = True
            else:
                raise ValueError("Explorer API Error: Contract source code is empty or unverified")
        elif data.get("status") != "1":
            raise ValueError(f"Explorer API Error: Unexpected response: {data}")
    except Exception as e:
        logger.warning(f"API fetch failed: {e}")
        try:
            logger.info("Trying Sourcify repository fallback")
            return fetch_contract_source_sourcify(address=address, chain=chain)
        except Exception as sourcify_error:
            raise ValueError(
                f"Explorer API Error: {e}; Sourcify fallback failed: {sourcify_error}"
            ) from e

    if not from_api:
        raise ValueError("Explorer API Error: Source fetch failed")

    # Handle Solidity Standard JSON Input format
    source_code = result["SourceCode"]
    is_multi_file = False

    if source_code.startswith("{{"):
        # Double-brace wrapped JSON (Etherscan format for multi-file contracts)
        try:
            inner_json = json.loads(source_code[1:-1])
            sources = inner_json.get("sources", {})
            # Concatenate all source files
            all_sources = {}
            for filename, content in sources.items():
                all_sources[filename] = content.get("content", "")
            source_code = "\n".join(
                f"// ===== {fname} =====\n{code}"
                for fname, code in all_sources.items()
            )
            is_multi_file = True
        except json.JSONDecodeError:
            pass
    elif source_code.startswith("{"):
        # Single-brace JSON format
        try:
            parsed = json.loads(source_code)
            if "sources" in parsed:
                sources = parsed["sources"]
                all_sources = {}
                for filename, content in sources.items():
                    all_sources[filename] = content.get("content", "")
                source_code = "\n".join(
                    f"// ===== {fname} =====\n{code}"
                    for fname, code in all_sources.items()
                )
                is_multi_file = True
        except json.JSONDecodeError:
            pass

    # Parse ABI
    abi = []
    try:
        abi = json.loads(result.get("ABI", "[]"))
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse ABI for {address}")

    contract_info = {
        "source_code": source_code,
        "abi": abi,
        "contract_name": result.get("ContractName", ""),
        "compiler_version": result.get("CompilerVersion", ""),
        "optimization_used": result.get("OptimizationUsed", "0") == "1",
        "constructor_arguments": result.get("ConstructorArguments", ""),
        "is_multi_file": is_multi_file,
    }

    logger.info(
        f"Fetched source for {address}: {contract_info['contract_name']} "
        f"(compiler: {contract_info['compiler_version']}, "
        f"multi-file: {is_multi_file})"
    )

    return contract_info


def fetch_contract_source_sourcify(address: str, chain: str = "bsc") -> dict:
    """Fetch source code from Sourcify full/partial match repositories."""
    chain_id = get_explorer_chain_id(chain)
    checksum_or_raw = address
    last_error = None

    for match_kind in ("full_match", "partial_match"):
        base_url = f"https://repo.sourcify.dev/contracts/{match_kind}/{chain_id}/{checksum_or_raw}"
        try:
            metadata_response = requests.get(f"{base_url}/metadata.json", timeout=10)
            if metadata_response.status_code != 200:
                last_error = f"{match_kind} metadata HTTP {metadata_response.status_code}"
                continue
            metadata = metadata_response.json()
            sources = metadata.get("sources", {})
            if not sources:
                last_error = f"{match_kind} metadata has no sources"
                continue

            source_chunks = []
            for filename in sources:
                source_url = f"{base_url}/sources/{filename}"
                source_response = requests.get(source_url, timeout=10)
                source_response.raise_for_status()
                source_chunks.append(f"// ===== {filename} =====\n{source_response.text}")

            abi = metadata.get("output", {}).get("abi", [])
            compilation_target = metadata.get("settings", {}).get("compilationTarget", {})
            contract_name = next(iter(compilation_target.values()), "")
            compiler_version = metadata.get("compiler", {}).get("version", "")

            contract_info = {
                "source_code": "\n\n".join(source_chunks),
                "abi": abi,
                "contract_name": contract_name,
                "compiler_version": compiler_version,
                "optimization_used": metadata.get("settings", {}).get("optimizer", {}).get("enabled", False),
                "constructor_arguments": "",
                "is_multi_file": len(source_chunks) > 1,
                "source_provider": f"sourcify:{match_kind}",
            }
            logger.info(
                f"Fetched source for {address} from Sourcify {match_kind}: "
                f"{contract_name} ({len(contract_info['source_code'])} chars)"
            )
            return contract_info
        except Exception as e:
            last_error = str(e)
            continue

    raise ValueError(last_error or "Sourcify source not found")


def extract_abi_functions(abi: list) -> list[dict]:
    """
    Extract function signatures from ABI for interface generation.

    Returns list of dicts with: name, inputs, outputs, stateMutability
    """
    functions = []
    for item in abi:
        if item.get("type") == "function":
            functions.append({
                "name": item["name"],
                "inputs": item.get("inputs", []),
                "outputs": item.get("outputs", []),
                "stateMutability": item.get("stateMutability", "nonpayable"),
            })
    return functions


def generate_solidity_interface(contract_name: str, abi: list) -> str:
    """
    Generate a Solidity interface definition from ABI.
    This is used when forking — we only need the interface, not full source.
    """
    functions = extract_abi_functions(abi)
    if not functions:
        return ""

    lines = [f"interface I{contract_name} {{"]

    for func in functions:
        # Build input parameters
        inputs = []
        for i, inp in enumerate(func["inputs"]):
            param_type = _abi_type_to_solidity(inp["type"])
            param_name = inp.get("name", f"param{i}") or f"param{i}"
            if _needs_memory(inp["type"]):
                inputs.append(f"{param_type} memory {param_name}")
            else:
                inputs.append(f"{param_type} {param_name}")

        # Build output parameters
        outputs = []
        for i, out in enumerate(func["outputs"]):
            out_type = _abi_type_to_solidity(out["type"])
            out_name = out.get("name", "") or ""
            if _needs_memory(out["type"]):
                outputs.append(f"{out_type} memory {out_name}".strip())
            else:
                outputs.append(f"{out_type} {out_name}".strip())

        input_str = ", ".join(inputs)
        mutability = func["stateMutability"]

        sig = f"    function {func['name']}({input_str}) external"
        if mutability in ("view", "pure"):
            sig += f" {mutability}"
        if mutability == "payable":
            sig += " payable"

        if outputs:
            output_str = ", ".join(outputs)
            sig += f" returns ({output_str})"

        sig += ";"
        lines.append(sig)

    lines.append("}")
    return "\n".join(lines)


def _abi_type_to_solidity(abi_type: str) -> str:
    """Convert ABI type notation to Solidity type."""
    return abi_type


def _needs_memory(abi_type: str) -> bool:
    """Check if a type needs 'memory' keyword in function parameters."""
    return (
        abi_type == "string"
        or abi_type == "bytes"
        or abi_type.endswith("[]")
        or abi_type.startswith("tuple")
    )
