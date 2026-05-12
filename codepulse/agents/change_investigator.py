"""
P4 — Change Investigator node.

LangGraph node: receives changed_symbols, queries the code graph for
every reachable downstream symbol (blast radius), and writes back:
  - impacted_symbols
  - fan_out_count
  - max_depth_reached
  - cross_module
  - has_test_coverage
"""

from __future__ import annotations

from pathlib import Path

from codepulse.agents.state import AgentState, ImpactedSymbol
from codepulse.graph.queries import get_blast_radius, get_test_coverage


def investigator_node(state: AgentState) -> dict:
    """
    LangGraph node — blast radius traversal.

    Reads:  state["changed_symbols"]
    Writes: state["impacted_symbols"], fan_out_count, max_depth_reached,
            cross_module, has_test_coverage
    """
    changed = state.get("changed_symbols", [])
    if not changed:
        return {
            "impacted_symbols": [],
            "fan_out_count": 0,
            "max_depth_reached": 0,
            "cross_module": False,
            "has_test_coverage": False,
        }

    # Collect unique impacted symbols across all changed symbols
    seen: dict[str, ImpactedSymbol] = {}   # name → deepest entry wins
    any_test_coverage = False

    for changed_sym in changed:
        symbol_name = changed_sym["symbol"]
        impacted = get_blast_radius(symbol_name, max_depth=3)

        for imp in impacted:
            existing = seen.get(imp["name"])
            if existing is None or imp["depth"] < existing["depth"]:
                seen[imp["name"]] = imp

        if get_test_coverage(symbol_name):
            any_test_coverage = True

    impacted_list = sorted(seen.values(), key=lambda x: x["depth"])

    # Detect cross-module impact: any impacted symbol in a different top-level folder
    changed_roots = {
        Path(s["file"]).parts[0] for s in changed if s.get("file")
    }
    cross_module = any(
        Path(imp["file"]).parts[0] not in changed_roots
        for imp in impacted_list
        if imp.get("file")
    )

    max_depth = max((imp["depth"] for imp in impacted_list), default=0)

    return {
        "impacted_symbols": impacted_list,
        "fan_out_count": len(impacted_list),
        "max_depth_reached": max_depth,
        "cross_module": cross_module,
        "has_test_coverage": any_test_coverage,
    }
