"""
P3 — Git diff resolver.

Converts `git diff <ref>` output into a list of ChangedSymbol objects
that the LangGraph pipeline can consume.

Pipeline entry point:
    changed = resolve_diff(repo_path="./my-repo", commit_ref="HEAD~1")
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from codepulse.agents.state import ChangedSymbol
from codepulse.git.symbol_diff import extract_symbols_from_hunk


# ── Low-level git helpers ─────────────────────────────────────────────────────

def _run(args: list[str], cwd: str) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git command failed: {result.stderr.strip()}")
    return result.stdout


def get_changed_files(repo_path: str, commit_ref: str = "HEAD~1") -> list[str]:
    """Return repo-relative paths of all files changed in the diff."""
    output = _run(["git", "diff", commit_ref, "--name-only"], cwd=repo_path)
    return [line.strip() for line in output.splitlines() if line.strip()]


def get_raw_diff(repo_path: str, commit_ref: str = "HEAD~1") -> str:
    """Return the full unified diff text."""
    return _run(["git", "diff", commit_ref, "--unified=3"], cwd=repo_path)


# ── Hunk-level parsing ────────────────────────────────────────────────────────

def _parse_file_hunks(diff_text: str) -> list[dict]:
    """
    Split a unified diff into per-file hunks.

    Returns a list of:
        {
            "file": "payments/service.py",
            "added_lines": ["def charge_card(user, amount):", ...],
            "removed_lines": ["def charge_card(user):", ...],
            "start_line": 42,
        }
    """
    import re

    hunks: list[dict] = []
    current_file: str | None = None
    added: list[str] = []
    removed: list[str] = []
    start_line: int | None = None

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            if current_file is not None:
                hunks.append(
                    {
                        "file": current_file,
                        "added_lines": added,
                        "removed_lines": removed,
                        "start_line": start_line,
                    }
                )
            m = re.search(r" b/(.+)$", line)
            current_file = m.group(1) if m else None
            added, removed, start_line = [], [], None

        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            if m:
                start_line = int(m.group(1))

        elif line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])

        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])

    if current_file is not None:
        hunks.append(
            {
                "file": current_file,
                "added_lines": added,
                "removed_lines": removed,
                "start_line": start_line,
            }
        )

    return hunks


# ── Public API ────────────────────────────────────────────────────────────────

def resolve_diff(repo_path: str, commit_ref: str = "HEAD~1") -> list[ChangedSymbol]:
    """
    Main P3 entry point.

    Parse `git diff <commit_ref>` and return a list of ChangedSymbol dicts
    ready to be passed into AgentState["changed_symbols"].

    Falls back to file-level symbols if no function/class names can be
    extracted from the diff lines.
    """
    repo_path = str(Path(repo_path).resolve())
    raw = get_raw_diff(repo_path, commit_ref)
    hunks = _parse_file_hunks(raw)

    results: list[ChangedSymbol] = []

    for hunk in hunks:
        file_path: str = hunk["file"]
        symbols = extract_symbols_from_hunk(
            file_path=file_path,
            added_lines=hunk["added_lines"],
            removed_lines=hunk["removed_lines"],
            start_line=hunk["start_line"],
        )

        if symbols:
            results.extend(symbols)
        else:
            # Fallback: treat the whole file as a changed "symbol"
            results.append(
                ChangedSymbol(
                    file=file_path,
                    symbol=Path(file_path).stem,
                    kind="unknown",
                    change_type="modified",
                    start_line=hunk["start_line"],
                    end_line=None,
                )
            )

    return results
