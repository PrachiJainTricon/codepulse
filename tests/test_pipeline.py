"""Tests for the LangGraph analysis pipeline."""

from __future__ import annotations

from unittest.mock import patch

from codepulse.agents.pipeline import run_pipeline
from codepulse.agents.state import RiskResult


def test_run_pipeline_returns_risk_result(mock_graph_queries, sample_changed_symbols):
    result: RiskResult = run_pipeline(
        repo_path="/tmp/fake-repo",
        commit_ref="HEAD~1",
        changed_symbols=sample_changed_symbols,
    )
    assert "score" in result
    assert result["level"] in ("low", "medium", "high")
    assert isinstance(result["reasons"], list)
    assert isinstance(result["explanation"], str)
    assert isinstance(result["impacted_symbols"], list)
    assert result["changed_symbols"] == sample_changed_symbols


def test_run_pipeline_empty_symbols():
    result: RiskResult = run_pipeline(
        repo_path="/tmp/fake-repo",
        commit_ref="HEAD~1",
        changed_symbols=[],
    )
    assert result["level"] in ("low", "medium", "high")
    assert result["score"] == 0 or result["impacted_symbols"] == []


def test_risk_level_high_for_wide_blast_radius(sample_changed_symbols):
    from codepulse.agents.state import ImpactedSymbol
    many_impacted = [
        ImpactedSymbol(name=f"sym_{i}", file=f"module_{i % 5}/file.py", kind="function", depth=1 + (i % 3))
        for i in range(15)
    ]
    with (
        patch("codepulse.agents.change_investigator.get_blast_radius", return_value=many_impacted),
        patch("codepulse.agents.change_investigator.get_test_coverage", return_value=False),
    ):
        result = run_pipeline(
            repo_path="/tmp/fake-repo",
            commit_ref="HEAD~1",
            changed_symbols=sample_changed_symbols,
        )
    assert result["level"] == "high"
    assert result["score"] > 15
