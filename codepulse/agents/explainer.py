"""
P4 — Explainer node.

Calls the LLM (Claude via Anthropic SDK) to turn the blast-radius data
into a plain-English explanation and a PR description.

Falls back to a template-based explanation when ANTHROPIC_API_KEY is not set,
so the pipeline always produces output even during local dev without an API key.
"""

from __future__ import annotations

import os

from codepulse.agents.state import AgentState
from codepulse.agents.prompts import build_explainer_prompt, build_pr_writer_prompt
from codepulse.git.commit_meta import get_commit_meta


# ── LLM call ─────────────────────────────────────────────────────────────────

def _call_llm(system: str, user: str) -> str:
    """
    Call Anthropic Claude. Raises ImportError if the SDK is missing,
    or returns a message if the key is absent.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set")

    import anthropic  # optional dependency — only needed at runtime

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-3-5-haiku-20241022",   # fast + cheap for demo
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text.strip()


def _fallback_explanation(state: AgentState) -> str:
    """Template-based fallback when no LLM key is available."""
    changed = [s["symbol"] for s in state.get("changed_symbols", [])]
    impacted = [s["name"] for s in state.get("impacted_symbols", [])]
    level = state.get("level", "unknown")
    reasons = state.get("reasons", [])

    lines = [
        f"Change detected in: {', '.join(changed) or 'unknown'}.",
        f"Downstream impact: {', '.join(impacted) if impacted else 'no downstream symbols found'}.",
        f"Risk level: {level.upper()}.",
    ]
    if reasons:
        lines.append("Reasons: " + "; ".join(reasons) + ".")
    return " ".join(lines)


# ── LangGraph node ────────────────────────────────────────────────────────────

def explainer_node(state: AgentState) -> dict:
    """
    LangGraph node — LLM explanation + PR description.

    Reads:  changed_symbols, impacted_symbols, score, level, reasons,
            repo_path, commit_ref
    Writes: explanation, pr_description
    """
    # --- Plain-English explanation ---
    try:
        system, user = build_explainer_prompt(state)
        explanation = _call_llm(system, user)
    except (EnvironmentError, ImportError):
        explanation = _fallback_explanation(state)

    # --- PR description ---
    try:
        repo_path  = state.get("repo_path", ".")
        commit_ref = state.get("commit_ref", "HEAD")
        # commit_ref for git log should be the actual commit, not HEAD~1
        log_ref = "HEAD" if commit_ref == "HEAD~1" else commit_ref
        meta = get_commit_meta(repo_path, log_ref)

        system, user = build_pr_writer_prompt(
            {**state, "explanation": explanation}, meta
        )
        pr_description = _call_llm(system, user)
    except Exception:
        # Non-fatal: explanation is the more important output
        changed = [s["symbol"] for s in state.get("changed_symbols", [])]
        pr_description = (
            f"## Summary\n{explanation}\n\n"
            f"**Changed:** {', '.join(changed) or 'see diff'}\n"
            f"**Risk:** {state.get('level', 'unknown').upper()}"
        )

    return {"explanation": explanation, "pr_description": pr_description}
