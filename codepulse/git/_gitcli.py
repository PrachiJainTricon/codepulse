"""Thin wrapper around the `git` CLI used by the git helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path


def git_output(repo_path: Path, *args: str, timeout: float = 8.0) -> str | None:
    """Run `git <args>` in `repo_path` and return trimmed stdout.

    Returns None on non-zero exit, missing git, or empty output.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def is_git_repo(repo_path: Path) -> bool:
    """True if `repo_path` is inside a git working tree."""
    return git_output(repo_path, "rev-parse", "--is-inside-work-tree") == "true"
