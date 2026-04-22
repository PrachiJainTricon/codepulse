"""
Route source files to the correct language parser.

This is the central dispatch layer: given a file path,
language, and source bytes, it returns a ParseResult.
"""

from __future__ import annotations

from pathlib import Path

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
