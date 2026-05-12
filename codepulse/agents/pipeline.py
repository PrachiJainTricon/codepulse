"""
LangGraph pipeline wiring.

Defines and compiles the StateGraph:

    START → investigator → [conditional] → explainer → pr_writer → END

Conditional routing:
  - If blast radius < 5 symbols → skip risk_analyst and test_advisor,
    set LOW risk, go straight to explainer → pr_writer.
  - Otherwise → risk_analyst → test_advisor → explainer → pr_writer.

Public entry point:
    from codepulse.agents.pipeline import run_pipeline

    result = run_pipeline(
        repo_path="./my-repo",
        commit_ref="HEAD~1",
        changed_symbols=changed,
    )
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from codepulse.agents.state import AgentState, RiskResult
from codepulse.agents.change_investigator import investigator_node
from codepulse.agents.risk_analyst import risk_analyst_node
from codepulse.agents.test_advisor import test_advisor_node
from codepulse.agents.explainer import explainer_node
from codepulse.agents.pr_writer import pr_writer_node


# ── Conditional routing ───────────────────────────────────────────────────────

def _route_start(state: AgentState) -> str:
    """Skip the whole pipeline when there's nothing to analyze."""
    if not state.get("changed_symbols"):
        return END
    return "investigator"


def _route_after_investigator(state: AgentState) -> str:
    """Skip risk_analyst when blast radius is small (< 5 symbols)."""
    fan_out = state.get("fan_out_count", 0)
    if fan_out < 5:
        return "test_advisor"
    return "risk_analyst"


# ── Graph definition ──────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    builder = StateGraph(AgentState)

    builder.add_node("investigator", investigator_node)
    builder.add_node("risk_analyst", risk_analyst_node)
    builder.add_node("test_advisor", test_advisor_node)
    builder.add_node("explainer", explainer_node)
    builder.add_node("pr_writer", pr_writer_node)

    # Conditional start: skip everything if no changed symbols
    builder.add_conditional_edges(START, _route_start, {"investigator": "investigator", END: END})

    # After investigator: skip risk_analyst for low-impact changes
    builder.add_conditional_edges(
        "investigator",
        _route_after_investigator,
        {"risk_analyst": "risk_analyst", "test_advisor": "test_advisor"},
    )

    builder.add_edge("risk_analyst", "test_advisor")
    builder.add_edge("test_advisor", "explainer")
    builder.add_edge("explainer", "pr_writer")
    builder.add_edge("pr_writer", END)

    return builder.compile()


# Compiled once at import time; safe to reuse across calls.
_graph = _build_graph()


# ── Public API ────────────────────────────────────────────────────────────────

def run_pipeline(
    repo_path: str,
    commit_ref: str,
    changed_symbols: list,
) -> RiskResult:
    """
    Run the full impact-analysis pipeline.

    Parameters
    ----------
    repo_path       : absolute or relative path to the git repo
    commit_ref      : git ref to diff against, e.g. "HEAD~1" or a SHA
    changed_symbols : list[ChangedSymbol] produced by resolve_diff()

    Returns
    -------
    RiskResult with score, level, reasons, explanation, pr_description,
    impacted_symbols, changed_symbols, test_gaps, tests_to_run.
    """
    initial_state: AgentState = {
        "repo_path": repo_path,
        "commit_ref": commit_ref,
        "changed_symbols": changed_symbols,
    }

    final_state: AgentState = _graph.invoke(initial_state)

    return RiskResult(
        score=final_state.get("score", 0),
        level=final_state.get("level", "low"),
        reasons=final_state.get("reasons", []),
        explanation=final_state.get("explanation", ""),
        pr_description=final_state.get("pr_description", ""),
        impacted_symbols=final_state.get("impacted_symbols", []),
        changed_symbols=final_state.get("changed_symbols", []),
        test_gaps=final_state.get("test_gaps", []),
        tests_to_run=final_state.get("tests_to_run", []),
    )
