"""
Shared state contracts for the LangGraph pipeline.

This is the single source of truth for data shapes passed between
P3 (diff) and P4 (agents). Freeze this before parallel work starts.
"""

from __future__ import annotations

from typing import Literal, Optional
from typing_extensions import TypedDict


# ── P3 output ────────────────────────────────────────────────────────────────

class ChangedSymbol(TypedDict):
    """One symbol (function, class, method) touched by the diff."""
    file: str                                          # repo-relative path
    symbol: str                                        # name, e.g. "charge_card"
    kind: Literal["function", "class", "method", "unknown"]
    change_type: Literal["added", "modified", "deleted"]
    start_line: Optional[int]
    end_line: Optional[int]


# ── P4 intermediate ───────────────────────────────────────────────────────────

class ImpactedSymbol(TypedDict):
    """A symbol reachable from a changed symbol via the code graph."""
    name: str
    file: str
    kind: str
    depth: int   # hops from the changed symbol


# ── Full pipeline state ───────────────────────────────────────────────────────

class AgentState(TypedDict, total=False):
    # Inputs (set before graph.invoke)
    repo_path: str
    commit_ref: str                    # e.g. "HEAD~1", a SHA, or a branch name
    changed_symbols: list[ChangedSymbol]

    # Investigator outputs
    impacted_symbols: list[ImpactedSymbol]
    fan_out_count: int
    max_depth_reached: int
    cross_module: bool
    has_test_coverage: bool

    # Risk analyst outputs
    score: int
    level: Literal["low", "medium", "high"]
    reasons: list[str]

    # Explainer output
    explanation: str
    pr_description: str

    # Error passthrough (non-fatal, lets pipeline complete with partial results)
    error: Optional[str]


# ── Risk result (final shape returned to CLI) ─────────────────────────────────

class RiskResult(TypedDict):
    score: int
    level: Literal["low", "medium", "high"]
    reasons: list[str]
    explanation: str
    impacted_symbols: list[ImpactedSymbol]
    changed_symbols: list[ChangedSymbol]
    pr_description: str
