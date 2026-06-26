"""
Exploit Dependency Graph helpers.

This module implements a lightweight, deterministic EDG representation that
matches PoCForge's planning interface: unresolved reachability, resource,
environment, and impact debts plus dependency-relevant admissible actions.
It is intentionally prompt-oriented rather than a full graph database.
"""

from __future__ import annotations

import re
from typing import Any

from core.models import ViolationTarget
from core.tools.slither_analyzer import extract_program_facts


EDGE_TYPES = {"require", "establish", "trigger", "affect", "evidence"}


def build_exploit_dependency_graph(
    violation_target: ViolationTarget,
    source_code: str,
    contract_info: dict,
) -> dict[str, Any]:
    """Build a compact EDG summary from VES fields and program facts."""
    facts = extract_program_facts(source_code)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []

    sink_id = _node_id("sink", violation_target.vulnerable_sink or violation_target.vulnerability_type)
    impact_id = _node_id("impact", violation_target.intended_impact or violation_target.vulnerability_type)

    nodes.append({
        "id": sink_id,
        "type": "vulnerable_sink",
        "label": violation_target.vulnerable_sink or violation_target.vulnerability_type,
    })
    nodes.append({
        "id": impact_id,
        "type": "impact_target",
        "label": violation_target.intended_impact or _oracle_label(violation_target),
    })
    edges.append({"src": sink_id, "dst": impact_id, "type": "affect"})

    preconditions = list(violation_target.preconditions)
    preconditions.extend(violation_target.code_preconditions)
    preconditions.extend(violation_target.environment_preconditions)
    for idx, precondition in enumerate(preconditions):
        kind = "environment_state" if precondition.source == "environment" or precondition.status == "environment" else "state_predicate"
        node_id = _node_id(kind, f"{precondition.type}:{idx}")
        nodes.append({
            "id": node_id,
            "type": kind,
            "label": precondition.description,
            "status": precondition.status or "inferred",
        })
        edges.append({"src": node_id, "dst": sink_id, "type": "require"})

    trigger = violation_target.trigger_context or {}
    trigger_func = trigger.get("function") if isinstance(trigger, dict) else None
    candidate_functions = _candidate_functions(facts, violation_target, trigger_func)
    for func in candidate_functions:
        op_id = _node_id("operation", func["name"])
        nodes.append({
            "id": op_id,
            "type": "operation",
            "label": func["name"],
            "visibility": func.get("visibility"),
            "modifiers": func.get("modifiers", []),
            "payable": func.get("payable", False),
        })
        edges.append({"src": op_id, "dst": sink_id, "type": "trigger"})
        for modifier in func.get("modifiers", []):
            mod_id = _node_id("role_or_guard", modifier)
            nodes.append({"id": mod_id, "type": "role_or_guard", "label": modifier})
            edges.append({"src": mod_id, "dst": op_id, "type": "require"})

    for evidence_idx, evidence in enumerate(violation_target.evidence[:12]):
        evidence_id = _node_id("evidence", str(evidence_idx))
        nodes.append({"id": evidence_id, "type": "evidence", "label": evidence})
        edges.append({"src": sink_id, "dst": evidence_id, "type": "evidence"})

    return {
        "root_sink": sink_id,
        "root_impact": impact_id,
        "nodes": _dedupe_nodes(nodes),
        "edges": _dedupe_edges(edges),
        "program_facts": facts,
        "planning_debt": compute_planning_debt(violation_target),
        "admissible_actions": derive_admissible_actions(violation_target, facts, candidate_functions),
    }


def compute_planning_debt(violation_target: ViolationTarget) -> dict[str, list[str]]:
    """Convert VES requirements into PoCForge planning debt buckets."""
    debt = {
        "reachability": [],
        "resource": [],
        "environment": [],
        "impact": [],
    }

    if violation_target.vulnerable_sink:
        debt["reachability"].append(f"Reach vulnerable sink: {violation_target.vulnerable_sink}")
    trigger = violation_target.trigger_context or {}
    if isinstance(trigger, dict):
        if trigger.get("function"):
            debt["reachability"].append(f"Trigger entry function: {trigger['function']}")
        for step in trigger.get("ordering", []) or []:
            debt["reachability"].append(f"Preserve transaction ordering: {step}")
        for param in trigger.get("parameters", []) or []:
            debt["reachability"].append(f"Use parameter constraint: {param}")

    for precondition in violation_target.preconditions + violation_target.code_preconditions:
        target = "resource" if precondition.type in {"token_balance", "balance", "attacker_resource"} else "reachability"
        debt[target].append(precondition.description)
    for precondition in violation_target.environment_preconditions:
        debt["environment"].append(precondition.description)

    if violation_target.intended_impact:
        debt["impact"].append(violation_target.intended_impact)
    debt["impact"].append(_oracle_label(violation_target))

    return {key: _dedupe_strings(value) for key, value in debt.items()}


def derive_admissible_actions(
    violation_target: ViolationTarget,
    facts: dict,
    candidate_functions: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Generate dependency-relevant action hints for the agent."""
    actions: list[dict[str, str]] = []
    trigger = violation_target.trigger_context or {}
    candidate_functions = candidate_functions or _candidate_functions(
        facts, violation_target, trigger.get("function") if isinstance(trigger, dict) else None
    )

    actions.append({
        "phase": "init",
        "action": "label_contracts_and_capture_baselines",
        "establishes": "execution evidence and oracle baselines",
    })

    for precondition in violation_target.preconditions + violation_target.code_preconditions:
        lowered = precondition.description.lower()
        if any(word in lowered for word in ("owner", "admin", "role", "permission", "only")):
            action = "query_role_holder_then_vm_prank"
        elif any(word in lowered for word in ("balance", "token", "fund", "liquidity")):
            action = "deal_or_transfer_required_assets"
        elif any(word in lowered for word in ("time", "deadline", "block")):
            action = "vm_warp_or_vm_roll"
        else:
            action = "call_state_preparation_function"
        actions.append({
            "phase": "prepare",
            "action": action,
            "establishes": precondition.description,
        })

    for precondition in violation_target.environment_preconditions:
        actions.append({
            "phase": "prepare",
            "action": "construct_or_override_environment_state",
            "establishes": precondition.description,
        })

    for func in candidate_functions[:8]:
        actions.append({
            "phase": "exploit",
            "action": f"call {func['name']}({func.get('params', '')})",
            "establishes": f"trigger sink via {func['name']}",
        })

    actions.append({
        "phase": "exploit",
        "action": "assert_asset_or_logic_oracle",
        "establishes": _oracle_label(violation_target),
    })
    return actions


def format_edg_for_agent(edg: dict[str, Any]) -> str:
    """Render a compact EDG/debt/action view for the LLM prompt."""
    lines = ["## Exploit Dependency Graph (EDG)"]
    lines.append("### Planning Debt")
    for bucket, items in edg.get("planning_debt", {}).items():
        lines.append(f"- {bucket}:")
        if items:
            for item in items[:8]:
                lines.append(f"  - {item}")
        else:
            lines.append("  - none")

    lines.append("\n### Admissible Actions")
    for action in edg.get("admissible_actions", [])[:18]:
        lines.append(
            f"- [{action.get('phase', '?')}] {action.get('action')} -> {action.get('establishes')}"
        )

    lines.append("\n### Relevant Program Facts")
    facts = edg.get("program_facts", {})
    for func in facts.get("external_functions", [])[:16]:
        modifiers = ", ".join(func.get("modifiers", [])) or "none"
        lines.append(f"- function {func['name']}({func.get('params', '')}) [{func.get('visibility')}; modifiers={modifiers}]")
    for predicate in facts.get("branch_predicates", [])[:12]:
        lines.append(f"- predicate in {predicate['function']}: {predicate['predicate']}")
    for call in facts.get("sensitive_operations", [])[:12]:
        lines.append(f"- sensitive call in {call['function']}: {call['target']}.{call['call']}()")
    return "\n".join(lines)


def _candidate_functions(facts: dict, vt: ViolationTarget, trigger_func: str | None) -> list[dict[str, Any]]:
    functions = facts.get("external_functions", [])
    if trigger_func:
        exact = [func for func in functions if func.get("name", "").lower() == str(trigger_func).lower()]
        if exact:
            return exact + [func for func in functions if func not in exact]

    haystack = " ".join([
        vt.vulnerability_type or "",
        vt.vulnerable_sink or "",
        vt.exploit_hint or "",
        vt.intended_impact or "",
    ]).lower()
    scored = []
    for func in functions:
        name = func.get("name", "")
        score = 0
        if name.lower() in haystack:
            score += 3
        if any(token in name.lower() for token in ("swap", "mint", "burn", "withdraw", "transfer", "claim", "set", "sync")):
            score += 1
        scored.append((score, func))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [func for score, func in scored if score > 0] or functions[:8]


def _oracle_label(vt: ViolationTarget) -> str:
    oracle = vt.oracle_verification
    if oracle.economic_check and oracle.logic_check:
        return "composite asset and logic oracle must pass"
    if oracle.economic_check:
        return f"asset oracle: {oracle.economic_check.condition} for {oracle.economic_check.target_token}"
    if oracle.logic_check:
        check = oracle.logic_check
        return f"logic oracle: {check.target_variable} {check.operator} {check.expected_value}"
    return "manual oracle evidence"


def _node_id(kind: str, label: str) -> str:
    compact = re.sub(r'[^A-Za-z0-9_]+', '_', str(label).strip().lower()).strip("_")
    return f"{kind}:{compact[:60] or 'unknown'}"


def _dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {}
    for node in nodes:
        by_id.setdefault(node["id"], node)
    return list(by_id.values())


def _dedupe_edges(edges: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    result = []
    for edge in edges:
        marker = (edge["src"], edge["dst"], edge["type"])
        if marker in seen or edge["type"] not in EDGE_TYPES:
            continue
        seen.add(marker)
        result.append(edge)
    return result


def _dedupe_strings(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
