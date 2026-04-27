"""Stable repo identifiers and names derived from git or path."""

from __future__ import annotations

import hashlib
from pathlib import Path

from codepulse.git._gitcli import git_output


def _remote_url(repo_path: Path) -> str | None:
    """Return the configured `origin` remote URL, or None."""
    return git_output(repo_path, "config", "--get", "remote.origin.url")


def get_repo_id(repo_path: Path) -> str:
    """
    Generate a stable 10-char id for a repository.

    Uses the git remote URL when available, otherwise the absolute path.
    The id is deterministic across runs and machines (for the same remote).
    """
    repo_path = repo_path.resolve()
    remote = _remote_url(repo_path)
    source = remote if remote else str(repo_path)
    return hashlib.sha1(source.encode()).hexdigest()[:10]


def get_repo_name(repo_path: Path) -> str:
    """Human-readable repo name (last segment of remote URL, or folder name)."""
    repo_path = repo_path.resolve()
    remote = _remote_url(repo_path)
    if remote:
        name = remote.rstrip("/").replace(".git", "")
        return name.split("/")[-1]
    return repo_path.name


def get_current_repo() -> tuple[str, str]:
    """`(repo_id, repo_name)` for the current working directory."""
    cwd = Path.cwd()
    return get_repo_id(cwd), get_repo_name(cwd)
