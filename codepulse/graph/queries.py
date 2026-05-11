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

_MOCK_TEST_COVERAGE: dict[str, list[str]] = {
    "charge_card": ["tests/test_billing.py"],
    "create_invoice": ["tests/test_billing.py"],
}


# ── Real Neo4j queries ────────────────────────────────────────────────────────

def _neo4j_blast_radius(symbol_name: str, max_depth: int = 3) -> list[ImpactedSymbol]:
    """
    Traverse callers of *symbol_name* up to *max_depth* hops.
    Only returns non-deleted symbols from the latest indexed state.
    """
    from codepulse.graph.client import Neo4jClient

    depth = max(1, min(int(max_depth), 10))

    cypher = f"""
    MATCH path = (start:Symbol)<-[:CALLS*1..{depth}]-(caller:Symbol)
    WHERE (start.name = $symbol_name OR start.qualified_name ENDS WITH $symbol_name)
      AND coalesce(start.deleted, false) = false
      AND coalesce(caller.deleted, false) = false
    RETURN DISTINCT caller.name        AS name,
           caller.file_path    AS file,
           caller.type         AS kind,
           length(path)        AS depth
    ORDER BY depth, name
    LIMIT 200
    """

    def _tx(tx):
        return list(tx.run(cypher, symbol_name=symbol_name))

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


def _neo4j_test_coverage(symbol_name: str) -> list[str]:
    """
    Return test file paths that cover *symbol_name*.
    Looks for test files that CALL or CONTAINS a test for this symbol.
    """
    from codepulse.graph.client import Neo4jClient

    cypher = """
    MATCH (test:Symbol)-[:CALLS]->(s:Symbol)
    WHERE (s.name = $symbol_name OR s.qualified_name ENDS WITH $symbol_name)
      AND test.is_test = true
      AND coalesce(s.deleted, false) = false
    RETURN DISTINCT test.file_path AS test_file, test.name AS test_name
    LIMIT 20
    """

    def _tx(tx):
        return list(tx.run(cypher, symbol_name=symbol_name))

    with Neo4jClient() as client:
        with client.driver.session(database=client.database) as session:
            records = session.execute_read(_tx)

    return [str(r["test_file"]) for r in records if r["test_file"]]

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


def get_test_coverage(symbol_name: str) -> list[str]:
    """Return list of test file paths that cover this symbol."""
    if not _MOCK_MODE:
        return _neo4j_test_coverage(symbol_name)
    return _MOCK_TEST_COVERAGE.get(symbol_name, [])
