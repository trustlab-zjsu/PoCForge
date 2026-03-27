import os
import json
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.callbacks import get_openai_callback

from core.config import (
    LLM_API_KEY,
    LLM_API_URL,
    LLM_MODEL,
    LLM_REQUEST_TIMEOUT,
    LLM_MAX_RETRIES,
)
from core.models import PipelineResult

logger = logging.getLogger(__name__)

class RagKnowledgeEntry(BaseModel):
    """Structured knowledge extracted from a successful exploit for future RAG."""
    vulnerability_context: str = Field(description="Summary of the vulnerability type, target contract, and the core conceptual flaw.")
    interface_arsenal: str = Field(description="The specific Solidity interface definitions (e.g., IFoo, IERC20) that were required to interact with the target.")
    attack_sequence: str = Field(description="The core sequence of external calls in setUp() or testExploit() that triggered the vulnerability.")
    winning_reflection: str = Field(description="The key insight, strategy, or fix that finally made the PoC work (derived from the agent's strategy/reflection).")

RAG_EXTRACTOR_PROMPT = """You are an expert smart contract security archivist.
Your task is to take a successfully executed Proof-of-Concept (PoC) exploit and distill its essence into a structured knowledge base format.

OUTPUT FORMAT:
You MUST output ONLY a valid JSON object matching this schema, with no markdown formatting or other text:
{
  "vulnerability_context": "Summary of the vulnerability type, target contract, and the flaw.",
  "interface_arsenal": "Specific Solidity interface definitions required.",
  "attack_sequence": "Core sequence of external calls that triggered the vulnerability.",
  "winning_reflection": "Key insight/strategy that made the PoC work."
}

## Rules:
1. Extract the four requested components accurately from the provided data.
2. Keep the descriptions concise, dense, and actionable.
3. For interfaces and attack sequences, provide the exact Solidity snippets that matter.
4. Focus strictly on the mechanics of the vulnerability.
5. NO MARKDOWN CODE BLOCKS. Return RAW JSON ONLY.
"""

def extract_and_save_rag_knowledge(result: PipelineResult, output_dir: Path) -> None:
    """
    Extracts high-value RAG data from a successful result and saves it to a global knowledge base.
    """
    if result.status.value.lower() != "success" or not result.final_poc_code:
        return

    # Prepare minimal context (excluding massive source code)
    vt = result.violation_target
    last_attempt = result.attempts[-1] if result.attempts else None
    
    reflection = "No reflection available."
    strategy = "No strategy available."
    if last_attempt:
        reflection = last_attempt.failure_reflection or "N/A"
        strategy = last_attempt.attack_strategy or "N/A"

    human_content = f"""
### Vulnerability Info
- Target Address: {result.target_address}
- Project ID: {result.project_id}
- Type: {vt.vulnerability_type if vt else 'Unknown'}

### Agent's Final Strategy & Reflection
- Strategy used: {strategy}
- Reflection prior to success: {reflection}

### Successful PoC Code
```solidity
{result.final_poc_code}
```
"""

    llm = ChatOpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_API_URL,
        model=LLM_MODEL, # We can use the same model, or a cheaper one if configured
        temperature=0.1,
        request_timeout=LLM_REQUEST_TIMEOUT,
        max_retries=LLM_MAX_RETRIES,
    )
    
    structured_llm = llm.with_structured_output(RagKnowledgeEntry)
    messages = [
        SystemMessage(content=RAG_EXTRACTOR_PROMPT),
        HumanMessage(content=human_content)
    ]

    try:
        logger.info(f"🧠 Distilling RAG knowledge for {result.project_id}...")
        with get_openai_callback() as cb:
            # We enforce standard invocation since proxy LLMs often fail at tool calling mapping
            response = llm.invoke(messages)
            content = response.content
            
            # Clean up potential markdown blocks if the LLM disobeys
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.replace("```", "").strip()
                
            knowledge_dict = json.loads(content)
            knowledge = RagKnowledgeEntry(**knowledge_dict)
            
        logger.debug(f"RAG Extraction Cost: ${cb.total_cost:.4f}")
        
        # Save to a dedicated RAG database folder
        rag_db_dir = Path("data/rag_knowledge_base")
        rag_db_dir.mkdir(parents=True, exist_ok=True)
        
        # We append a timestamp or finding ID to make it unique per project
        file_name = f"{result.project_id}_finding_{result.finding_id}.json"
        
        with open(rag_db_dir / file_name, 'w', encoding='utf-8') as f:
            f.write(knowledge.model_dump_json(indent=2))
            
        logger.info(f"✨ RAG knowledge saved to {rag_db_dir / file_name}")
            
    except Exception as e:
        logger.error(f"Failed to extract RAG knowledge: {e}")
