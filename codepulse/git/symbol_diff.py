"""
P3 — Extract changed symbol names directly from diff lines.

No parser dependency required. Uses regex patterns against the +/- lines
in the diff to find function/class definitions that were touched.

Supports: Python, TypeScript / JavaScript.
Falls back gracefully: if nothing is detected, the caller gets an empty list
and falls back to file-level tracking.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from codepulse.agents.state import ChangedSymbol


# ── Regex patterns per language ───────────────────────────────────────────────

_PYTHON_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\("), "function"),
    (re.compile(r"^\s*class\s+(\w+)\s*[:(]"), "class"),
]

_TS_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\("), "function"),
    (re.compile(r"^\s*(?:export\s+)?class\s+(\w+)\s*[{(]"), "class"),
    # arrow functions: export const foo = (...) =>
    (re.compile(r"^\s*(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\("), "function"),
    # method inside a class body
    (re.compile(r"^\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?::\s*\w+\s*)?\{"), "method"),
]


def _patterns_for(file_path: str) -> list[tuple[re.Pattern, str]]:
    suffix = Path(file_path).suffix.lower()
    if suffix == ".py":
        return _PYTHON_PATTERNS
    if suffix in {".ts", ".tsx", ".js", ".jsx"}:
        return _TS_PATTERNS
    return []


# ── Core extraction ───────────────────────────────────────────────────────────

def _extract_from_lines(
    lines: list[str],
    patterns: list[tuple[re.Pattern, str]],
    change_type: str,
    file_path: str,
    start_line: Optional[int],
) -> list[ChangedSymbol]:
    found: list[ChangedSymbol] = []
    seen: set[str] = set()

    for i, line in enumerate(lines):
        for pattern, kind in patterns:
            m = pattern.match(line)
            if m:
                name = m.group(1)
                if name in seen:
                    continue
                seen.add(name)
                found.append(
                    ChangedSymbol(
                        file=file_path,
                        symbol=name,
                        kind=kind,  # type: ignore[arg-type]
                        change_type=change_type,  # type: ignore[arg-type]
                        start_line=(start_line + i) if start_line else None,
                        end_line=None,
                    )
                )
    return found


# ── Public API ────────────────────────────────────────────────────────────────

def extract_symbols_from_hunk(
    file_path: str,
    added_lines: list[str],
    removed_lines: list[str],
    start_line: Optional[int] = None,
) -> list[ChangedSymbol]:
    """
    Given the added/removed lines of one file's diff hunk, return a list
    of ChangedSymbol objects for every function/class definition touched.

    Logic:
    - A symbol appearing only in added_lines  → "added"
    - A symbol appearing only in removed_lines → "deleted"
    - A symbol appearing in both              → "modified"
    """
    patterns = _patterns_for(file_path)
    if not patterns:
        return []

    added_syms = _extract_from_lines(added_lines, patterns, "added", file_path, start_line)
    removed_syms = _extract_from_lines(removed_lines, patterns, "deleted", file_path, start_line)

    added_names = {s["symbol"] for s in added_syms}
    removed_names = {s["symbol"] for s in removed_syms}

    results: list[ChangedSymbol] = []
    seen: set[str] = set()

    for sym in added_syms:
        name = sym["symbol"]
        if name in removed_names:
            sym = dict(sym)  # type: ignore[assignment]
            sym["change_type"] = "modified"
        results.append(sym)  # type: ignore[arg-type]
        seen.add(name)

    for sym in removed_syms:
        if sym["symbol"] not in seen:
            results.append(sym)

    return results
