"""Resolve the commit context (HEAD, base, changes) for a repo path.

Falls back to a stable "snapshot" id when the path is not a git repo.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from codepulse.git._gitcli import git_output, is_git_repo
from codepulse.git.diff_resolver import (
    ChangeEntry,
    git_diff_changes,
    git_initial_commit_changes,
    git_working_tree_changes,
)


@dataclass(frozen=True)
class CommitContext:
    """Information about the commit/snapshot being indexed."""

    commit_id: str
    mode: str                 # "commit" or "snapshot"
    base_commit: str | None
    head_commit: str | None
    changes: list[ChangeEntry]


def resolve_commit_context(repo_path: Path) -> CommitContext:
    """Derive commit metadata from git, or fall back to a snapshot hash."""
    repo_path = repo_path.resolve()

    if not is_git_repo(repo_path):
        return _snapshot(repo_path)

    head = git_output(repo_path, "rev-parse", "HEAD")
    if not head:
        return _snapshot(repo_path)

    base = git_output(repo_path, "rev-parse", "HEAD~1")
    if base:
        return CommitContext(
            commit_id=head,
            mode="commit",
            base_commit=base,
            head_commit=head,
            changes=git_diff_changes(repo_path, base, head),
        )

    # Initial commit — no parent to diff against.
    return CommitContext(
        commit_id=head,
        mode="commit",
        base_commit=None,
        head_commit=head,
        changes=git_initial_commit_changes(repo_path),
    )


def compute_snapshot_commit_id(repo_path: Path) -> str:
    """Deterministic id derived from file paths + mtimes (non-git fallback)."""
    repo_path = repo_path.resolve()
    entries: list[str] = []
    for path in sorted(repo_path.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_path).as_posix()
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            continue
        entries.append(f"{rel}:{mtime_ns}")
    return hashlib.sha1("\n".join(entries).encode("utf-8")).hexdigest()


def _snapshot(repo_path: Path) -> CommitContext:
    return CommitContext(
        commit_id=compute_snapshot_commit_id(repo_path),
        mode="snapshot",
        base_commit=None,
        head_commit=None,
        changes=[],
    )


@dataclass(frozen=True)
class CommitMeta:
    """Lightweight commit metadata for LLM context."""
    sha: str
    author: str
    date: str
    message: str


def get_commit_meta(repo_path: str, ref: str = "HEAD") -> CommitMeta:
    """Return author, date, and message for *ref* in *repo_path*."""
    root = Path(repo_path)
    if not is_git_repo(root):
        return CommitMeta(sha="", author="", date="", message="")

    sha     = git_output(root, "rev-parse", "--short", ref) or ""
    author  = git_output(root, "log", "-1", "--format=%an", ref) or ""
    date    = git_output(root, "log", "-1", "--format=%ad", "--date=short", ref) or ""
    message = git_output(root, "log", "-1", "--format=%s", ref) or ""
    return CommitMeta(sha=sha, author=author, date=date, message=message)

