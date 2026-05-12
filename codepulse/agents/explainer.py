"""
Explainer node.

Calls the configured LLM to produce a plain-English explanation
of the blast radius and impact paths.

Falls back to a template-based explanation when no API key is set,
so the pipeline always produces output even during local dev.
"""

from __future__ import annotations

from codepulse.agents.state import AgentState
from codepulse.agents.prompts import build_explainer_prompt
from codepulse.llm import call_llm


def _fallback_explanation(state: AgentState) -> str:
    """Template-based fallback when no LLM key is available."""
    changed = [s["symbol"] for s in state.get("changed_symbols", [])]
    impacted = [s["name"] for s in state.get("impacted_symbols", [])]
    level = state.get("level", "unknown")
    reasons = state.get("reasons", [])
    test_gaps = state.get("test_gaps", [])

    lines = [
        f"Change detected in: {', '.join(changed) or 'unknown'}.",
        f"Downstream impact: {', '.join(impacted) if impacted else 'no downstream symbols found'}.",
        f"Risk level: {level.upper()}.",
    ]
    if reasons:
        lines.append("Reasons: " + "; ".join(reasons) + ".")
    if test_gaps:
        lines.append(f"Test gaps: {', '.join(test_gaps)}.")
    return " ".join(lines)


# ── LangGraph node ────────────────────────────────────────────────────────────

def explainer_node(state: AgentState) -> dict:
    """
    LangGraph node — LLM explanation of impact paths.

    Reads:  changed_symbols, impacted_symbols, score, level, reasons, test_gaps
    Writes: explanation
    """
    try:
        system, user = build_explainer_prompt(state)
        explanation = call_llm(system=system, user=user)
    except (EnvironmentError, ImportError):
        explanation = _fallback_explanation(state)

    return {"explanation": explanation}
