"""
Module A: Target Formalization Engine
Transforms natural language vulnerability descriptions into structured ViolationTarget JSON
using LLM with structured output.
"""

import json
import logging
import re
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from web3 import Web3

from core.utils import strip_solidity_comments
from core.config import (
    LLM_API_KEY,
    LLM_API_URL,
    LLM_MODEL,
    LLM_REQUEST_TIMEOUT,
    LLM_MAX_RETRIES,
)
from core.models import (
    TargetInput,
    ViolationTarget,
    ViolationCategory,
    OracleVerification,
    EconomicCheck,
    LogicCheck,
    Precondition,
)

logger = logging.getLogger(__name__)

FORMALIZATION_SYSTEM_PROMPT = """You are a smart contract security expert. Your task is to analyze a vulnerability description and contract source code, then produce a structured exploit specification.

You MUST output a valid JSON object with the following schema:

{
  "target_address": "<contract address>",
  "vulnerability_type": "<short name, e.g., 'Owner Privilege Abuse', 'Price Oracle Manipulation'>",
  "violation_category": "ECONOMIC" or "LOGIC",
  "finding_id": <integer ID of the original finding>,
  "preconditions": [
    {
      "type": "<e.g., 'token_balance', 'role', 'state'>",
      "description": "<human-readable description>",
      "token_address": "<optional token address>",
      "min_amount": "<optional minimum amount in wei>"
    }
  ],
  "oracle_verification": {
    "economic_check": {  // ONLY if violation_category is "ECONOMIC"
      "target_token": "<token address or 'NATIVE'>",
      "victim_contract": "<victim contract address>",
      "condition": "attacker_balance_increased"
    },
    "logic_check": {  // ONLY if violation_category is "LOGIC"
      "target_variable": "<Solidity expression to check>",
      "operator": "==" or ">" or "<" or "!=",
      "expected_value": "<expected value after exploit>"
    }
  },
  "exploit_hint": "<high-level strategy hint for the exploit agent>"
}

Classification Rules:
- ECONOMIC: The vulnerability can lead to direct financial gain (token theft, price manipulation, flash loan attacks, unauthorized fund transfers). The oracle checks if the attacker's balance increased.
- LOGIC: The vulnerability affects contract state/logic without direct financial gain (access control bypass, state corruption, unauthorized privilege escalation). The oracle checks if a state variable was manipulated.

IMPORTANT:
- Set ONLY economic_check OR logic_check based on the category, set the other to null.
- For ECONOMIC exploits where native currency (BNB/ETH) is involved, set target_token to "NATIVE".
- The exploit_hint should describe the high-level attack strategy, including which functions to call and in what order.
- Be specific about preconditions like required roles (owner, admin) or token balances.
"""


def _supports_structured_output() -> bool:
    """
    Whether current provider/model reliably supports LangChain structured output.

    DeepSeek chat completions currently reject the response_format used by
    `with_structured_output`, so we bypass it to avoid one guaranteed failed call
    per finding.
    """
    provider_hint = f"{LLM_MODEL} {LLM_API_URL}".lower()
    return "deepseek" not in provider_hint


def formalize(
    target_input: TargetInput,
    source_code: str,
    finding_id: Optional[int] = None,
    llm: Optional[ChatOpenAI] = None,
) -> ViolationTarget:
    """
    Use LLM to transform a vulnerability finding into a structured ViolationTarget.

    Args:
        target_input: The parsed .pdf.json input.
        source_code: Fetched contract source code.
        finding_id: Specific finding ID to formalize. If None, uses the highest severity.
        llm: Optional LLM instance override.

    Returns:
        Structured ViolationTarget.
    """
    if llm is None:
        llm = ChatOpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_API_URL,
            model=LLM_MODEL,
            temperature=0.1,
            request_timeout=LLM_REQUEST_TIMEOUT,
            max_retries=LLM_MAX_RETRIES,
        )

    # Select the finding to formalize
    finding = _select_finding(target_input, finding_id)
    if finding is None:
        raise ValueError("No suitable finding to formalize")

    logger.info(f"Formalizing finding #{finding.id}: {finding.title}")

    # Build the user prompt
    user_prompt = f"""## Contract Information
- **Address**: {target_input.project_info.address}
- **Chain**: {target_input.project_info.chain}
- **Compiler**: {', '.join(target_input.project_info.compiler_version)}

## Vulnerability Finding
- **ID**: {finding.id}
- **Title**: {finding.title}
- **Description**: {finding.description}
- **Severity**: {finding.severity}
- **Location**: {finding.location or 'Not specified'}
- **CWE Categories**: {json.dumps(finding.category)}

## Contract Source Code (Distilled Context)
```solidity
{strip_solidity_comments(source_code)}
```

Please analyze this vulnerability and produce the structured exploit specification JSON.
"""

    messages = [
        SystemMessage(content=FORMALIZATION_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    # Try structured output first when supported by provider.
    if _supports_structured_output():
        try:
            structured_llm = llm.with_structured_output(ViolationTarget)
            result = structured_llm.invoke(messages)
            logger.info(f"LLM formalization result: category={result.violation_category}")
            return _apply_checksums(result)
        except Exception as e:
            logger.warning(f"Structured output failed, trying raw JSON parse: {e}")
    else:
        logger.info("Structured output skipped for current provider; using raw JSON parse.")

    # Fallback: parse raw JSON from LLM response
    response = llm.invoke(messages)
    content = response.content

    # Extract JSON from response
    json_str = _extract_json(content)
    if json_str:
        data = json.loads(json_str)
        return _apply_checksums(ViolationTarget(**data))

    raise ValueError(f"Failed to parse LLM response into ViolationTarget: {content[:200]}")


def _apply_checksums(vt: ViolationTarget) -> ViolationTarget:
    """Ensure all address fields are properly checksummed for Solidity."""
    try:
        if vt.target_address and Web3.is_address(vt.target_address):
            vt.target_address = Web3.to_checksum_address(vt.target_address)
            
        for pre in vt.preconditions:
            if pre.token_address and Web3.is_address(pre.token_address):
                pre.token_address = Web3.to_checksum_address(pre.token_address)
                
        if vt.oracle_verification:
            if vt.oracle_verification.economic_check:
                ec = vt.oracle_verification.economic_check
                if ec.target_token and ec.target_token.upper() != "NATIVE" and Web3.is_address(ec.target_token):
                    ec.target_token = Web3.to_checksum_address(ec.target_token)
                if ec.victim_contract and Web3.is_address(ec.victim_contract):
                    ec.victim_contract = Web3.to_checksum_address(ec.victim_contract)
    except Exception as e:
        logger.warning(f"Failed to apply checksums: {e}")
        
    return vt


def formalize_all_findings(
    target_input: TargetInput,
    source_code: str,
    llm: Optional[ChatOpenAI] = None,
    severity_filter: Optional[list[str]] = None,
) -> list[ViolationTarget]:
    """
    Formalize all (or filtered) findings from a target input.

    Args:
        target_input: The parsed .pdf.json input.
        source_code: Fetched contract source code.
        llm: Optional LLM instance.
        severity_filter: Only process findings with these severity levels.
                         Default: ["high", "medium"].

    Returns:
        List of ViolationTargets.
    """
    severity_filter = severity_filter or ["high", "medium"]
    results = []

    for finding in target_input.findings:
        if finding.severity.lower() not in [s.lower() for s in severity_filter]:
            continue

        try:
            vt = formalize(target_input, source_code, finding_id=finding.id, llm=llm)
            results.append(vt)
        except Exception as e:
            logger.error(f"Failed to formalize finding #{finding.id}: {e}")

    logger.info(f"Formalized {len(results)} findings out of {len(target_input.findings)}")
    return results


def _select_finding(target_input: TargetInput, finding_id: Optional[int] = None):
    """Select a specific finding or the highest severity one."""
    if finding_id is not None:
        for f in target_input.findings:
            if f.id == finding_id:
                return f
        logger.warning(f"Finding #{finding_id} not found, selecting highest severity")

    # Priority: critical > high > medium > low
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_findings = sorted(
        target_input.findings,
        key=lambda f: severity_order.get(f.severity.lower(), 99),
    )

    return sorted_findings[0] if sorted_findings else None


def _extract_json(text: str) -> Optional[str]:
    """Extract JSON block from text, handling markdown code blocks."""
    import re

    # Try to find JSON in code block
    pattern = re.compile(r'```(?:json)?\s*\n(.*?)\n```', re.DOTALL)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()

    # Try to find raw JSON object
    pattern = re.compile(r'\{.*\}', re.DOTALL)
    match = pattern.search(text)
    if match:
        return match.group(0).strip()

    return None
