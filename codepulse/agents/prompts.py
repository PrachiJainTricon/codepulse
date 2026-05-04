"""
P4 — LLM prompt templates.

Kept separate from the agent logic so they are easy to tweak without
touching node code.
"""

from __future__ import annotations


EXPLAINER_SYSTEM = """\
You are a senior software engineer reviewing a code change.
Your job is to explain the impact of that change clearly and concisely to a developer.
Focus on what could break, what is now affected, and why the risk level makes sense.
Be direct. No fluff. Use plain English. 3–5 sentences maximum.
"""

EXPLAINER_USER = """\
A developer just made the following change:

Changed symbols:
{changed_symbols}

Downstream impact (symbols reachable from the change):
{impacted_symbols}

Risk score: {score} ({level})
Reasons: {reasons}

Write a short plain-English explanation of what this change affects and why the risk is {level}.
""".strip()


PR_WRITER_SYSTEM = """\
You are a technical writer helping a developer write a pull request description.
Be concise, accurate, and structured. Use a short paragraph followed by a bullet list.
"""

PR_WRITER_USER = """\
Commit author: {author}
Commit date:   {date}
Commit message: {subject}

Changed symbols: {changed_symbols}
Impacted symbols: {impacted_symbols}
Risk level: {level}
Explanation: {explanation}

Write a clear, professional pull request description for this change.
""".strip()


def build_explainer_prompt(state: dict) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the explainer node."""
    changed = [s["symbol"] for s in state.get("changed_symbols", [])]
    impacted = [s["name"] for s in state.get("impacted_symbols", [])]
    reasons = state.get("reasons", [])

    user = EXPLAINER_USER.format(
        changed_symbols=", ".join(changed) or "none",
        impacted_symbols=", ".join(impacted) or "none",
        score=state.get("score", 0),
        level=state.get("level", "unknown"),
        reasons="; ".join(reasons) or "none",
    )
    return EXPLAINER_SYSTEM, user


def build_pr_writer_prompt(state: dict, commit_meta: dict) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the PR writer node."""
    changed = [s["symbol"] for s in state.get("changed_symbols", [])]
    impacted = [s["name"] for s in state.get("impacted_symbols", [])]

    user = PR_WRITER_USER.format(
        author=commit_meta.get("author", "unknown"),
        date=commit_meta.get("date", "unknown"),
        subject=commit_meta.get("subject", ""),
        changed_symbols=", ".join(changed) or "none",
        impacted_symbols=", ".join(impacted) or "none",
        level=state.get("level", "unknown"),
        explanation=state.get("explanation", ""),
    )
    return PR_WRITER_SYSTEM, user
