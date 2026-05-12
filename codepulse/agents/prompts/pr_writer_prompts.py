"""PR Writer agent prompts."""

from __future__ import annotations

SYSTEM = """\
You are a technical writer generating a pull request description.

Format:
## <type>: <concise title>

### What changed
- bullet list of changes

### Impact
- bullet list of downstream effects

### Testing
- ✓ tests that cover this change
- ⚠ gaps that need new tests

### Risk
One sentence: risk level + reasoning.

Rules:
- Be concise and accurate.
- Use conventional commit type prefix (fix, feat, refactor, chore).
- No fluff, no filler sentences.
"""

USER = """\
Commit: {subject}
Author: {author} ({date})

Changed symbols: {changed_symbols}
Files changed: {changed_files}

Blast radius: {fan_out_count} downstream symbols in {file_count} files
Risk level: {level}
Explanation: {explanation}

Test coverage:
  Must run: {tests_to_run}
  Gaps: {test_gaps}

Generate the PR description.
"""


def build_pr_writer_prompt(state: dict, commit_meta: dict) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the PR writer node."""
    changed = [s["symbol"] for s in state.get("changed_symbols", [])]
    changed_files = list({s.get("file", "") for s in state.get("changed_symbols", [])})
    impacted = state.get("impacted_symbols", [])
    impacted_files = list({s.get("file", "") for s in impacted if s.get("file")})

    user = USER.format(
        author=commit_meta.get("author", "unknown"),
        date=commit_meta.get("date", "unknown"),
        subject=commit_meta.get("message", commit_meta.get("subject", "")),
        changed_symbols=", ".join(changed) or "none",
        changed_files=", ".join(changed_files) or "none",
        fan_out_count=len(impacted),
        file_count=len(impacted_files),
        level=state.get("level", "unknown"),
        explanation=state.get("explanation", ""),
        tests_to_run=", ".join(state.get("tests_to_run", [])) or "none identified",
        test_gaps=", ".join(state.get("test_gaps", [])) or "all covered",
    )
    return SYSTEM, user
