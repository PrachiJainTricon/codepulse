"""
P3 — Commit metadata helper.

Fetches human-readable info about a commit so the explainer/PR writer
agents can include context like author and message in their output.
"""

from __future__ import annotations

import subprocess
from typing import TypedDict


class CommitMeta(TypedDict):
    sha: str
    short_sha: str
    author: str
    date: str
    subject: str       # first line of commit message
    body: str          # rest of commit message (may be empty)


def get_commit_meta(repo_path: str, commit_ref: str = "HEAD") -> CommitMeta:
    """
    Return metadata for the given commit ref.

    Example:
        meta = get_commit_meta("./my-repo", "HEAD~1")
        # {"sha": "abc123...", "author": "Alice", "subject": "fix payment bug", ...}
    """
    fmt = "%H%n%h%n%an%n%ad%n%s%n%b"
    result = subprocess.run(
        ["git", "log", "-1", f"--format={fmt}", "--date=short", commit_ref],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr.strip()}")

    lines = result.stdout.split("\n", 5)
    # pad to 6 entries in case body is missing
    while len(lines) < 6:
        lines.append("")

    return CommitMeta(
        sha=lines[0].strip(),
        short_sha=lines[1].strip(),
        author=lines[2].strip(),
        date=lines[3].strip(),
        subject=lines[4].strip(),
        body=lines[5].strip(),
    )


def get_diff_stat(repo_path: str, commit_ref: str = "HEAD~1") -> str:
    """Return a short --stat summary (number of files, insertions, deletions)."""
    result = subprocess.run(
        ["git", "diff", commit_ref, "--stat"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()
