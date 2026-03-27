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

    def to_feedback(self) -> str:
        """Convert error to actionable feedback prompt for the agent."""
        if self.error_type == ErrorType.COMPILE_ERROR:
            return (
                f"编译失败：{self.reason}。"
                f"请检查语法和导入是否正确。位置: {self.location or '未知'}"
            )
        elif self.error_type == ErrorType.ASSERTION_FAILED:
            return (
                f"执行未回滚，但断言失败：{self.reason}。"
                f"请检查攻击逻辑是否完整，或计算的参数是否正确。"
            )
        elif self.error_type == ErrorType.EVM_REVERT:
            reason_lower = self.reason.lower()
            if "transfer amount exceeds balance" in reason_lower:
                return f"资金不足发生回滚。请在调用前使用 `deal()` 注入代币。原因: {self.reason}"
            elif "is not the owner" in reason_lower or "ownable" in reason_lower:
                return f"遭遇权限锁。请检查是否需要 `vm.prank` 伪造身份。原因: {self.reason}"
            else:
                return f"EVM Revert: {self.reason}。请调整参数或调用路径。"
        else:
            return f"未知错误: {self.reason}。请检查代码。"


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
