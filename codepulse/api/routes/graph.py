"""
GET /graph/blast-radius  —  return the downstream impact graph for a symbol.
GET /graph/test-coverage —  return whether a symbol has test coverage.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from codepulse.graph.queries import get_blast_radius, get_test_coverage
from codepulse.agents.state import ImpactedSymbol

router = APIRouter()


@router.get("/blast-radius")
def blast_radius(
    symbol: str = Query(..., description="Symbol name to query"),
    max_depth: int = Query(3, ge=1, le=10, description="Max traversal depth"),
) -> list[ImpactedSymbol]:
    """Return all symbols reachable from *symbol* within *max_depth* hops."""
    return get_blast_radius(symbol, max_depth=max_depth)


@router.get("/test-coverage")
def test_coverage(
    symbol: str = Query(..., description="Symbol name to check"),
) -> dict:
    """Return whether *symbol* has associated test files in the graph."""
    has_tests = get_test_coverage(symbol)
    return {"symbol": symbol, "has_tests": has_tests}
