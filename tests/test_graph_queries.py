"""Tests for graph/queries.py — mock path only (no Neo4j required)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


def test_get_blast_radius_mock_returns_list():
    """get_blast_radius falls back to mock data when NEO4J_URI is unset."""
    with patch.dict(os.environ, {}, clear=True):
        # Remove CODEPULSE_NEO4J_URI so _MOCK_MODE activates
        env = {k: v for k, v in os.environ.items() if k != "CODEPULSE_NEO4J_URI"}
        with patch.dict(os.environ, env, clear=True):
            # Re-import to pick up mock mode
            import importlib
            import codepulse.graph.queries as q
            importlib.reload(q)

            result = q.get_blast_radius("charge_card")
            assert isinstance(result, list)
            for sym in result:
                assert "name" in sym
                assert "depth" in sym


def test_get_test_coverage_mock_known_symbol():
    import importlib
    import codepulse.graph.queries as q
    importlib.reload(q)

    # charge_card is True in mock data
    assert q.get_test_coverage("charge_card") is True


def test_get_test_coverage_mock_unknown_symbol():
    import importlib
    import codepulse.graph.queries as q
    importlib.reload(q)

    assert q.get_test_coverage("some_unknown_symbol") is False


def test_get_blast_radius_depth_filtering():
    import importlib
    import codepulse.graph.queries as q
    importlib.reload(q)

    # max_depth=1 should exclude depth-2 symbols
    result = q.get_blast_radius("charge_card", max_depth=1)
    assert all(sym["depth"] <= 1 for sym in result)
