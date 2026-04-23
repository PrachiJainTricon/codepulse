"""Compatibility adapter that exposes parse_directory() for Neo4j."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from codepulse.indexer.parser_worker import parse_file
from codepulse.indexer.repo_scanner import scan_repo
from codepulse.indexer.snapshot import compute_hash
from codepulse.parsers.base import ImportInfo, ParseResult, SymbolInfo


def parse_directory(
    directory: Path,
    *,
    max_depth: int = 4,
    include_text: bool = False,
) -> dict[str, Any]:
    """Parse a local directory and return JSON for Neo4j ingestion."""
    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"Directory does not exist: {directory}")

    root = directory.resolve()
    # Get repo name for context prefixing
    repo_name = root.name
    parsed_results: list[ParseResult] = []

    for file_path, language in scan_repo(root):
        file_hash = compute_hash(file_path)
        parsed = parse_file(file_path, root, language, file_hash)
        if parsed is not None:
            parsed_results.append(parsed)

    del max_depth
    del include_text

    return {
        "root": str(root),
        "repo_name": repo_name,
        "files_parsed": len(parsed_results),
        "results": [to_legacy_file_result(result, repo_name) for result in parsed_results],
    }


def to_legacy_file_result(result: ParseResult, repo_name: str) -> dict[str, Any]:
    rel_path = result.file.path.replace("\\", "/")
    # Prefix with repo name for unique identification
    repo_path = f"{repo_name}/{rel_path}"
    module_name = _module_name_from_path(rel_path)
    imports = _imports_to_strings(result.imports)
    calls_by_symbol = _group_calls_by_symbol(result)

    symbols: list[dict[str, Any]] = []
    for symbol in result.symbols:
        symbols.append(
            {
                "type": symbol.kind.value,
                "name": symbol.name,
                # Prefix qualified name with repo
                "qualified_name": f"{repo_name}.{_qualified_name(module_name, symbol)}",
                "start_line": symbol.line,
                "end_line": symbol.end_line,
                "file_path": repo_path,  # Include repo prefix
                "calls": calls_by_symbol.get(_symbol_key(symbol), []),
                "imports": imports,
            }
        )

    return {
        "path": repo_path,  # Include repo prefix
        "language": result.file.language.value,
        "hash": result.file.hash,
        "symbols": symbols,
    }


def _group_calls_by_symbol(result: ParseResult) -> dict[tuple[str, int, int, str | None], list[str]]:
    grouped: dict[tuple[str, int, int, str | None], set[str]] = {
        _symbol_key(symbol): set() for symbol in result.symbols
    }

    for call in result.calls:
        caller = call.caller
        if caller in {"<module>", "<class>", "<global>"}:
            continue

        candidates = [
            symbol
            for symbol in result.symbols
            if symbol.line <= call.line <= symbol.end_line
        ]
        hinted = [symbol for symbol in candidates if symbol.name == caller]
        if not hinted:
            continue

        target = min(hinted, key=lambda symbol: symbol.end_line - symbol.line)
        grouped[_symbol_key(target)].add(call.callee)

    return {key: sorted(values) for key, values in grouped.items()}


def _symbol_key(symbol: SymbolInfo) -> tuple[str, int, int, str | None]:
    return (symbol.name, symbol.line, symbol.end_line, symbol.parent)


def _imports_to_strings(imports: list[ImportInfo]) -> list[str]:
    normalized: set[str] = set()
    for item in imports:
        if item.name == "*":
            statement = f"from {item.module} import *"
        elif item.module == item.name:
            statement = f"import {item.module}"
        else:
            statement = f"from {item.module} import {item.name}"

        if item.alias:
            statement = f"{statement} as {item.alias}"
        normalized.add(statement)
    return sorted(normalized)


def _module_name_from_path(path: str) -> str:
    stem = path.rsplit(".", 1)[0].replace("/", ".")
    if stem.endswith(".__init__"):
        stem = stem[: -len(".__init__")]
    return stem


def _qualified_name(module_name: str, symbol: SymbolInfo) -> str:
    parts: list[str] = []
    if module_name:
        parts.append(module_name)
    if symbol.parent:
        parts.append(symbol.parent)
    parts.append(symbol.name)
    return ".".join(parts)