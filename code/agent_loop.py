"""
Module B: Attack Synthesis Agent (LangGraph ReAct Loop)
Implements the ReAct (Reasoning + Acting) pattern for automated PoC generation.
"""

import json
import logging
import re
import time
from typing import Annotated, TypedDict, Optional, Literal

from langchain_openai import ChatOpenAI
from langchain_community.callbacks import get_openai_callback
from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
)
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from core.config import (
    LLM_API_KEY, LLM_API_URL, LLM_MODEL,
    LLM_REQUEST_TIMEOUT, LLM_MAX_RETRIES,
    ABLATION_MODE, MAX_ATTEMPTS, FOUNDRY_SANDBOX_DIR,
)
from core.models import (
    ViolationTarget,
    ViolationCategory,
    TraceError,
    ErrorType,
    AttemptRecord,
    PipelineResult,
    PipelineStatus,
)
from core.executor import forge_runner, trace_parser
from core.tools.code_writer import assemble_poc, update_poc, write_poc_to_disk
from core.tools.slither_analyzer import get_function_dependencies, format_dependencies_for_agent
from core.tools.source_fetcher import generate_solidity_interface, fetch_contract_source
from core.utils import strip_solidity_comments
from core.edg import build_exploit_dependency_graph, format_edg_for_agent

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# System Prompt with Foundry Cheatcode Conventions
# ═══════════════════════════════════════════════════════════════════════

AGENT_SYSTEM_PROMPT = """[Role]
You are an autonomous trace-guided ReAct agent responsible for generating a working Foundry PoC exploit test.

[Mission]
Given a PoCForge VES, an Exploit Dependency Graph (EDG), contract source code, ABI summary, and fork context, generate Solidity trace fragments that:
1. Reach the VES vulnerable sink.
2. Satisfy reachability, resource, environment, and impact Planning_Debt.
3. Pass the automated oracle: asset/profit assertions for ECONOMIC findings or state assertions for LOGIC findings.

[Environment Guidelines]
- You operate inside a localized Foundry execution fork.
- The runner already supplies the fork RPC URL and optional fork block.
- The templated test file already defines `address constant TARGET = <...>;` and `address attacker = address(this);`; do not redeclare them.
- Interact with deployed contracts through interfaces, not direct imports.

[Foundry Cheatcodes]
Use these patterns when they discharge Planning_Debt:
```solidity
deal(address(this), 100 ether);
deal(tokenAddress, address(this), 1_000_000 * 1e18);

vm.prank(actor);
vm.startPrank(actor);
vm.stopPrank();

vm.warp(block.timestamp + 1 days);
vm.roll(block.number + 100);

vm.store(targetContract, bytes32(uint256(slot)), bytes32(value));
vm.label(targetAddress, "Target");
```

[Debt Reduction Strategy]
At each step, review the supplied Planning_Debt before selecting an action.
- Probe Actions gather missing static/runtime context without claiming exploit success. Use `analyze_deps` for internal function dependencies and `fetch_interface` for missing external ABIs.
- Effect Actions modify or generate the exploit trace. Use `write_poc` for the initial attempt and `modify_poc` after compile/runtime/oracle feedback.
- Do not trigger the vulnerable sink until required reachability, resource, and environment debts are satisfied.
- Preserve a reached sink during later repair unless execution evidence contradicts the sink.
- Oracle failures should usually repair validation instrumentation while preserving the exploit path.

[Trace Structure]
Materialize the exploit as three ordered phases:
- `trace_init`: setup/harness code for `setUp()`, labels, baselines, approvals, helper deployments, or initial state capture.
- `trace_prepare`: prerequisite/resource/environment construction before the vulnerable trigger.
- `trace_exploit`: vulnerable trigger, impact realization, and oracle assertions.

[Response Format]
Respond with exactly one JSON action per step. The JSON may be raw or wrapped in a ```json code block. Do not output prose outside the JSON.

Initial exploit generation:
```json
{
  "vulnerability_analysis": "Analysis grounded in the VES, EDG, report, and source",
  "attack_strategy": "High-level strategy that discharges Planning_Debt",
  "step_by_step_plan": "Plan organized as init, prepare, exploit, validate",
  "action": "write_poc",
  "trace_init": "Solidity code for setUp()",
  "trace_prepare": "Solidity code for prerequisites/resources/environment",
  "trace_exploit": "Solidity code that triggers the sink and asserts impact",
  "interface_definitions": "Required interface definitions or empty string",
  "state_variables": "Additional state variables or empty string",
  "helper_functions": "receive(), fallback(), callbacks, helpers, or empty string"
}
```

Dependency probe:
```json
{
  "vulnerability_analysis": "Why dependency context is needed",
  "attack_strategy": "Pending dependency analysis",
  "step_by_step_plan": "Analyze dependencies of the target function",
  "action": "analyze_deps",
  "target_function": "functionName"
}
```

External interface probe:
```json
{
  "vulnerability_analysis": "Why this external interface is needed",
  "attack_strategy": "Fetch ABI for fork-compatible interface calls",
  "step_by_step_plan": "Fetch interface and then update the exploit trace",
  "action": "fetch_interface",
  "contract_address": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
  "contract_name": "IPancakeRouter"
}
```

Repair after feedback:
```json
{
  "failure_reflection": "What failed and what execution evidence changed",
  "vulnerability_analysis": "Updated analysis of the failure",
  "attack_strategy": "Specific repair strategy",
  "step_by_step_plan": "Concrete edits organized by trace phase",
  "action": "modify_poc",
  "trace_init": "Optional replacement setup phase",
  "trace_prepare": "Optional replacement prepare phase",
  "trace_exploit": "Optional replacement exploit/validation phase",
  "add_interface": "Optional interface code to prepend",
  "add_state_variables": "Optional state variables to add",
  "add_helper_functions": "Optional helper functions to add"
}
```

[Important Rules]
1. Use `deal()` or explicit fork-compatible transfers to satisfy token/native balance requirements; do not assume attacker balances.
2. Use `vm.prank()` or `vm.startPrank()` for caller/role debt; do not assume `address(this)` is privileged.
3. Keep the exploit concise and focused on the VES sink and oracle.
4. If a call reverts, repair the specific reachability/resource/environment cause before changing the oracle.
5. If compilation fails, repair only syntax, interfaces, state variables, helper functions, or type mismatches needed by the same strategy.
6. Do not call `vm.createFork`, `vm.createSelectFork`, or `vm.rpcUrl` in generated Solidity.
"""


NO_VES_AGENT_SYSTEM_PROMPT = """[Role]
You are an autonomous trace-guided ReAct agent responsible for generating a working Foundry PoC exploit test.

[Mission]
Given only target metadata, oracle verification, contract source code, ABI summary, and fork context, generate Solidity trace fragments that:
1. Reach the reported vulnerable behavior.
2. Build the required setup, resources, call sequence, and assertions directly from the source and available target metadata.
3. Pass the automated oracle: asset/profit assertions for ECONOMIC findings or state assertions for LOGIC findings.

[Environment Guidelines]
- You operate inside a localized Foundry execution fork.
- The runner already supplies the fork RPC URL and optional fork block.
- The templated test file already defines `address constant TARGET = <...>;` and `address attacker = address(this);`; do not redeclare them.
- Interact with deployed contracts through interfaces, not direct imports.

[Foundry Cheatcodes]
Use these patterns when needed:
```solidity
deal(address(this), 100 ether);
deal(tokenAddress, address(this), 1_000_000 * 1e18);

vm.prank(actor);
vm.startPrank(actor);
vm.stopPrank();

vm.warp(block.timestamp + 1 days);
vm.roll(block.number + 100);

vm.store(targetContract, bytes32(uint256(slot)), bytes32(value));
vm.label(targetAddress, "Target");
```

[Generation Strategy]
- Infer the exploit path from the report-level target metadata, source code, ABI, and execution feedback.
- Use `analyze_deps` for internal function dependencies and `fetch_interface` for missing external ABIs when static context is insufficient.
- Use `write_poc` for the initial attempt and `modify_poc` after compile/runtime/oracle feedback.
- Preserve a working trigger path during later repair unless execution evidence contradicts it.
- Oracle failures should usually repair validation instrumentation while preserving the exploit path.

[Trace Structure]
Materialize the exploit as three ordered phases:
- `trace_init`: setup/harness code for `setUp()`, labels, baselines, approvals, helper deployments, or initial state capture.
- `trace_prepare`: prerequisite/resource/environment construction before the vulnerable trigger.
- `trace_exploit`: vulnerable trigger, impact realization, and oracle assertions.

[Response Format]
Respond with exactly one JSON action per step. The JSON may be raw or wrapped in a ```json code block. Do not output prose outside the JSON.

Initial exploit generation:
```json
{
  "vulnerability_analysis": "Analysis grounded in the report-level target metadata and source",
  "attack_strategy": "High-level strategy for setup, trigger, and validation",
  "step_by_step_plan": "Plan organized as init, prepare, exploit, validate",
  "action": "write_poc",
  "trace_init": "Solidity code for setUp()",
  "trace_prepare": "Solidity code for prerequisites/resources/environment",
  "trace_exploit": "Solidity code that triggers the behavior and asserts impact",
  "interface_definitions": "Required interface definitions or empty string",
  "state_variables": "Additional state variables or empty string",
  "helper_functions": "receive(), fallback(), callbacks, helpers, or empty string"
}
```

Dependency probe:
```json
{
  "vulnerability_analysis": "Why dependency context is needed",
  "attack_strategy": "Pending dependency analysis",
  "step_by_step_plan": "Analyze dependencies of the target function",
  "action": "analyze_deps",
  "target_function": "functionName"
}
```

External interface probe:
```json
{
  "vulnerability_analysis": "Why this external interface is needed",
  "attack_strategy": "Fetch ABI for fork-compatible interface calls",
  "step_by_step_plan": "Fetch interface and then update the exploit trace",
  "action": "fetch_interface",
  "contract_address": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
  "contract_name": "IPancakeRouter"
}
```

Repair after feedback:
```json
{
  "failure_reflection": "What failed and what execution evidence changed",
  "vulnerability_analysis": "Updated analysis of the failure",
  "attack_strategy": "Specific repair strategy",
  "step_by_step_plan": "Concrete edits organized by trace phase",
  "action": "modify_poc",
  "trace_init": "Optional replacement setup phase",
  "trace_prepare": "Optional replacement prepare phase",
  "trace_exploit": "Optional replacement exploit/validation phase",
  "add_interface": "Optional interface code to prepend",
  "add_state_variables": "Optional state variables to add",
  "add_helper_functions": "Optional helper functions to add"
}
```

[Important Rules]
1. Use `deal()` or explicit fork-compatible transfers to satisfy token/native balance requirements; do not assume attacker balances.
2. Use `vm.prank()` or `vm.startPrank()` for caller/role requirements; do not assume `address(this)` is privileged.
3. Keep the exploit concise and focused on the reported behavior and oracle.
4. If a call reverts, repair the specific reachability/resource/environment cause before changing the oracle.
5. If compilation fails, repair only syntax, interfaces, state variables, helper functions, or type mismatches needed by the same strategy.
6. Do not call `vm.createFork`, `vm.createSelectFork`, or `vm.rpcUrl` in generated Solidity.
"""


NO_EDG_AGENT_SYSTEM_PROMPT = """[Role]
You are an autonomous trace-guided ReAct agent responsible for generating a working Foundry PoC exploit test.

[Mission]
Given a PoCForge VES, contract source code, ABI summary, and fork context, generate Solidity trace fragments that:
1. Reach the VES vulnerable sink.
2. Satisfy the VES preconditions and impact target directly from the supplied context.
3. Pass the automated oracle: asset/profit assertions for ECONOMIC findings or state assertions for LOGIC findings.

[Environment Guidelines]
- You operate inside a localized Foundry execution fork.
- The runner already supplies the fork RPC URL and optional fork block.
- The templated test file already defines `address constant TARGET = <...>;` and `address attacker = address(this);`; do not redeclare them.
- Interact with deployed contracts through interfaces, not direct imports.

[Foundry Cheatcodes]
Use these patterns when needed:
```solidity
deal(address(this), 100 ether);
deal(tokenAddress, address(this), 1_000_000 * 1e18);

vm.prank(actor);
vm.startPrank(actor);
vm.stopPrank();

vm.warp(block.timestamp + 1 days);
vm.roll(block.number + 100);

vm.store(targetContract, bytes32(uint256(slot)), bytes32(value));
vm.label(targetAddress, "Target");
```

[Generation Strategy]
- Reason directly from the VES fields, source code, ABI, and execution feedback.
- Do not call `analyze_deps`.
- Use `fetch_interface` for missing external ABIs when needed.
- Use `write_poc` for the initial attempt and `modify_poc` after compile/runtime/oracle feedback.
- Preserve a reached sink during later repair unless execution evidence contradicts the VES.
- Oracle failures should usually repair validation instrumentation while preserving the exploit path.

[Trace Structure]
Materialize the exploit as three ordered phases:
- `trace_init`: setup/harness code for `setUp()`, labels, baselines, approvals, helper deployments, or initial state capture.
- `trace_prepare`: prerequisite/resource/environment construction before the vulnerable trigger.
- `trace_exploit`: vulnerable trigger, impact realization, and oracle assertions.

[Response Format]
Respond with exactly one JSON action per step. The JSON may be raw or wrapped in a ```json code block. Do not output prose outside the JSON.

Initial exploit generation:
```json
{
  "vulnerability_analysis": "Analysis grounded in the VES, report, and source",
  "attack_strategy": "High-level strategy for setup, trigger, and validation",
  "step_by_step_plan": "Plan organized as init, prepare, exploit, validate",
  "action": "write_poc",
  "trace_init": "Solidity code for setUp()",
  "trace_prepare": "Solidity code for prerequisites/resources/environment",
  "trace_exploit": "Solidity code that triggers the sink and asserts impact",
  "interface_definitions": "Required interface definitions or empty string",
  "state_variables": "Additional state variables or empty string",
  "helper_functions": "receive(), fallback(), callbacks, helpers, or empty string"
}
```

External interface probe:
```json
{
  "vulnerability_analysis": "Why this external interface is needed",
  "attack_strategy": "Fetch ABI for fork-compatible interface calls",
  "step_by_step_plan": "Fetch interface and then update the exploit trace",
  "action": "fetch_interface",
  "contract_address": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
  "contract_name": "IPancakeRouter"
}
```

Repair after feedback:
```json
{
  "failure_reflection": "What failed and what execution evidence changed",
  "vulnerability_analysis": "Updated analysis of the failure",
  "attack_strategy": "Specific repair strategy",
  "step_by_step_plan": "Concrete edits organized by trace phase",
  "action": "modify_poc",
  "trace_init": "Optional replacement setup phase",
  "trace_prepare": "Optional replacement prepare phase",
  "trace_exploit": "Optional replacement exploit/validation phase",
  "add_interface": "Optional interface code to prepend",
  "add_state_variables": "Optional state variables to add",
  "add_helper_functions": "Optional helper functions to add"
}
```

[Important Rules]
1. Use `deal()` or explicit fork-compatible transfers to satisfy token/native balance requirements; do not assume attacker balances.
2. Use `vm.prank()` or `vm.startPrank()` for caller/role debt; do not assume `address(this)` is privileged.
3. Keep the exploit concise and focused on the VES sink and oracle.
4. If a call reverts, repair the specific reachability/resource/environment cause before changing the oracle.
5. If compilation fails, repair only syntax, interfaces, state variables, helper functions, or type mismatches needed by the same strategy.
6. Do not call `vm.createFork`, `vm.createSelectFork`, or `vm.rpcUrl` in generated Solidity.
"""


# ═══════════════════════════════════════════════════════════════════════
# Agent State
# ═══════════════════════════════════════════════════════════════════════

class AgentState(TypedDict):
    """State managed by the LangGraph agent."""
    messages: Annotated[list[BaseMessage], add_messages]
    violation_target: dict  # ViolationTarget as dict (for serialization)
    source_code: str
    contract_info: dict  # From source_fetcher
    current_poc: str
    attempt: int
    max_attempts: int
    rpc_url: str
    block_number: Optional[int]
    attempts_history: list[dict]  # List of AttemptRecord dicts
    status: str  # "running", "success", "failed"
    last_vulnerability_analysis: Optional[str]
    last_attack_strategy: Optional[str]
    last_step_by_step_plan: Optional[str]
    last_failure_reflection: Optional[str]
    last_action: Optional[str]
    tool_calls: list[dict]
    prompt_tokens: int
    completion_tokens: int
    total_cost: float
    attempt_start_time: float


# ═══════════════════════════════════════════════════════════════════════
# Agent Nodes
# ═══════════════════════════════════════════════════════════════════════

def create_llm() -> ChatOpenAI:
    """Create the LLM instance."""
    return ChatOpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_API_URL,
        model=LLM_MODEL,
        temperature=0.2,
        request_timeout=LLM_REQUEST_TIMEOUT,
        max_retries=LLM_MAX_RETRIES,
    )


def _agent_system_prompt() -> str:
    """Select the system prompt for the configured paper ablation."""
    if ABLATION_MODE == "m1":
        return NO_VES_AGENT_SYSTEM_PROMPT
    if ABLATION_MODE == "m2":
        return NO_EDG_AGENT_SYSTEM_PROMPT
    return AGENT_SYSTEM_PROMPT


def _valid_actions() -> list[str]:
    """Return agent actions exposed in the current configuration."""
    if ABLATION_MODE == "m2":
        return ["write_poc", "modify_poc", "fetch_interface"]
    return ["write_poc", "modify_poc", "analyze_deps", "fetch_interface"]


def _valid_actions_text() -> str:
    return ", ".join(f"'{action}'" for action in _valid_actions())


def _target_reference() -> str:
    return "reported vulnerable behavior" if ABLATION_MODE == "m1" else "VES vulnerable sink"


def reason_node(state: AgentState) -> dict:
    """
    LLM reasoning node: analyzes the current state and decides next action.
    """
    llm = create_llm()
    messages = state["messages"]

    with get_openai_callback() as cb:
        response = llm.invoke(messages)

    logger.info(f"Agent reasoning (attempt {state['attempt']})")
    logger.debug(f"Agent response: {response.content[:200]}...")

    return {
        "messages": [response],
        "prompt_tokens": state.get("prompt_tokens", 0) + cb.prompt_tokens,
        "completion_tokens": state.get("completion_tokens", 0) + cb.completion_tokens,
        "total_cost": state.get("total_cost", 0.0) + cb.total_cost,
    }


def act_node(state: AgentState) -> dict:
    """
    Action execution node: parses LLM output and executes the chosen action.
    """
    last_message = state["messages"][-1]
    content = last_message.content

    # Parse the action from LLM response
    action_data = _parse_agent_action(content)

    if action_data is None:
        return {
            "messages": [HumanMessage(content=(
                "I couldn't parse your response. Please respond with a valid JSON object "
                "containing 'vulnerability_analysis', 'attack_strategy', 'step_by_step_plan', 'action', and the relevant fields. "
                f"Valid actions are: {_valid_actions_text()}."
            ))]
        }

    action = action_data.get("action", "")
    vuln_analysis = action_data.get("vulnerability_analysis", "")
    attack_strategy = action_data.get("attack_strategy", "")
    step_plan = action_data.get("step_by_step_plan", "")
    failure_refl = action_data.get("failure_reflection", "")
    logger.info(f"Agent action: {action} | Strategy: {attack_strategy[:100]}...")

    if action == "analyze_deps" and ABLATION_MODE == "m2":
        result = {
            "messages": [HumanMessage(content=(
                "Dependency analysis tool is disabled in this configuration. "
                "Please proceed directly with `write_poc` or `modify_poc`."
            ))]
        }
    elif action == "analyze_deps":
        result = _handle_analyze_deps(state, action_data)
    elif action == "fetch_interface":
        result = _handle_fetch_interface(state, action_data)
    elif action == "write_poc":
        result = _handle_write_poc(state, action_data)
    elif action == "modify_poc":
        result = _handle_modify_poc(state, action_data)
    else:
        result = {
            "messages": [HumanMessage(content=(
                f"Unknown action: '{action}'. Valid actions are: "
                f"{_valid_actions_text()}."
            ))]
        }

    result["last_vulnerability_analysis"] = vuln_analysis
    result["last_attack_strategy"] = attack_strategy
    result["last_step_by_step_plan"] = step_plan
    result["last_failure_reflection"] = failure_refl
    result["last_action"] = action
    
    # Store intermediate tool actions for the output log
    if action in ["analyze_deps", "fetch_interface"]:
        current_tools = state.get("tool_calls", [])
        result["tool_calls"] = current_tools + [action_data]
        
    return result


def verify_node(state: AgentState) -> dict:
    """
    Verification node: runs forge build, fixes syntax if needed, then runs forge test.
    """
    current_poc = state["current_poc"]
    if not current_poc:
        return {
            "messages": [HumanMessage(content="No PoC code to verify. Please generate one first.")],
        }

    # ─── Fast-Fail Syntax Loop ───
    # Try to compile first. If it fails due to syntax/missing imports, 
    # use a lightweight sub-agent to fix it up to 5 times.
    syntax_attempts = 0
    max_syntax_attempts = 5
    build_passed = False
    
    llm = create_llm()

    while syntax_attempts < max_syntax_attempts:
        write_poc_to_disk(current_poc, str(FOUNDRY_SANDBOX_DIR))
        exit_code, stdout, stderr = forge_runner.build_only(sandbox_dir=FOUNDRY_SANDBOX_DIR)
        
        if exit_code == 0:
            build_passed = True
            logger.info("🛠️ Syntax check passed! Proceeding to EVM execution.")
            break
            
        syntax_attempts += 1
        logger.warning(f"🛠️ Syntax error (attempt {syntax_attempts}/{max_syntax_attempts}). Fixing...")
        
        # Parse the compilation error
        error = trace_parser.parse(stdout, stderr)
        
        syntax_prompt = f"""You are a Solidity syntax fixer.
The following Solidity PoC failed to compile. 

## Source Code:
```solidity
{current_poc}
```

## Compiler Error:
```
{error.reason}
{error.raw_snippet or ""}
```

Provide ONLY the corrected, full Solidity code wrapped in ```solidity ... ```.
Do NOT change the attack logic, ONLY fix the compilation errors (e.g., missing semicolons, undeclared variables, type mismatches, missing imports, wrong interface signatures).
"""
        with get_openai_callback() as cb:
            response = llm.invoke([HumanMessage(content=syntax_prompt)])
            
        state["prompt_tokens"] = state.get("prompt_tokens", 0) + cb.prompt_tokens
        state["completion_tokens"] = state.get("completion_tokens", 0) + cb.completion_tokens
        state["total_cost"] = state.get("total_cost", 0.0) + cb.total_cost
        
        # Extract new code
        import re
        pattern = re.compile(r'```solidity\s*\n(.*?)\n```', re.DOTALL)
        match = pattern.search(response.content)
        if match:
            current_poc = match.group(1)
            state["current_poc"] = current_poc
        else:
            logger.error("Syntax sub-agent failed to output ```solidity blocks")
            break

    if not build_passed:
        logger.error("❌ Failed to resolve syntax errors after max attempts. Giving up on this try.")
        # We fail the main agent attempt if we can't even compile it after 5 tries
        error = trace_parser.parse(stdout, stderr)
        record = AttemptRecord(
            attempt_number=state["attempt"],
            vulnerability_analysis=state.get("last_vulnerability_analysis"),
            attack_strategy=state.get("last_attack_strategy"),
            step_by_step_plan=state.get("last_step_by_step_plan"),
            failure_reflection=state.get("last_failure_reflection"),
            action=state.get("last_action"),
            tool_calls=state.get("tool_calls", []),
            poc_code=current_poc,
            exit_code=-1,
            error=error,
            feedback="Too many syntax errors. " + error.to_feedback(),
            duration_seconds=time.time() - state.get("attempt_start_time", time.time()),
            prompt_tokens=state.get("prompt_tokens", 0),
            completion_tokens=state.get("completion_tokens", 0),
            total_cost=state.get("total_cost", 0.0),
        )
        history = state["attempts_history"] + [record.model_dump()]
        
        new_attempt = state["attempt"] + 1
        if new_attempt > state["max_attempts"]:
            return {
                "messages": [HumanMessage(content=f"❌ FAILED: Max attempts reached due to deep syntax errors.")],
                "attempts_history": history,
                "attempt": new_attempt,
                "status": "failed",
                "tool_calls": [],
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_cost": 0.0,
                "attempt_start_time": time.time(),
            }
            
        return {
            "messages": [HumanMessage(content=f"Compile failed after {max_syntax_attempts} auto-fixes. Error:\n{error.reason}\nRewrite the PoC.")],
            "attempts_history": history,
            "attempt": new_attempt,
            "tool_calls": [],
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_cost": 0.0,
            "attempt_start_time": time.time(),
        }

    # ─── EVM Trace Execution Loop ───
    # Run forge test
    exit_code, stdout, stderr = forge_runner.run(
        sandbox_dir=FOUNDRY_SANDBOX_DIR,
        rpc_url=state["rpc_url"],
        block_number=state.get("block_number"),
    )

    attempt_num = state["attempt"]
    vt_for_evidence = ViolationTarget(**state["violation_target"])
    sink_markers = _sink_markers(vt_for_evidence)
    evidence = trace_parser.collect_evidence(
        stdout=stdout,
        stderr=stderr,
        sink_markers=sink_markers,
        exit_code=exit_code,
    )

    if exit_code == 0:
        if evidence.reached_sink is False:
            error = trace_parser.build_reachability_error(evidence)
            feedback = error.to_feedback()
            logger.warning(f"Attempt {attempt_num} failed CHECKREACH: {error.reason}")
            record = AttemptRecord(
                attempt_number=attempt_num,
                vulnerability_analysis=state.get("last_vulnerability_analysis"),
                attack_strategy=state.get("last_attack_strategy"),
                step_by_step_plan=state.get("last_step_by_step_plan"),
                failure_reflection=state.get("last_failure_reflection"),
                action=state.get("last_action"),
                tool_calls=state.get("tool_calls", []),
                poc_code=current_poc,
                exit_code=exit_code,
                error=error,
                feedback=feedback,
                execution_evidence=evidence,
                duration_seconds=time.time() - state.get("attempt_start_time", time.time()),
                prompt_tokens=state.get("prompt_tokens", 0),
                completion_tokens=state.get("completion_tokens", 0),
                total_cost=state.get("total_cost", 0.0),
            )
            history = state["attempts_history"] + [record.model_dump()]
            new_attempt = attempt_num + 1
            if new_attempt > state["max_attempts"]:
                return {
                    "messages": [HumanMessage(content=f"❌ FAILED: Max attempts reached. Last error: {feedback}")],
                    "attempts_history": history,
                    "attempt": new_attempt,
                    "status": "failed",
                    "current_poc": current_poc,
                    "tool_calls": [],
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_cost": 0.0,
                    "attempt_start_time": time.time(),
                }
            return {
                "messages": [HumanMessage(content=(
                    f"Attempt {attempt_num} executed and passed assertions, but CHECKREACH failed.\n"
                    f"Expected vulnerable sink marker(s): {', '.join(sink_markers)}.\n"
                    f"Relevant trace:\n```\n{evidence.call_trace_excerpt or ''}\n```\n"
                    f"Repair the trace so the {_target_reference()} is reached, while preserving the oracle."
                ))],
                "attempts_history": history,
                "attempt": new_attempt,
                "current_poc": current_poc,
                "tool_calls": [],
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_cost": 0.0,
                "attempt_start_time": time.time(),
            }

        logger.info(f"🎉 Exploit test PASSED on attempt {attempt_num}!")
        record = AttemptRecord(
            attempt_number=attempt_num,
            vulnerability_analysis=state.get("last_vulnerability_analysis"),
            attack_strategy=state.get("last_attack_strategy"),
            step_by_step_plan=state.get("last_step_by_step_plan"),
            failure_reflection=state.get("last_failure_reflection"),
            action=state.get("last_action"),
            poc_code=current_poc,
            exit_code=exit_code,
            execution_evidence=evidence,
            duration_seconds=time.time() - state.get("attempt_start_time", time.time()),
            prompt_tokens=state.get("prompt_tokens", 0),
            completion_tokens=state.get("completion_tokens", 0),
            total_cost=state.get("total_cost", 0.0),
        )
        history = state["attempts_history"] + [record.model_dump()]

        return {
            "messages": [HumanMessage(content="✅ SUCCESS: The exploit test passed! The PoC is valid.")],
            "attempts_history": history,
            "status": "success",
            "current_poc": current_poc,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_cost": 0.0,
            "attempt_start_time": time.time(),
        }

    # Parse the error
    error = trace_parser.parse(stdout, stderr)
    feedback = error.to_feedback()

    logger.warning(f"Attempt {attempt_num} failed: {error.error_type} - {error.reason[:100]}")

    record = AttemptRecord(
        attempt_number=attempt_num,
        vulnerability_analysis=state.get("last_vulnerability_analysis"),
        attack_strategy=state.get("last_attack_strategy"),
        step_by_step_plan=state.get("last_step_by_step_plan"),
        failure_reflection=state.get("last_failure_reflection"),
        action=state.get("last_action"),
        tool_calls=state.get("tool_calls", []),
        poc_code=current_poc,
        exit_code=exit_code,
        error=error,
        feedback=feedback,
        execution_evidence=evidence,
        duration_seconds=time.time() - state.get("attempt_start_time", time.time()),
        prompt_tokens=state.get("prompt_tokens", 0),
        completion_tokens=state.get("completion_tokens", 0),
        total_cost=state.get("total_cost", 0.0),
    )
    history = state["attempts_history"] + [record.model_dump()]

    # Check if max attempts reached
    new_attempt = attempt_num + 1
    if new_attempt > state["max_attempts"]:
        logger.warning(f"Max attempts ({state['max_attempts']}) reached. Giving up.")
        return {
            "messages": [HumanMessage(content=f"❌ FAILED: Max attempts reached. Last error: {feedback}")],
            "attempts_history": history,
            "attempt": new_attempt,
            "status": "failed",
            "current_poc": current_poc,
            "tool_calls": [],
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_cost": 0.0,
            "attempt_start_time": time.time(),
        }

    # Generate feedback for the agent
    feedback_msg = (
        f"Attempt {attempt_num} failed.\n\n"
        f"**Error Type**: {error.error_type.value}\n"
        f"**PoCForge Failure Stage**: {error.failure_stage or 'unknown'}\n"
        f"**Reached Sink**: {error.reached_sink if error.reached_sink is not None else 'unknown'}\n"
        f"**Oracle Outcome**: {error.oracle_outcome or 'unknown'}\n"
        f"**Feedback**: {feedback}\n"
    )
    if error.raw_snippet:
        feedback_msg += f"\n**Relevant Log Snippet**:\n```\n{error.raw_snippet}\n```\n"

    feedback_msg += (
        "\nRepair policy: compile failures should only change syntax/interfaces; trace/core failures should revise "
        "preparation traces, action parameters, resources, or environment state; oracle failures should preserve "
        f"the reached sink and modify only validation instrumentation unless execution evidence contradicts the {_target_reference()}.\n"
        f"\nPlease output a `modify_poc` action with corrected phase code. "
        f"You have {state['max_attempts'] - attempt_num} attempts remaining."
    )

    return {
        "messages": [HumanMessage(content=feedback_msg)],
        "attempts_history": history,
        "attempt": new_attempt,
        "current_poc": current_poc,
        "tool_calls": [],
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_cost": 0.0,
        "attempt_start_time": time.time(),
    }


# ═══════════════════════════════════════════════════════════════════════
# Action Handlers
# ═══════════════════════════════════════════════════════════════════════

def _handle_analyze_deps(state: AgentState, action_data: dict) -> dict:
    """Handle the analyze_deps action."""
    target_func = action_data.get("target_function", "")
    if not target_func:
        return {
            "messages": [HumanMessage(content="Please specify a target_function to analyze.")]
        }

    source_code = state["source_code"]
    contract_name = state["contract_info"].get("contract_name", None)

    deps = get_function_dependencies(
        source_code=source_code,
        target_function=target_func,
        contract_name=contract_name,
    )

    formatted = format_dependencies_for_agent(deps)

    return {
        "messages": [HumanMessage(content=f"Dependency analysis results:\n\n{formatted}\n\nNow write the exploit.")]
    }


def _handle_fetch_interface(state: AgentState, action_data: dict) -> dict:
    """Handle the fetch_interface action to grab external ABIs."""
    address = action_data.get("contract_address", "")
    name = action_data.get("contract_name", "ExternalContract")
    
    if not address:
        return {
            "messages": [HumanMessage(content="Please provide a valid 'contract_address' to fetch.")]
        }

    try:
        logger.info(f"Agent requested to fetch dynamic interface for {name} ({address})")
        
        # We assume BSC here for typical targets, but it could be expanded
        info = fetch_contract_source(address=address, chain="bsc")
        
        if not info.get("abi"):
            return {
                "messages": [HumanMessage(content=f"Could not find ABI for address {address}. It might not be verified or reachable.")]
            }
            
        interface_code = generate_solidity_interface(name, info["abi"])
        
        response_msg = (
            f"Successfully fetched interface for {name} ({address}):\n\n```solidity\n{interface_code}\n```\n\n"
            f"You can now use `modify_poc` to inject this interface into your exploit using the `add_interface` JSON key."
        )
        return {
            "messages": [HumanMessage(content=response_msg)]
        }
    except Exception as e:
        logger.error(f"Failed to fetch dynamic interface: {e}")
        return {
            "messages": [HumanMessage(content=f"Failed to fetch interface for {address}: {str(e)}")]
        }


def _handle_write_poc(state: AgentState, action_data: dict) -> dict:
    """Handle the write_poc action — initial PoC generation."""
    vt = ViolationTarget(**state["violation_target"])

    trace_init = action_data.get("trace_init", action_data.get("setup_code", ""))
    trace_prepare = action_data.get("trace_prepare", "")
    trace_exploit = action_data.get("trace_exploit", action_data.get("exploit_code", "// TODO: exploit steps"))
    exploit_code = _join_trace_phases(trace_prepare, trace_exploit)
    setup_code = trace_init
    interface_defs = action_data.get("interface_definitions", "")
    state_vars = action_data.get("state_variables", "")
    helper_funcs = action_data.get("helper_functions", "")

    # Generate interface from ABI if not provided
    if not interface_defs and state["contract_info"].get("abi"):
        interface_defs = generate_solidity_interface(
            state["contract_info"].get("contract_name", "Target"),
            state["contract_info"]["abi"],
        )

    # Add IERC20 interface if needed
    oracle = vt.oracle_verification
    if oracle.economic_check and oracle.economic_check.target_token != "NATIVE":
        if "IERC20" not in interface_defs:
            ierc20 = (
                "interface IERC20 {\n"
                "    function balanceOf(address account) external view returns (uint256);\n"
                "    function transfer(address to, uint256 amount) external returns (bool);\n"
                "    function approve(address spender, uint256 amount) external returns (bool);\n"
                "    function transferFrom(address from, address to, uint256 amount) external returns (bool);\n"
                "    function totalSupply() external view returns (uint256);\n"
                "}\n"
            )
            interface_defs = ierc20 + "\n" + interface_defs

    poc_code = assemble_poc(
        violation_target=vt,
        exploit_sequence=exploit_code,
        setup_code=setup_code,
        interface_definitions=interface_defs,
        state_variables=state_vars,
        helper_functions=helper_funcs,
    )

    return {
        "messages": [HumanMessage(content="PoC assembled. Proceeding to verification.")],
        "current_poc": poc_code,
    }


def _handle_modify_poc(state: AgentState, action_data: dict) -> dict:
    """Handle the modify_poc action — incremental modification."""
    existing = state["current_poc"]
    if not existing:
        # No existing PoC, fall back to write_poc
        return _handle_write_poc(state, action_data)

    modifications = {}
    trace_prepare = action_data.get("trace_prepare")
    trace_exploit = action_data.get("trace_exploit")
    if trace_prepare is not None or trace_exploit is not None:
        modifications["exploit_code"] = _join_trace_phases(trace_prepare or "", trace_exploit or "")
    elif "exploit_code" in action_data:
        modifications["exploit_code"] = action_data["exploit_code"]
    if "trace_init" in action_data:
        modifications["setup_code"] = action_data["trace_init"]
    if "setup_code" in action_data:
        modifications["setup_code"] = action_data["setup_code"]
    if "add_state_variables" in action_data:
        modifications["add_state_variables"] = action_data["add_state_variables"]
    if "add_helper_functions" in action_data:
        modifications["add_helper_functions"] = action_data["add_helper_functions"]
    if "add_interface" in action_data:
        modifications["add_interface"] = action_data["add_interface"]

    if not modifications:
        # If only exploit_code is missing but there's thought, try to extract
        return {
            "messages": [HumanMessage(content="No modifications specified. Please provide 'exploit_code' or other fields to modify.")]
        }

    updated = update_poc(existing, modifications)

    return {
        "messages": [HumanMessage(content="PoC modified. Proceeding to verification.")],
        "current_poc": updated,
    }


def _join_trace_phases(trace_prepare: str, trace_exploit: str) -> str:
    """Join phase-labeled trace snippets into a single test body."""
    parts = []
    if trace_prepare.strip():
        parts.append("// trace_prepare: satisfy prerequisite/resource/environment debt")
        parts.append(trace_prepare.strip())
    if trace_exploit.strip():
        parts.append("// trace_exploit: trigger vulnerable sink and realize impact")
        parts.append(trace_exploit.strip())
    return "\n".join(parts) if parts else "// TODO: exploit steps"


def _sink_markers(vt: ViolationTarget) -> list[str]:
    """Markers used for CHECKREACH over Forge traces."""
    if ABLATION_MODE == "m1":
        return []

    markers = []
    trigger = vt.trigger_context or {}
    if isinstance(trigger, dict) and trigger.get("function"):
        markers.append(str(trigger["function"]))

    sink = vt.vulnerable_sink or ""
    call_match = re.search(r'\b([A-Za-z_]\w*)\s*\(', sink)
    if call_match:
        markers.append(call_match.group(1))
    elif re.fullmatch(r'[A-Za-z_]\w*', sink):
        markers.append(sink)

    return list(dict.fromkeys(markers))


# ═══════════════════════════════════════════════════════════════════════
# Router (Edge Conditions)
# ═══════════════════════════════════════════════════════════════════════

def should_verify(state: AgentState) -> str:
    """Route after act: go to verify if PoC was written, otherwise back to reason."""
    last_msg = state["messages"][-1].content if state["messages"] else ""
    if "Proceeding to verification" in last_msg:
        return "verify"
    return "reason"


def after_verify(state: AgentState) -> str:
    """Route after verify: end if success/failed, otherwise back to reason."""
    status = state.get("status", "running")
    if status in ("success", "failed"):
        return END
    return "reason"


# ═══════════════════════════════════════════════════════════════════════
# Graph Construction
# ═══════════════════════════════════════════════════════════════════════

def build_agent_graph() -> StateGraph:
    """Build the LangGraph agent state graph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("reason", reason_node)
    graph.add_node("act", act_node)
    graph.add_node("verify", verify_node)

    # Set entry point
    graph.set_entry_point("reason")

    # Add edges
    graph.add_edge("reason", "act")
    graph.add_conditional_edges("act", should_verify, {"verify": "verify", "reason": "reason"})
    graph.add_conditional_edges("verify", after_verify, {END: END, "reason": "reason"})

    return graph


def run_agent(
    violation_target: ViolationTarget,
    source_code: str,
    contract_info: dict,
    rpc_url: str,
    block_number: Optional[int] = None,
    max_attempts: Optional[int] = None,
) -> PipelineResult:
    """
    Run the ReAct agent loop to generate and validate an exploit PoC.

    Args:
        violation_target: Structured vulnerability target from Module A.
        source_code: Fetched contract source code.
        contract_info: Contract metadata from source_fetcher.
        rpc_url: RPC URL for fork-mode testing.
        block_number: Optional block number to fork from.
        max_attempts: Maximum number of attempts (default: config.MAX_ATTEMPTS).

    Returns:
        PipelineResult with status, final PoC code, and attempt history.
    """
    max_attempts = max_attempts or MAX_ATTEMPTS

    # Build initial user message
    vt_dict = violation_target.model_dump()
    initial_prompt = _build_initial_prompt(violation_target, source_code, contract_info)

    initial_state: AgentState = {
        "messages": [
            SystemMessage(content=_agent_system_prompt()),
            HumanMessage(content=initial_prompt),
        ],
        "violation_target": vt_dict,
        "source_code": source_code,
        "contract_info": contract_info,
        "current_poc": "",
        "attempt": 1,
        "max_attempts": max_attempts,
        "rpc_url": rpc_url,
        "block_number": block_number,
        "attempts_history": [],
        "tool_calls": [],
        "status": "running",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_cost": 0.0,
        "attempt_start_time": time.time(),
    }

    # Build and compile the graph
    graph = build_agent_graph()
    app = graph.compile()

    # Run the agent
    logger.info(f"Starting agent loop for {violation_target.target_address} "
                f"(finding #{violation_target.finding_id}, max_attempts={max_attempts})")

    try:
        final_state = app.invoke(initial_state)
    except Exception as e:
        logger.error(f"Agent loop crashed: {e}")
        return PipelineResult(
            project_id=contract_info.get("contract_name", "unknown"),
            target_address=violation_target.target_address,
            finding_id=violation_target.finding_id,
            status=PipelineStatus.ERROR,
            error_message=str(e),
        )

    # Build result
    status = PipelineStatus.SUCCESS if final_state["status"] == "success" else PipelineStatus.FAILED
    attempts = [AttemptRecord(**a) for a in final_state["attempts_history"]]

    return PipelineResult(
        project_id=contract_info.get("contract_name", "unknown"),
        target_address=violation_target.target_address,
        finding_id=violation_target.finding_id,
        status=status,
        violation_target=violation_target,
        final_poc_code=final_state.get("current_poc", ""),
        attempts=attempts,
        total_attempts=len(attempts),
    )


def _build_initial_prompt(
    violation_target: ViolationTarget,
    source_code: str,
    contract_info: dict,
) -> str:
    """Build the initial prompt for the agent."""
    vt = violation_target

    category_desc = (
        "💰 ECONOMIC — The oracle checks if the attacker's balance increased."
        if vt.violation_category == ViolationCategory.ECONOMIC
        else "🔧 LOGIC — The oracle checks if a contract state was tampered."
    )

    oracle_desc = ""
    if vt.oracle_verification.economic_check:
        ec = vt.oracle_verification.economic_check
        oracle_desc = (
            f"  - Token: {ec.target_token}\n"
            f"  - Victim: {ec.victim_contract}\n"
            f"  - Check: {ec.condition}"
        )
    if vt.oracle_verification.logic_check:
        lc = vt.oracle_verification.logic_check
        logic_desc = (
            f"  - Variable: {lc.target_variable}\n"
            f"  - Operator: {lc.operator}\n"
            f"  - Expected: {lc.expected_value}"
        )
        oracle_desc = f"{oracle_desc}\n{logic_desc}".strip() if oracle_desc else logic_desc

    ves_sections = ""
    if ABLATION_MODE != "m1":
        if vt.preconditions:
            precond_desc = "\n".join(
                f"  - [{p.type}] {p.description}" for p in vt.preconditions
            )
        else:
            precond_desc = "  None specified"
        exploit_hint = vt.exploit_hint or "No hint provided. Analyze the source code."
        ves_sections = f"""
### Preconditions
{precond_desc}

### VES Fields
- Vulnerable Sink (κ): {vt.vulnerable_sink or 'Not specified'}
- Intended Impact (φ): {vt.intended_impact or 'Not specified'}
- Trigger Context (Λ): {json.dumps(vt.trigger_context or {}, ensure_ascii=False)}
- Code Preconditions (Π_code): {json.dumps([p.model_dump() for p in vt.code_preconditions], ensure_ascii=False)}
- Environment Preconditions (Π_env): {json.dumps([p.model_dump() for p in vt.environment_preconditions], ensure_ascii=False)}
- Evidence (E): {json.dumps(vt.evidence, ensure_ascii=False)}

### Exploit Hint
{exploit_hint}
"""

    edg_block = ""
    if ABLATION_MODE not in {"m1", "m2"}:
        edg = build_exploit_dependency_graph(violation_target, source_code, contract_info)
        edg_block = f"\n{format_edg_for_agent(edg)}\n"

    if ABLATION_MODE == "m2":
        deps_instruction = (
            "The `analyze_deps` action is unavailable. "
            "Do NOT call it. Generate PoC directly via `write_poc`/`modify_poc`."
        )
    else:
        deps_instruction = (
            "If you need to understand function dependencies first, use `analyze_deps`."
        )

    prompt = f"""## Exploit Target

- **Contract Address**: `{vt.target_address}`
- **Contract Name**: {contract_info.get('contract_name', 'Unknown')}
- **Vulnerability**: {vt.vulnerability_type}
- **Category**: {category_desc}

### Oracle Verification
{oracle_desc}
{ves_sections}{edg_block}

## Contract Source Code (Distilled Context)
```solidity
{strip_solidity_comments(source_code)}
```

## ABI Functions Available
{_format_abi_summary(contract_info.get('abi', []))}

---

Please analyze this vulnerability and produce a working exploit.
Start by outputting a `write_poc` action with `trace_init`, `trace_prepare`, and `trace_exploit`.
{deps_instruction}
"""
    return prompt


def _format_abi_summary(abi: list) -> str:
    """Format ABI as a concise function list."""
    functions = [item for item in abi if item.get("type") == "function"]
    if not functions:
        return "No ABI available."

    lines = []
    for f in functions[:30]:  # Limit to 30 functions
        inputs = ", ".join(
            f"{i.get('type', '?')} {i.get('name', '')}" for i in f.get("inputs", [])
        )
        outputs = ", ".join(
            f"{o.get('type', '?')}" for o in f.get("outputs", [])
        )
        mutability = f.get("stateMutability", "")
        sig = f"  - `{f['name']}({inputs})` → `({outputs})` [{mutability}]"
        lines.append(sig)

    return "\n".join(lines)


def _parse_agent_action(content: str) -> Optional[dict]:
    """Parse the agent's response to extract the action JSON."""
    import re

    # Try to find JSON in code block
    pattern = re.compile(r'```(?:json)?\s*\n(.*?)\n```', re.DOTALL)
    match = pattern.search(content)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object
    pattern = re.compile(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', re.DOTALL)
    for match in pattern.finditer(content):
        try:
            data = json.loads(match.group(0))
            if "action" in data:
                return data
        except json.JSONDecodeError:
            continue

    # Last resort: try the entire content as JSON
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    return None
