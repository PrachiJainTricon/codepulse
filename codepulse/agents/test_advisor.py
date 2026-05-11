"""
Test Advisor node.

Checks which impacted symbols have test coverage and which don't.
Writes test_gaps (uncovered symbols) and tests_to_run (existing test files)
back to the shared state.

Purely deterministic — no LLM calls.
"""

from __future__ import annotations

from codepulse.agents.state import AgentState
from codepulse.graph.queries import get_test_coverage


def test_advisor_node(state: AgentState) -> dict:
    """
    LangGraph node — test coverage analysis.

    Reads:  impacted_symbols, changed_symbols
    Writes: test_gaps, tests_to_run
    """
    impacted = state.get("impacted_symbols", [])
    changed = state.get("changed_symbols", [])

    tests_to_run: set[str] = set()
    test_gaps: list[str] = []

    # Check coverage for changed symbols
    for sym in changed:
        symbol_name = sym["symbol"]
        coverage = get_test_coverage(symbol_name)
        if coverage:
            tests_to_run.update(coverage)
        else:
            test_gaps.append(f"{sym.get('file', '?')}::{symbol_name}")

    # Check coverage for impacted symbols
    for imp in impacted:
        symbol_name = imp["name"]
        coverage = get_test_coverage(symbol_name)
        if coverage:
            tests_to_run.update(coverage)
        else:
            test_gaps.append(f"{imp.get('file', '?')}::{symbol_name}")

    return {
        "test_gaps": test_gaps,
        "tests_to_run": sorted(tests_to_run),
    }
