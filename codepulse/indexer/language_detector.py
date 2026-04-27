"""
Map file extensions to supported languages.

Returns None for unsupported files so the indexer can skip them.
Detection is purely extension-based — fast and deterministic.
"""

from __future__ import annotations

from pathlib import Path

from codepulse.parsers.base import Language

# ── Extension → Language lookup ───────────────────────────────

_EXTENSION_MAP: dict[str, Language] = {
    # Python
    ".py":   Language.PYTHON,
    ".pyi":  Language.PYTHON,
    # JavaScript
    ".js":   Language.JAVASCRIPT,
    ".jsx":  Language.JAVASCRIPT,
    ".mjs":  Language.JAVASCRIPT,
    ".cjs":  Language.JAVASCRIPT,
    # TypeScript
    ".ts":   Language.TYPESCRIPT,
    ".tsx":  Language.TYPESCRIPT,
    # Java
    ".java": Language.JAVA,
    # C / C++
    ".cpp":  Language.CPP,
    ".cxx":  Language.CPP,
    ".cc":   Language.CPP,
    ".c":    Language.CPP,      # treat C as C++ subset for parsing
    ".h":    Language.CPP,
    ".hpp":  Language.CPP,
    ".hxx":  Language.CPP,
}


def detect_language(file_path: str | Path) -> Language | None:
    """
    Return the Language enum for a file, or None if unsupported.
    """
    suffix = Path(file_path).suffix.lower()
    return _EXTENSION_MAP.get(suffix)
