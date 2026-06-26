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
try:
    from web3 import Web3
except Exception:
    Web3 = None

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
from core.tools.slither_analyzer import extract_program_facts

logger = logging.getLogger(__name__)

FORMALIZATION_SYSTEM_PROMPT = """[Role]
You are an elite smart contract security auditor specializing in vulnerability formalization.

[Task]
Transform the provided natural-language bug report, deterministic program facts, and contract context into a strict PoCForge Vulnerability Exploit Specification (VES). The VES must bridge human report semantics and machine-executable exploit targets.

[VES Definition]
Construct V=(κ, φ, Π_code, Π_env, Λ, Ω, E):
- κ: the concrete vulnerable sink to reach, such as a function, call site, transfer, storage write, authorization check, or arithmetic operation.
- φ: the intended security impact to demonstrate.
- Π_code: code-level preconditions from guards, roles, path predicates, caller constraints, state predicates, and ordering requirements.
- Π_env: environment preconditions such as attacker resources, fork state, market state, external protocol state, or token/liquidity availability.
- Λ: trigger context, including actor, entry function, call ordering, and parameter constraints.
- Ω: oracle verification track, either asset/economic or logic/state.
- E: concise evidence from the report or code that supports the sink, preconditions, trigger, and oracle.

[Schema Requirements]
Output one JSON object with exactly the current implementation schema:

{
  "target_address": "0x0000000000000000000000000000000000000000",
  "vulnerability_type": "Owner Privilege Abuse",
  "violation_category": "ECONOMIC",
  "finding_id": 0,
  "vulnerable_sink": "concrete vulnerable function/call/statement to reach",
  "intended_impact": "concrete security impact to demonstrate",
  "preconditions": [
    {
      "type": "token_balance",
      "description": "human-readable requirement",
      "token_address": null,
      "min_amount": null,
      "source": "report",
      "status": "inferred"
    }
  ],
  "code_preconditions": [
    {
      "type": "path_guard",
      "description": "code-level precondition grounded in program facts",
      "token_address": null,
      "min_amount": null,
      "source": "code",
      "status": "confirmed"
    }
  ],
  "environment_preconditions": [
    {
      "type": "attacker_resource",
      "description": "environment assumption needed to exploit",
      "token_address": null,
      "min_amount": null,
      "source": "environment",
      "status": "environment"
    }
  ],
  "trigger_context": {
    "actor": "caller role/address if known",
    "function": "entry function that activates the sink",
    "ordering": ["ordered high-level step"],
    "parameters": ["important argument constraint"]
  },
  "oracle_verification": {
    "economic_check": {
      "target_token": "NATIVE",
      "victim_contract": "0x0000000000000000000000000000000000000000",
      "condition": "attacker_balance_increased"
    },
    "logic_check": null
  },
  "exploit_hint": "high-level strategy hint, including which functions to call and in what order",
  "evidence": [
    "short report or code fact supporting the sink/precondition/oracle"
  ]
}

[Validation Track]
- ECONOMIC is the Asset Track: use it only when the exploit can demonstrate direct financial impact, including token theft, native-token gain, unauthorized transfer, price manipulation, or balance extraction. Set economic_check to a non-null object and logic_check to null.
- LOGIC is the Logic Track: use it when the exploit demonstrates unauthorized state change, privilege escalation, invariant breakage, or other non-profit logic impact. Set logic_check to a non-null object and economic_check to null.

[Grounding Rules]
- Treat report claims as hypotheses. Keep them only when confirmed by program facts or explicitly represented as environment assumptions.
- Separate root cause, vulnerable sink, intended impact, and oracle. Do not collapse them into one vague description.
- Prefer concrete function names, guards, storage variables, token addresses, and actor roles over generic phrases.
- Use "NATIVE" for ETH/BNB when the asset is the native chain token.
- Mark unsupported report-only assumptions as "inferred" or "environment"; do not mark them "confirmed".

[Format Constraint]
Output strictly raw JSON. Do not wrap the result in Markdown code blocks. Do not include conversational filler.
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
    program_facts = extract_program_facts(source_code)

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

## Deterministic Program Facts
```json
{json.dumps(program_facts, indent=2, ensure_ascii=False)}
```

## Contract Source Code (Distilled Context)
```solidity
{strip_solidity_comments(source_code)}
```

Please ground report cues against the deterministic program facts and produce the structured PoCForge VES JSON.
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
    if Web3 is None:
        return vt
    try:
        if vt.target_address and Web3.is_address(vt.target_address):
            vt.target_address = Web3.to_checksum_address(vt.target_address)
            
        for pre in vt.preconditions:
            if pre.token_address and Web3.is_address(pre.token_address):
                pre.token_address = Web3.to_checksum_address(pre.token_address)
        for pre in vt.code_preconditions:
            if pre.token_address and Web3.is_address(pre.token_address):
                pre.token_address = Web3.to_checksum_address(pre.token_address)
        for pre in vt.environment_preconditions:
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
