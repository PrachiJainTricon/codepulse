"""
Neo4j blast-radius queries.

When CODEPULSE_NEO4J_URI is set, real Cypher queries run against Neo4j.
Otherwise falls back to built-in mock data so the pipeline can be
demoed without a running database.
"""

from __future__ import annotations

import os

from codepulse.agents.state import ImpactedSymbol

_MOCK_MODE: bool = os.getenv("CODEPULSE_NEO4J_URI") is None


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


# ── Real Neo4j queries ────────────────────────────────────────────────────────

def _neo4j_blast_radius(symbol_name: str, max_depth: int = 3) -> list[ImpactedSymbol]:
    """
    Traverse callers/importers of *symbol_name* up to *max_depth* hops.

    Matches any Symbol whose ``name`` ends with the unqualified identifier
    (handles repo-id-prefixed qualified_name values stored by the ingester).
    """
    from codepulse.graph.client import Neo4jClient

    cypher = """
    MATCH path = (start:Symbol)<-[:CALLS|IMPORTS*1..$max_depth]-(other:Symbol)
    WHERE start.name = $symbol_name OR start.qualified_name ENDS WITH $symbol_name
    RETURN other.name        AS name,
           other.file        AS file,
           other.kind        AS kind,
           length(path)      AS depth
    ORDER BY depth
    """

    def _tx(tx):
        return list(tx.run(cypher, symbol_name=symbol_name, max_depth=max_depth))

    with Neo4jClient() as client:
        with client.driver.session(database=client.database) as session:
            records = session.execute_read(_tx)

    return [
        ImpactedSymbol(
            name=str(r["name"]),
            file=str(r["file"] or ""),
            kind=str(r["kind"] or "unknown"),
            depth=int(r["depth"]),
        )
        for r in records
    ]


def _neo4j_has_tests(symbol_name: str) -> bool:
    """
    Return True if *symbol_name* has at least one test file linked via
    a ``TESTED_BY`` relationship in the graph.
    """
    from codepulse.graph.client import Neo4jClient

    cypher = """
    MATCH (s:Symbol)-[:TESTED_BY]->(f:File)
    WHERE (s.name = $symbol_name OR s.qualified_name ENDS WITH $symbol_name)
      AND f.is_test = true
    RETURN count(f) > 0 AS has_tests
    """

    def _tx(tx):
        result = tx.run(cypher, symbol_name=symbol_name)
        record = result.single()
        return bool(record["has_tests"]) if record else False

    with Neo4jClient() as client:
        with client.driver.session(database=client.database) as session:
            return session.execute_read(_tx)


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
