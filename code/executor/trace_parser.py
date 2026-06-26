"""
Module C: Trace Parser
Multi-level regex parser for Forge -vvvv output.
Extracts structured error information from compile errors, assertion failures, and EVM reverts.
"""

import re
import logging
from typing import Optional

from core.models import ExecutionEvidence, TraceError, ErrorType

logger = logging.getLogger(__name__)


def collect_evidence(
    stdout: str,
    stderr: str = "",
    sink_markers: Optional[list[str]] = None,
    exit_code: int = 0,
) -> ExecutionEvidence:
    """Collect execution evidence Gamma from Forge output."""
    combined = stdout + "\n" + stderr
    sink_markers = [m for m in (sink_markers or []) if m]
    matched = []
    combined_lower = combined.lower()
    for marker in sink_markers:
        if marker.lower() in combined_lower:
            matched.append(marker)

    trace_lines = [
        line for line in combined.splitlines()
        if "├─" in line or "└─" in line or "│" in line or "[PASS]" in line or "[FAIL" in line
    ]
    return ExecutionEvidence(
        compiled="Compiler run failed" not in combined and "compiler run failed" not in combined_lower,
        executed=exit_code == 0 or bool(trace_lines),
        reached_sink=bool(matched) if sink_markers else None,
        sink_markers=sink_markers,
        matched_sink_markers=matched,
        oracle_passed=exit_code == 0,
        call_trace_excerpt="\n".join(trace_lines[-20:]) if trace_lines else _truncate(combined, 800),
    )


def build_reachability_error(evidence: ExecutionEvidence) -> TraceError:
    """Create a structured failure descriptor for CHECKREACH failures."""
    markers = ", ".join(evidence.sink_markers) or "not specified"
    return TraceError(
        error_type=ErrorType.ASSERTION_FAILED,
        reason=f"Vulnerable sink was not observed in execution trace. Expected marker(s): {markers}",
        failure_stage="trace",
        reached_sink=False,
        oracle_outcome="impact_oracle_passed_but_sink_unconfirmed",
        raw_snippet=evidence.call_trace_excerpt,
    )


def parse(stdout: str, stderr: str = "") -> TraceError:
    """
    Parse Forge test output and extract structured error information.

    Parsing priority (checked in order):
    1. Compilation errors (from stderr or stdout)
    2. Assertion failures (test ran but assertion failed)
    3. EVM Reverts (runtime revert with reason)
    4. Unknown errors

    Args:
        stdout: Standard output from forge test.
        stderr: Standard error from forge test.

    Returns:
        TraceError with structured error information.
    """
    combined = stdout + "\n" + stderr

    # ─── Level 1: Compilation Errors ──────────────────────────────────
    compile_error = _parse_compile_error(combined)
    if compile_error:
        return compile_error

    # ─── Level 2: Assertion Failures ──────────────────────────────────
    assertion_error = _parse_assertion_failure(combined)
    if assertion_error:
        return assertion_error

    # ─── Level 3: EVM Reverts ─────────────────────────────────────────
    revert_error = _parse_evm_revert(combined)
    if revert_error:
        return revert_error

    # ─── Level 4: Unknown ────────────────────────────────────────────
    return TraceError(
        error_type=ErrorType.UNKNOWN,
        reason="Unable to parse specific error from forge output",
        failure_stage="unknown",
        raw_snippet=_truncate(combined, 500),
    )


def _parse_compile_error(output: str) -> Optional[TraceError]:
    """
    Detect and parse compilation errors.

    Patterns:
    - "Compiler run failed:"
    - "Error (XXXX):" with solidity error codes
    - "TypeError:", "DeclarationError:", "ParserError:" etc.
    """
    # Check for compiler run failure marker
    if "Compiler run failed" not in output and "compiler run failed" not in output.lower():
        return None

    logger.debug("Detected compilation error")

    # Try to extract specific error details
    # Pattern: Error (XXXX): description
    # --> path/file.sol:line:col
    error_pattern = re.compile(
        r'(Error|TypeError|DeclarationError|ParserError|SyntaxError)\s*'
        r'(?:\((\d+)\))?\s*:\s*(.+?)(?:\n|$)'
        r'(?:\s*-->\s*(.+?)(?:\n|$))?',
        re.MULTILINE
    )

    match = error_pattern.search(output)
    if match:
        error_kind = match.group(1)
        error_code = match.group(2) or ""
        error_msg = match.group(3).strip()
        location = match.group(4).strip() if match.group(4) else None

        reason = f"{error_kind}"
        if error_code:
            reason += f" ({error_code})"
        reason += f": {error_msg}"

        return TraceError(
            error_type=ErrorType.COMPILE_ERROR,
            reason=reason,
            location=location,
            failure_stage="compile",
            raw_snippet=_extract_context(output, match.start(), 300),
        )

    # Fallback: extract any line after "Compiler run failed"
    fail_idx = output.lower().find("compiler run failed")
    context = output[fail_idx:fail_idx + 500] if fail_idx >= 0 else output[:500]

    return TraceError(
        error_type=ErrorType.COMPILE_ERROR,
        reason="Compiler run failed (details in raw_snippet)",
        failure_stage="compile",
        raw_snippet=_truncate(context, 500),
    )


def _parse_assertion_failure(output: str) -> Optional[TraceError]:
    """
    Detect and parse assertion failures.

    Patterns:
    - "[FAIL. Reason: reason_string]"
    - "Assertion failed" variants
    """
    # Primary pattern: [FAIL. Reason: ...]
    fail_pattern = re.compile(
        r'\[FAIL\.\s*Reason:\s*(.+?)\]',
        re.IGNORECASE
    )

    match = fail_pattern.search(output)
    if match:
        reason = match.group(1).strip()
        logger.debug(f"Detected assertion failure: {reason}")

        return TraceError(
            error_type=ErrorType.ASSERTION_FAILED,
            reason=reason,
            failure_stage=_classify_assertion_stage(reason),
            reached_sink=True,
            oracle_outcome="failed",
            raw_snippet=_extract_context(output, match.start(), 400),
        )

    # Secondary pattern: standalone assertion messages
    assert_pattern = re.compile(
        r'(?:assertion|assert\w*)\s+(?:failed|violation)',
        re.IGNORECASE
    )
    match = assert_pattern.search(output)
    if match:
        return TraceError(
            error_type=ErrorType.ASSERTION_FAILED,
            reason="Assertion failed (no specific reason extracted)",
            failure_stage="oracle",
            reached_sink=True,
            oracle_outcome="failed",
            raw_snippet=_extract_context(output, match.start(), 400),
        )

    return None


def _parse_evm_revert(output: str) -> Optional[TraceError]:
    """
    Detect and parse EVM revert errors from the execution trace.

    Strategy: find the deepest revert in the call stack for the most
    specific error reason.

    Patterns:
    - "├─ [Revert] reason"  or  "└─ [Revert] reason"
    - "Panic(uint256): 0x11 (Arithmetic overflow)"
    - Custom error selectors
    - "revert: reason"
    """
    # Collect all revert occurrences with their positions (depth)
    revert_entries = []

    # Pattern 1: Trace tree revert lines
    # e.g., "    │   │   └─ ← [Revert] ERC20: transfer amount exceeds balance"
    trace_revert = re.compile(
        r'\[Revert\]\s*(.+?)$',
        re.MULTILINE
    )
    for m in trace_revert.finditer(output):
        reason = m.group(1).strip()
        # Estimate depth from beginning of line
        line_start = output.rfind('\n', 0, m.start()) + 1
        depth = m.start() - line_start
        revert_entries.append((depth, reason, m.start(), line_start))

    # Pattern 2: Panic errors
    panic_pattern = re.compile(
        r'Panic\(.*?\)(?::\s*(.+?))?(?:\n|$)',
        re.MULTILINE
    )
    for m in panic_pattern.finditer(output):
        reason = m.group(0).strip()
        # Estimate depth from indentation
        line_start = output.rfind('\n', 0, m.start()) + 1
        indent = m.start() - line_start
        revert_entries.append((indent, reason, m.start(), line_start))

    # Pattern 3: Simple revert reason (only for lines NOT already matched by [Revert])
    simple_revert = re.compile(
        r'(?:revert|reverted)\s*(?:with\s+reason\s+string\s+)?[\'"]?(.+?)[\'"]?\s*$',
        re.MULTILINE | re.IGNORECASE
    )
    for m in simple_revert.finditer(output):
        # Skip lines that contain [Revert] (already handled by Pattern 1)
        line_start = output.rfind('\n', 0, m.start()) + 1
        line_end = output.find('\n', m.end())
        if line_end == -1:
            line_end = len(output)
        full_line = output[line_start:line_end]
        if '[Revert]' in full_line:
            continue

        reason = m.group(1).strip()
        if reason and len(reason) < 200:
            indent = m.start() - line_start
            revert_entries.append((indent, reason, m.start(), line_start))

    # Pattern 4: Check for [FAIL] without specific assertion (could be a revert-based failure)
    fail_revert = re.compile(
        r'\[FAIL\.\s*Reason:\s*(?:EvmError:\s*)?Revert\]',
        re.IGNORECASE
    )
    if fail_revert.search(output) and not revert_entries:
        # Try to find the revert reason from the trace
        return TraceError(
            error_type=ErrorType.EVM_REVERT,
            reason="EVM Revert (no specific reason in trace)",
            failure_stage="trace",
            reached_sink=False,
            raw_snippet=_truncate(output, 500),
        )

    if not revert_entries:
        return None

    # Select the deepest revert (most specific error) by looking at identation/depth
    revert_entries.sort(key=lambda x: x[0], reverse=True)
    depth, reason, pos, line_start = revert_entries[0]

    logger.debug(f"Detected EVM revert (deepest): {reason}")
    
    # --- Dynamic Trace Slicing ---
    # Extract the N lines BEFORE the revert to show the exact calls that led to it.
    trace_lines = output[:pos].splitlines()
    # Take up to 10 previous lines, filtering out empty ones
    preceding_calls = [line for line in trace_lines[-15:] if "├─" in line or "└─" in line or "│" in line]
    sliced_trace_context = "\n".join(preceding_calls[-8:])  # keep the most immediate 8 steps
    
    # We append the actual revert reason to the end of the slice
    sliced_trace_context += f"\n👉 [Revert Occurred Here]: {reason}"

    return TraceError(
        error_type=ErrorType.EVM_REVERT,
        reason=reason,
        failure_stage=_classify_revert_stage(reason),
        reached_sink=False,
        raw_snippet=sliced_trace_context,
    )


def _classify_assertion_stage(reason: str) -> str:
    lowered = reason.lower()
    if any(term in lowered for term in ("economic exploit failed", "logic exploit failed", "assertion failed")):
        return "oracle"
    if any(term in lowered for term in ("manual verification", "unknown operator")):
        return "semantic"
    return "core"


def _classify_revert_stage(reason: str) -> str:
    lowered = reason.lower()
    if any(term in lowered for term in ("insufficient", "exceeds balance", "transfer amount", "allowance")):
        return "core"
    if any(term in lowered for term in ("ownable", "owner", "admin", "role", "forbidden", "unauthorized")):
        return "core"
    if any(term in lowered for term in ("expired", "deadline", "invalid path", "pair", "liquidity", "reserve")):
        return "trace"
    if any(term in lowered for term in ("assert", "oracle")):
        return "oracle"
    return "trace"


def _extract_context(text: str, position: int, max_chars: int = 300) -> str:
    """Extract surrounding context around a position in text."""
    half = max_chars // 2
    start = max(0, position - half)
    end = min(len(text), position + half)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def _truncate(text: str, max_chars: int = 500) -> str:
    """Truncate text to max_chars."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."
