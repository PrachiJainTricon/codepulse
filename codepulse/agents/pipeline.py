"""
P4 — LangGraph pipeline wiring.

Defines and compiles the StateGraph:

    START → investigator → risk_analyst → explainer → END

The graph also has one conditional edge: if no changed_symbols are
present in the initial state, the pipeline skips to END immediately.

Public entry point:
    from codepulse.agents.pipeline import run_pipeline

    result = run_pipeline(
        repo_path="./my-repo",
        commit_ref="HEAD~1",
        changed_symbols=changed,   # list[ChangedSymbol] from P3
    )
    # result is a RiskResult TypedDict
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from codepulse.agents.state import AgentState, RiskResult
from codepulse.agents.change_investigator import investigator_node
from codepulse.agents.risk_analyst import risk_analyst_node
from codepulse.agents.explainer import explainer_node


# ── Conditional routing ───────────────────────────────────────────────────────

def _route_start(state: AgentState) -> str:
    """Skip the whole pipeline when there's nothing to analyze."""
    if not state.get("changed_symbols"):
        return END
    return "investigator"


# ── Graph definition ──────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    builder = StateGraph(AgentState)

    builder.add_node("investigator", investigator_node)
    builder.add_node("risk_analyst", risk_analyst_node)
    builder.add_node("explainer", explainer_node)

    # Conditional start: skip everything if no changed symbols
    builder.add_conditional_edges(START, _route_start, {"investigator": "investigator", END: END})

    builder.add_edge("investigator", "risk_analyst")
    builder.add_edge("risk_analyst", "explainer")
    builder.add_edge("explainer", END)

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
    changed_symbols : list[ChangedSymbol] produced by P3's resolve_diff()

    Returns
    -------
    RiskResult with score, level, reasons, explanation, pr_description,
    impacted_symbols, and changed_symbols.
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
    )
