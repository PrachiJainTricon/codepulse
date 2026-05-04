"""Shared pytest fixtures."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from codepulse.agents.state import ChangedSymbol, ImpactedSymbol


@pytest.fixture()
def mock_graph_queries():
    """Patch get_blast_radius and get_test_coverage so tests don't need Neo4j."""
    impacted: list[ImpactedSymbol] = [
        ImpactedSymbol(name="create_invoice", file="billing/invoice.py", kind="function", depth=1),
        ImpactedSymbol(name="payment_controller", file="api/payments.py", kind="class", depth=2),
    ]
    with (
        patch("codepulse.agents.change_investigator.get_blast_radius", return_value=impacted),
        patch("codepulse.agents.change_investigator.get_test_coverage", return_value=True),
    ):
        yield impacted


@pytest.fixture()
def sample_changed_symbols() -> list[ChangedSymbol]:
    return [
        ChangedSymbol(
            file="billing/charge.py",
            symbol="charge_card",
            kind="function",
            change_type="modified",
            start_line=10,
            end_line=40,
        )
    ]
