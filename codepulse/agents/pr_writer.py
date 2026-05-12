"""
PR Writer node.

Calls the configured LLM to generate a pull request description
from the full pipeline state. Falls back to a template when no API key is set.
"""

from __future__ import annotations

from codepulse.agents.state import AgentState
from codepulse.agents.prompts import build_pr_writer_prompt
from codepulse.git.commit_meta import get_commit_meta
from codepulse.llm import call_llm


def _fallback_pr_description(state: AgentState) -> str:
    """Template-based fallback when no LLM key is available."""
    changed = [s["symbol"] for s in state.get("changed_symbols", [])]
    level = state.get("level", "unknown")
    explanation = state.get("explanation", "")
    test_gaps = state.get("test_gaps", [])
    tests_to_run = state.get("tests_to_run", [])

    lines = [
        f"## Summary\n{explanation}\n",
        f"**Changed:** {', '.join(changed) or 'see diff'}",
        f"**Risk:** {level.upper()}",
    ]
    if tests_to_run:
        lines.append(f"**Run:** {', '.join(tests_to_run)}")
    if test_gaps:
        lines.append(f"**Gaps:** {', '.join(test_gaps)}")
    return "\n".join(lines)


def pr_writer_node(state: AgentState) -> dict:
    """
    LangGraph node — PR description generation.

    Reads:  full state (changed_symbols, impacted_symbols, explanation, etc.)
    Writes: pr_description
    """
    try:
        repo_path = state.get("repo_path", ".")
        commit_ref = state.get("commit_ref", "HEAD")
        log_ref = "HEAD" if commit_ref == "HEAD~1" else commit_ref
        meta = get_commit_meta(repo_path, log_ref)

        system, user = build_pr_writer_prompt(state, meta.__dict__)
        pr_description = call_llm(system=system, user=user)
    except Exception:
        pr_description = _fallback_pr_description(state)

    return {"pr_description": pr_description}
