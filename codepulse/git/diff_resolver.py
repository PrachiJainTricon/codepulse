"""Resolve a list of changed files between two git commits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codepulse.git._gitcli import git_output, is_git_repo
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


def git_working_tree_changes(repo_path: Path) -> list[ChangeEntry]:
    """Return changes in the working tree (unstaged + staged) vs HEAD."""
    output = git_output(repo_path, "diff", "--name-status", "HEAD")
    staged = git_output(repo_path, "diff", "--name-status", "--cached", "HEAD")
    seen: dict[str, ChangeEntry] = {}
    for raw in (output, staged):
        if not raw:
            continue
        for line in raw.splitlines():
            parts = [p for p in line.split("\t") if p]
            if len(parts) < 2:
                continue
            status = parts[0][0]
            change_type = _status_to_type(status)
            if change_type is None:
                continue
            file_path = parts[-1].replace("\\", "/")
            seen[file_path] = ChangeEntry(
                file_path=file_path, status=status, type=change_type,
            )
    return list(seen.values())


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


# ── High-level adapter ────────────────────────────────────────────────────────

def resolve_diff(repo_path: str, commit_ref: str = "HEAD~1") -> list:
    """
    Return a list of ``ChangedSymbol`` objects for every function/class
    touched by *commit_ref* relative to its parent.

    Uses ``git diff <commit_ref>^..<commit_ref>`` to get the patch, then
    runs symbol extraction on each changed file's hunk lines.

    Raises ``RuntimeError`` if *repo_path* is not a git repository.
    """
    from codepulse.agents.state import ChangedSymbol
    from codepulse.git.symbol_diff import extract_symbols_from_hunk

    root = Path(repo_path)
    if not is_git_repo(root):
        raise RuntimeError(f"{repo_path!r} is not a git repository")

    # Get the unified diff for commit_ref vs its parent
    patch = git_output(root, "diff", f"{commit_ref}^", commit_ref, "-U0")
    if not patch:
        # Might be the initial commit — diff against empty tree
        patch = git_output(
            root,
            "diff",
            "--cached",
            "4b825dc642cb6eb9a060e54bf8d69288fbee4904",  # empty tree SHA
            commit_ref,
            "-U0",
        )
    if not patch:
        return []

    symbols: list[ChangedSymbol] = []
    current_file: str | None = None
    added_lines: list[str] = []
    removed_lines: list[str] = []
    hunk_start: int | None = None

    def _flush():
        nonlocal current_file, added_lines, removed_lines, hunk_start
        if current_file and (added_lines or removed_lines):
            syms = extract_symbols_from_hunk(
                current_file, added_lines, removed_lines, hunk_start
            )
            # If no symbols detected, fall back to a file-level entry
            if not syms:
                # Determine overall change type from lines
                if added_lines and not removed_lines:
                    ct = "added"
                elif removed_lines and not added_lines:
                    ct = "deleted"
                else:
                    ct = "modified"
                syms = [
                    ChangedSymbol(
                        file=current_file,
                        symbol=Path(current_file).stem,
                        kind="unknown",
                        change_type=ct,
                        start_line=hunk_start,
                        end_line=None,
                    )
                ]
            symbols.extend(syms)
        added_lines = []
        removed_lines = []
        hunk_start = None

    for line in patch.splitlines():
        if line.startswith("diff --git "):
            _flush()
            # Parse file name: "diff --git a/foo.py b/foo.py"
            parts = line.split(" b/", 1)
            current_file = parts[-1].strip() if parts else None
        elif line.startswith("--- ") or line.startswith("+++ "):
            continue
        elif line.startswith("@@"):
            _flush()
            # Parse @@ -l,s +l,s @@
            try:
                plus_part = line.split("+")[1].split("@@")[0].strip()
                hunk_start = int(plus_part.split(",")[0])
            except (IndexError, ValueError):
                hunk_start = None
        elif line.startswith("+"):
            added_lines.append(line[1:])
        elif line.startswith("-"):
            removed_lines.append(line[1:])

    _flush()
    return symbols

