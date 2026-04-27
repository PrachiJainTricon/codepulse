"""
Route source files to the correct language parser.

This is the central dispatch layer: given a file path,
language, and source bytes, it returns a ParseResult.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from codepulse.indexer.language_detector import detect_language
from codepulse.indexer.repo_scanner import scan_repo
from codepulse.indexer.snapshot import compute_hash
from codepulse.logging import get_logger
from codepulse.parsers import get_parser
from codepulse.parsers.base import FileInfo, Language, ParseResult

log = get_logger(__name__)


def parse_file(
    file_path: Path,
    repo_root: Path,
    language: Language,
    file_hash: str,
) -> ParseResult | None:
    """
    Parse a single file and return its ParseResult.

    Returns None if the file cannot be read or parsing fails.

    Parameters
    ----------
    file_path : Path
        Absolute path to the source file.
    repo_root : Path
        Absolute path to the repository root.
    language : Language
        Detected language enum.
    file_hash : str
        Pre-computed SHA-256 hash of the file.
    """
    rel_path = str(file_path.relative_to(repo_root))

    # Read source bytes
    try:
        source = file_path.read_bytes()
    except OSError as exc:
        log.warning(f"Cannot read {rel_path}: {exc}")
        return None

    file_info = FileInfo(path=rel_path, language=language, hash=file_hash)

    # Dispatch to the right language parser
    parser = get_parser(language)
    try:
        result = parser.parse(source, file_info)
        log.debug(
            f"Parsed {rel_path}: "
            f"{len(result.symbols)} symbols, "
            f"{len(result.imports)} imports, "
            f"{len(result.calls)} calls"
        )
        return result
    except Exception as exc:
        log.warning(f"Parse error in {rel_path}: {exc}")
        return None


def parse_all_files(repo_path: Path) -> list[ParseResult]:
    """Parse every indexable file in `repo_path` (full scan, no snapshot cache)."""
    results: list[ParseResult] = []
    for abs_path, language in scan_repo(repo_path):
        file_hash = compute_hash(abs_path)
        parsed = parse_file(abs_path, repo_path, language, file_hash)
        if parsed is not None:
            results.append(parsed)
    return results


def parse_changed_files(
    repo_path: Path,
    rel_paths: Iterable[str],
) -> list[ParseResult]:
    """Parse a specific set of repo-relative files.

    Files with unsupported languages or missing from disk are skipped silently.
    """
    results: list[ParseResult] = []
    for rel_path in sorted(set(rel_paths)):
        rel = Path(rel_path)
        language = detect_language(rel)
        if language is None:
            continue
        abs_path = repo_path / rel
        if not abs_path.is_file():
            continue
        file_hash = compute_hash(abs_path)
        parsed = parse_file(abs_path, repo_path, language, file_hash)
        if parsed is not None:
            results.append(parsed)
    return results
