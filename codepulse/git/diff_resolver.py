"""Resolve a list of changed files between two git commits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codepulse.git._gitcli import git_output
from codepulse.indexer.language_detector import detect_language


@dataclass(frozen=True)
class ChangeEntry:
    file_path: str
    status: str  # single-letter git status: A / M / D / R / C
    type: str    # normalized: added / modified / deleted


def git_diff_changes(repo_path: Path, base: str, head: str) -> list[ChangeEntry]:
    """Return `ChangeEntry` rows for `git diff --name-status base head`."""
    output = git_output(repo_path, "diff", "--name-status", base, head)
    if not output:
        return []
    changes: list[ChangeEntry] = []
    for line in output.splitlines():
        parts = [p for p in line.split("\t") if p]
        if len(parts) < 2:
            continue
        status = parts[0][0]
        change_type = _status_to_type(status)
        if change_type is None:
            continue
        file_path = parts[-1].replace("\\", "/")
        changes.append(ChangeEntry(file_path=file_path, status=status, type=change_type))
    return changes


def git_initial_commit_changes(repo_path: Path) -> list[ChangeEntry]:
    """All tracked language files for the initial commit (no base to diff against)."""
    output = git_output(repo_path, "ls-tree", "-r", "--name-only", "HEAD")
    if not output:
        return []
    changes: list[ChangeEntry] = []
    for line in output.splitlines():
        rel = line.strip().replace("\\", "/")
        if not rel or detect_language(Path(rel)) is None:
            continue
        changes.append(ChangeEntry(file_path=rel, status="A", type="added"))
    return changes


def _status_to_type(status: str) -> str | None:
    if status == "A":
        return "added"
    if status == "M":
        return "modified"
    if status == "D":
        return "deleted"
    if status in {"R", "C"}:
        return "modified"
    return None
