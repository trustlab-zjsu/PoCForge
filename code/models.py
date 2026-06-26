"""
LogicGap Data Models
Pydantic models for all data structures used across the pipeline.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════
# Input Models — matching the .pdf.json format from FORGE-Artifacts
# ═══════════════════════════════════════════════════════════════════════

class ProjectInfo(BaseModel):
    """Contract metadata from the .pdf.json file."""
    url: Optional[str] = None
    commit_id: Optional[str] = None
    address: str
    chain: str = "bsc"
    compiler_version: list[str] = Field(default_factory=list)
    project_path: Optional[dict[str, str]] = None


class VulnerabilityFinding(BaseModel):
    """A single vulnerability finding from the audit report."""
    id: int
    category: dict[str, list[str]] = Field(default_factory=dict)
    title: str
    description: str
    severity: str = "low"
    location: Optional[str] = None


class TargetInput(BaseModel):
    """Complete input parsed from a .pdf.json file."""
    path: Optional[str] = None
    project_info: ProjectInfo
    findings: list[VulnerabilityFinding] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
# Module A Output — Violation Target (structured by LLM)
# ═══════════════════════════════════════════════════════════════════════

class ViolationCategory(str, Enum):
    ECONOMIC = "ECONOMIC"
    LOGIC = "LOGIC"


class Precondition(BaseModel):
    """A precondition for the exploit."""
    type: str = Field(description="e.g., 'token_balance', 'role', 'state'")
    description: str = Field(description="Human-readable description of the precondition")
    token_address: Optional[str] = None
    min_amount: Optional[str] = None
    source: Optional[str] = Field(
        default=None,
        description="Evidence source: report, code, environment, or execution"
    )
    status: Optional[str] = Field(
        default=None,
        description="Grounding status: confirmed, environment, unsupported, or inferred"
    )


class EconomicCheck(BaseModel):
    """Oracle check for economic exploits (profit verification)."""
    target_token: str = Field(description="Token address, or 'NATIVE' for native currency")
    victim_contract: str = Field(description="Address of the victim contract")
    condition: str = Field(default="attacker_balance_increased")


class LogicCheck(BaseModel):
    """Oracle check for logic exploits (state tampering verification)."""
    target_variable: str = Field(description="Solidity expression to check, e.g., 'contract.owner()'")
    operator: str = Field(description="Comparison operator: ==, >, <, !=")
    expected_value: str = Field(description="Expected value after exploit")


class OracleVerification(BaseModel):
    """Verification oracle — only one of economic_check or logic_check should be set."""
    economic_check: Optional[EconomicCheck] = None
    logic_check: Optional[LogicCheck] = None


class ViolationTarget(BaseModel):
    """Module A output: structured exploit target specification."""
    target_address: str = Field(description="Address of the target contract")
    vulnerability_type: str = Field(description="Short name of the vulnerability")
    violation_category: ViolationCategory
    finding_id: int = Field(description="ID of the original finding that this target addresses")
    preconditions: list[Precondition] = Field(default_factory=list)
    oracle_verification: OracleVerification
    exploit_hint: Optional[str] = Field(
        default=None,
        description="High-level hint for the agent about the exploit strategy"
    )
    vulnerable_sink: Optional[str] = Field(
        default=None,
        description="VES κ: concrete vulnerable function, call, or statement to reach"
    )
    intended_impact: Optional[str] = Field(
        default=None,
        description="VES phi: target security impact to demonstrate"
    )
    code_preconditions: list[Precondition] = Field(
        default_factory=list,
        description="VES Pi_code: code-level guards, roles, state predicates, and call constraints"
    )
    environment_preconditions: list[Precondition] = Field(
        default_factory=list,
        description="VES Pi_env: fork, market, resource, oracle, or attacker-controlled environment assumptions"
    )
    trigger_context: Optional[dict] = Field(
        default=None,
        description="VES Lambda: actor, function, ordering, and parameters that activate the sink"
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="VES E: report and program facts supporting the chosen sink, preconditions, and oracle"
    )


# ═══════════════════════════════════════════════════════════════════════
# Module C Output — Trace Parser Results
# ═══════════════════════════════════════════════════════════════════════

class ErrorType(str, Enum):
    COMPILE_ERROR = "COMPILE_ERROR"
    ASSERTION_FAILED = "ASSERTION_FAILED"
    EVM_REVERT = "EVM_REVERT"
    UNKNOWN = "UNKNOWN"


class TraceError(BaseModel):
    """Structured error information extracted from Forge output."""
    error_type: ErrorType
    reason: str = Field(description="Human-readable error reason")
    location: Optional[str] = Field(default=None, description="File:line if available")
    raw_snippet: Optional[str] = Field(
        default=None,
        description="Relevant raw log snippet (trimmed)"
    )
    failure_stage: Optional[str] = Field(
        default=None,
        description="PoCForge repair stage: compile, trace, core, oracle, semantic, or unknown"
    )
    reached_sink: Optional[bool] = Field(
        default=None,
        description="Whether execution evidence suggests the vulnerable sink was reached"
    )
    oracle_outcome: Optional[str] = Field(
        default=None,
        description="Structured oracle outcome used for feedback-driven repair"
    )

    def to_feedback(self) -> str:
        """Convert error to actionable feedback prompt for the agent."""
        if self.error_type == ErrorType.COMPILE_ERROR:
            return (
                f"Compilation failed: {self.reason}. "
                f"Check Solidity syntax and imports. Location: {self.location or 'unknown'}"
            )
        elif self.error_type == ErrorType.ASSERTION_FAILED:
            return (
                f"Execution did not revert, but an assertion failed: {self.reason}. "
                "Check whether the exploit logic is complete and whether computed parameters are correct."
            )
        elif self.error_type == ErrorType.EVM_REVERT:
            reason_lower = self.reason.lower()
            if "transfer amount exceeds balance" in reason_lower:
                return f"Reverted due to insufficient balance. Use `deal()` to inject tokens before the call. Reason: {self.reason}"
            elif "is not the owner" in reason_lower or "ownable" in reason_lower:
                return f"Reverted due to an ownership or permission check. Check whether `vm.prank` is needed. Reason: {self.reason}"
            else:
                return f"EVM revert: {self.reason}. Adjust the call path, parameters, resources, or environment state."
        else:
            return f"Unknown error: {self.reason}. Inspect the PoC code and execution logs."


class ExecutionEvidence(BaseModel):
    """Execution evidence Gamma collected from Forge output."""
    compiled: bool = False
    executed: bool = False
    reached_sink: Optional[bool] = None
    sink_markers: list[str] = Field(default_factory=list)
    matched_sink_markers: list[str] = Field(default_factory=list)
    oracle_passed: Optional[bool] = None
    call_trace_excerpt: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════
# Pipeline Result — Final Output
# ═══════════════════════════════════════════════════════════════════════

from typing import Optional, Union

class AttemptRecord(BaseModel):
    """Record of a single attempt in the pipeline."""
    attempt_number: int
    vulnerability_analysis: Optional[Union[str, list[str]]] = None
    attack_strategy: Optional[Union[str, list[str]]] = None
    step_by_step_plan: Optional[Union[str, list[str]]] = None
    failure_reflection: Optional[Union[str, list[str]]] = Field(default=None, description="Agent's self-reflection on why the previous attempt failed")
    action: Optional[str] = None
    tool_calls: list[dict] = Field(default_factory=list, description="Record of intermediate actions taken (e.g., analyze_deps, fetch_interface) before PoC compilation")
    poc_code: str
    exit_code: int
    error: Optional[TraceError] = None
    feedback: Optional[str] = None
    execution_evidence: Optional[ExecutionEvidence] = None
    
    # Telemetry metrics
    duration_seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost: float = 0.0


class PipelineStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ERROR = "ERROR"


class PipelineResult(BaseModel):
    """Final result from the pipeline for one target."""
    project_id: str
    target_address: str
    finding_id: int
    status: PipelineStatus
    violation_target: Optional[ViolationTarget] = None
    final_poc_code: Optional[str] = None
    attempts: list[AttemptRecord] = Field(default_factory=list)
    total_attempts: int = 0
    error_message: Optional[str] = None
    
    # Global Telemetry
    total_duration_seconds: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost: float = 0.0
