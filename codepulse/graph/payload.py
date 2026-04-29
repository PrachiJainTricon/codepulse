"""Build the JSON payload that `Neo4jIngestion.ingest_from_json` consumes.

Two entry points:

* ``to_legacy_file_result`` — convert a single ``ParseResult`` into the
  per-file dict expected by the graph ingestion layer.
* ``build_graph_payload`` — end-to-end helper: given a repo path, resolve
  the commit context, parse the right set of files, and assemble the full
  payload (repo / commit / changes / per-file results).

The CLI only needs to call ``build_graph_payload``; everything else is an
implementation detail.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codepulse.git import (
    CommitContext,
    get_repo_id,
    get_repo_name,
    resolve_commit_context,
)
from codepulse.git.diff_resolver import git_working_tree_changes
from codepulse.indexer.parser_worker import (
    parse_all_files,
    parse_changed_files,
)
from codepulse.parsers.base import ImportInfo, ParseResult, SymbolInfo


# ── Public API ────────────────────────────────────────────────


def build_graph_payload(repo_path: Path, *, full: bool = False) -> dict[str, Any]:
    """Resolve commit context, parse files, and return the ingestion JSON.

    When *full* is True every tracked file is parsed regardless of the
    last-commit diff – this is the expected behaviour for initial graph
    population and for ``codepulse index --full --to-graph``.
    """
    repo_path = repo_path.resolve()
    repo_id = get_repo_id(repo_path)
    repo_name = get_repo_name(repo_path)
    commit_ctx = resolve_commit_context(repo_path)

    results = _parse_for_context(repo_path, commit_ctx, full=full)

    return {
        "root": str(repo_path),
        "repo_id": repo_id,
        "repo_name": repo_name,
        "commit_id": commit_ctx.commit_id,
        "mode": commit_ctx.mode,
        "base_commit": commit_ctx.base_commit,
        "head_commit": commit_ctx.head_commit,
        "files_parsed": len(results),
        "changes": [
            {
                "repo_id": repo_id,
                "commit_id": commit_ctx.commit_id,
                "file_path": change.file_path,
                "status": change.status,
                "type": change.type,
            }
            for change in commit_ctx.changes
        ],
        "results": [
            to_legacy_file_result(
                result,
                repo_id,
                repo_name,
                commit_id=commit_ctx.commit_id,
            )
            for result in results
        ],
    }


def to_legacy_file_result(
    result: ParseResult,
    repo_id: str,
    repo_name: str,
    *,
    commit_id: str | None = None,
) -> dict[str, Any]:
    """Convert a ``ParseResult`` into the per-file dict used by ingestion."""
    rel_path = result.file.path.replace("\\", "/")
    module_name = _module_name_from_path(rel_path)
    imports = _imports_to_strings(result.imports)
    calls_by_symbol = _group_calls_by_symbol(result)

    symbols: list[dict[str, Any]] = []
    for symbol in result.symbols:
        symbols.append(
            {
                "type": symbol.kind.value,
                "name": symbol.name,
                # Prefix qualified name with repo_id for cross-repo uniqueness.
                "qualified_name": f"{repo_id}.{_qualified_name(module_name, symbol)}",
                "start_line": symbol.line,
                "end_line": symbol.end_line,
                "file_path": rel_path,
                "repo_id": repo_id,
                "repo": repo_name,
                "commit_id": commit_id,
                "calls": calls_by_symbol.get(_symbol_key(symbol), []),
                "imports": imports,
            }
        )

    return {
        "repo_id": repo_id,
        "commit_id": commit_id,
        "path": rel_path,
        "language": result.file.language.value,
        "hash": result.file.hash,
        "symbols": symbols,
    }


# ── Internals ─────────────────────────────────────────────────


def _parse_for_context(
    repo_path: Path,
    commit_ctx: CommitContext,
    *,
    full: bool = False,
) -> list[ParseResult]:
    """Decide between full-scan and diff-driven parsing based on mode."""
    if full or commit_ctx.mode == "snapshot":
        return parse_all_files(repo_path)

    # Incremental: only parse files with uncommitted working-tree changes.
    # The last commit should already be in Neo4j from a prior --to-graph
    # or --full --to-graph run.
    wt_changes = git_working_tree_changes(repo_path)
    changed = {
        change.file_path
        for change in wt_changes
        if change.status in {"A", "M", "R", "C"}
    }
    if not changed:
        return []
    return parse_changed_files(repo_path, changed)


def _group_calls_by_symbol(
    result: ParseResult,
) -> dict[tuple[str, int, int, str | None], list[str]]:
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
