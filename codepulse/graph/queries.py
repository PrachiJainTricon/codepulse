"""
Neo4j blast-radius queries.

P2 owns this file. P4 (investigator node) calls get_blast_radius() and
get_test_coverage(). The signatures below are the contract — P2 fills
in the Cypher; P4 works against the mock until Neo4j is ready.

To swap in real Neo4j, replace _MOCK_MODE = True with False and make
sure NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD are set in .env.
"""

from __future__ import annotations

import os

from codepulse.agents.state import ImpactedSymbol

_MOCK_MODE: bool = os.getenv("NEO4J_URI") is None


# ── Mock data (used when Neo4j is not available) ──────────────────────────────

_MOCK_GRAPH: dict[str, list[dict]] = {
    "charge_card": [
        {"name": "create_invoice", "file": "billing/invoice.py", "kind": "function", "depth": 1},
        {"name": "send_receipt", "file": "notifications/email.py", "kind": "function", "depth": 1},
        {"name": "payment_controller", "file": "api/payments.py", "kind": "class", "depth": 2},
    ],
    "refund_payment": [
        {"name": "refund_controller", "file": "api/refunds.py", "kind": "class", "depth": 1},
        {"name": "ledger_entry", "file": "billing/ledger.py", "kind": "function", "depth": 2},
    ],
}

_MOCK_TEST_FILES: dict[str, bool] = {
    "charge_card": True,
    "send_receipt": False,
}


# ── Real Neo4j queries (P2 fills these in) ────────────────────────────────────

def _neo4j_blast_radius(symbol_name: str, max_depth: int = 3) -> list[ImpactedSymbol]:
    """
    Cypher query to traverse callers/importers up to max_depth hops.

    MATCH path = (start:Symbol {name: $symbol_name})<-[:CALLS|IMPORTS*1..$max_depth]-(other)
    RETURN other.name AS name, other.file AS file, other.kind AS kind,
           length(path) AS depth
    ORDER BY depth
    """
    # TODO (P2): replace this stub with a real neo4j driver call
    raise NotImplementedError("Neo4j query not yet implemented by P2")


def _neo4j_has_tests(symbol_name: str) -> bool:
    """
    Check whether a symbol has associated test files in the graph.

    MATCH (:Symbol {name: $symbol_name})-[:TESTED_BY]->(:File {is_test: true})
    RETURN count(*) > 0 AS has_tests
    """
    # TODO (P2): replace this stub with a real neo4j driver call
    raise NotImplementedError("Neo4j query not yet implemented by P2")


# ── Public API (P4 uses these) ────────────────────────────────────────────────

def get_blast_radius(symbol_name: str, max_depth: int = 3) -> list[ImpactedSymbol]:
    """
    Return symbols reachable from symbol_name within max_depth hops.

    Uses real Neo4j when NEO4J_URI env var is set; falls back to mock data.
    """
    if not _MOCK_MODE:
        return _neo4j_blast_radius(symbol_name, max_depth)

    raw = _MOCK_GRAPH.get(symbol_name, [])
    return [
        ImpactedSymbol(
            name=item["name"],
            file=item["file"],
            kind=item["kind"],
            depth=item["depth"],
        )
        for item in raw
        if item["depth"] <= max_depth
    ]


def get_test_coverage(symbol_name: str) -> bool:
    """Return True if the symbol has associated test files in the graph."""
    if not _MOCK_MODE:
        return _neo4j_has_tests(symbol_name)
    return _MOCK_TEST_FILES.get(symbol_name, False)
