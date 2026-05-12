"""
P4 — Risk Analyst node.

Deterministic (no LLM). Computes a numeric risk score and a LOW / MEDIUM / HIGH
label from the blast-radius data written by the investigator node.

Scoring formula
---------------
  fan_out      × 2   — more impacted symbols = higher risk
  max_depth    × 3   — deeper traversal = higher risk
  cross_module × 5   — cross-package impact adds significant risk
  test_gap     × 4   — no test coverage found = extra risk
                       (subtracted when test coverage IS present)

Thresholds (tunable):
  score < 8   → low
  8–15        → medium
  > 15        → high
"""

from __future__ import annotations

from typing import Literal

from codepulse.agents.state import AgentState


# ── Scoring weights ───────────────────────────────────────────────────────────

_W_FAN_OUT      = 2
_W_DEPTH        = 3
_W_CROSS_MODULE = 5
_W_NO_TESTS     = 4

_THRESHOLD_LOW    = 8
_THRESHOLD_MEDIUM = 15


def _compute_score(
    fan_out: int,
    max_depth: int,
    cross_module: bool,
    has_tests: bool,
) -> int:
    score = (
        fan_out * _W_FAN_OUT
        + max_depth * _W_DEPTH
        + (cross_module * _W_CROSS_MODULE)
        - (has_tests * _W_NO_TESTS)
    )
    return max(score, 0)


def _score_to_level(score: int) -> Literal["low", "medium", "high"]:
    if score < _THRESHOLD_LOW:
        return "low"
    if score <= _THRESHOLD_MEDIUM:
        return "medium"
    return "high"


# ── LangGraph node ────────────────────────────────────────────────────────────

def risk_analyst_node(state: AgentState) -> dict:
    """
    LangGraph node — risk scoring.

    Reads:  fan_out_count, max_depth_reached, cross_module, has_test_coverage
    Writes: score, level, reasons
    """
    fan_out   = state.get("fan_out_count", 0)
    max_depth = state.get("max_depth_reached", 0)
    cross_mod = state.get("cross_module", False)
    has_tests = state.get("has_test_coverage", False)

    score = _compute_score(fan_out, max_depth, cross_mod, has_tests)
    level = _score_to_level(score)

    reasons: list[str] = [f"{fan_out} downstream symbol(s) impacted"]

    if max_depth > 0:
        reasons.append(f"Impact reaches {max_depth} level(s) deep")
    if cross_mod:
        reasons.append("Change crosses module boundaries")
    if not has_tests:
        reasons.append("No test coverage detected for changed symbols")
    else:
        reasons.append("Test coverage found — risk partially mitigated")

    return {"score": score, "level": level, "reasons": reasons}
