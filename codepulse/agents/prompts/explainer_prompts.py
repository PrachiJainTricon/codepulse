"""Explainer agent prompts."""

from __future__ import annotations

SYSTEM = """\
You are a senior software engineer reviewing a code change.
Your job is to explain the blast radius — what could break, what is now affected, and why.

Rules:
- Be direct, no fluff. Plain English.
- Structure as numbered impact paths: Symbol A → Symbol B → Symbol C
- For each path, explain WHY the dependency matters (not just that it exists).
- 3–5 impact paths maximum. Prioritize by risk (uncovered paths first).
- End with a one-sentence risk summary.
"""

USER = """\
Changed symbols: {changed_symbols}

Downstream blast radius ({fan_out_count} symbols impacted):
{impacted_symbols}

Risk level: {level} (score: {score})
Signals: {reasons}

Test gaps (symbols with NO test coverage):
{test_gaps}

Write impact path explanations for the most critical paths.
"""


def build_explainer_prompt(state: dict) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the explainer node."""
    changed = [s["symbol"] for s in state.get("changed_symbols", [])]
    impacted = [
        f"  {s['name']} ({s.get('kind', '?')}) in {s.get('file', '?')} — depth {s.get('depth', '?')}"
        for s in state.get("impacted_symbols", [])
    ]
    test_gaps = state.get("test_gaps", [])

    user = USER.format(
        changed_symbols=", ".join(changed) or "none",
        fan_out_count=state.get("fan_out_count", 0),
        impacted_symbols="\n".join(impacted) or "none",
        score=state.get("score", 0),
        level=state.get("level", "unknown"),
        reasons="; ".join(state.get("reasons", [])) or "none",
        test_gaps=", ".join(test_gaps) or "all covered",
    )
    return SYSTEM, user
