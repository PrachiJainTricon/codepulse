"""
Walk a repository tree and yield files eligible for indexing.

Respects .gitignore patterns so that build artefacts,
node_modules, __pycache__ etc. are never sent to a parser.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pathspec

from codepulse.config import settings
from codepulse.indexer.language_detector import detect_language
from codepulse.logging import get_logger
from codepulse.parsers.base import Language

log = get_logger(__name__)

# Directories we always skip regardless of .gitignore
_ALWAYS_SKIP_DIRS: set[str] = {
    ".git", "__pycache__", "node_modules", ".tox",
    ".mypy_cache", ".pytest_cache", "dist", "build",
    ".venv", "venv", ".eggs", ".idea", ".vscode",
}


def _load_gitignore(repo_root: Path) -> pathspec.PathSpec:
    """Load .gitignore patterns from the repository root."""
    gitignore_path = repo_root / ".gitignore"
    patterns: list[str] = []
    if gitignore_path.is_file():
        patterns = gitignore_path.read_text(errors="replace").splitlines()
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def scan_repo(repo_root: Path) -> Iterator[tuple[Path, Language]]:
    """
    Yield (absolute_path, language) for every indexable file.

    Skips:
      - directories in _ALWAYS_SKIP_DIRS
      - paths matched by .gitignore
      - files with unsupported extensions
      - files larger than settings.max_file_size_kb
    """
    repo_root = repo_root.resolve()
    spec = _load_gitignore(repo_root)
    max_bytes = settings.max_file_size_kb * 1024

    file_count = 0
    skipped_count = 0

    for path in sorted(repo_root.rglob("*")):
        # --- Skip directories we never want ---
        if any(part in _ALWAYS_SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue

        # --- Relative path for .gitignore matching ---
        rel = path.relative_to(repo_root)
        if spec.match_file(str(rel)):
            skipped_count += 1
            continue

        # --- Check language support ---
        lang = detect_language(rel)
        if lang is None:
            continue

        # --- Skip oversized files ---
        try:
            if path.stat().st_size > max_bytes:
                log.debug(f"Skipping large file: {rel}")
                skipped_count += 1
                continue
        except OSError:
            continue

        file_count += 1
        yield path, lang

    log.info(
        f"Scan complete: [bold green]{file_count}[/] files to index, "
        f"{skipped_count} skipped"
    )
