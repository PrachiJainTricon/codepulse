"""
Index service — the core orchestrator for the indexing pipeline.

This module contains zero CLI or UI logic. It is the single
entry point that both the CLI (`index_cmd.py`) and the future
API (`routes/repos.py`) call to index a repository.

Responsibilities:
    1. Register the repo in the database
    2. Scan the file tree
    3. Check snapshot hashes for changes
    4. Dispatch to tree-sitter parsers
    5. Collect ParseResults
    6. Update snapshot + repo stats
    7. Return a structured IndexReport (no printing)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from codepulse.db.migrations import run_migrations
from codepulse.db.run_store import RepoRecord, RepoStore
from codepulse.indexer.parser_worker import parse_file
from codepulse.indexer.repo_scanner import scan_repo
from codepulse.indexer.snapshot import SnapshotStore, compute_hash
from codepulse.logging import get_logger
from codepulse.parsers.base import ParseResult

log = get_logger(__name__)


# ── Return type ──────────────────────────────────────────────


@dataclass
class IndexReport:
    """
    Structured result of an index run.

    Returned to the caller (CLI / API) — they decide how to
    display it.
    """
    repo: RepoRecord
    results: list[ParseResult] = field(default_factory=list)
    skipped_files: int = 0         # files unchanged by hash

    @property
    def total_files(self) -> int:
        return len(self.results)

    @property
    def total_symbols(self) -> int:
        return sum(len(r.symbols) for r in self.results)

    @property
    def total_imports(self) -> int:
        return sum(len(r.imports) for r in self.results)

    @property
    def total_calls(self) -> int:
        return sum(len(r.calls) for r in self.results)

    @property
    def total_exports(self) -> int:
        return sum(len(r.exports) for r in self.results)

    @property
    def languages_found(self) -> set[str]:
        return {r.file.language.value for r in self.results}


# ── Service function ─────────────────────────────────────────


def run_index(repo_path: Path, *, full: bool = False) -> IndexReport:
    """
    Index a repository end-to-end.

    Parameters
    ----------
    repo_path : Path
        Absolute path to the repository root.
    full : bool
        If True, ignore the snapshot cache and re-parse everything.

    Returns
    -------
    IndexReport
        Structured report with parse results and repo record.
    """
    repo_path = repo_path.resolve()

    # Step 0 — ensure DB schema exists
    run_migrations()

    # Step 1 — register the repo (idempotent)
    with RepoStore() as repo_store:
        repo_record = repo_store.register(repo_path)

    # Step 2–5 — scan, hash-check, parse
    results: list[ParseResult] = []
    new_hashes: list[tuple[Path, str]] = []
    skipped = 0

    with SnapshotStore(repo_path) as snap:
        for file_path, language in scan_repo(repo_path):
            file_hash = compute_hash(file_path)
            rel_path = file_path.relative_to(repo_path)

            # Incremental check
            if not full and not snap.has_changed(rel_path, file_hash):
                skipped += 1
                continue

            result = parse_file(file_path, repo_path, language, file_hash)
            if result is not None:
                results.append(result)
                new_hashes.append((rel_path, file_hash))

        # Step 6a — persist snapshot hashes
        snap.upsert_batch(new_hashes)

    # Step 6b — update repo stats
    report = IndexReport(
        repo=repo_record,
        results=results,
        skipped_files=skipped,
    )

    with RepoStore() as repo_store:
        if full:
            # Full run has the complete picture — overwrite stats.
            repo_store.update_stats(
                str(repo_path),
                languages=", ".join(sorted(report.languages_found)),
                total_files=report.total_files,
                total_symbols=report.total_symbols,
                total_imports=report.total_imports,
                total_calls=report.total_calls,
                total_exports=report.total_exports,
            )
        else:
            # Incremental run only saw changed files — don't clobber
            # the totals from the last full run; just bump the timestamp.
            repo_store.touch(str(repo_path))
        # Re-fetch to get updated timestamps
        report.repo = repo_store.get_by_path(str(repo_path))  # type: ignore

    log.info(
        f"Index complete: {report.total_files} parsed, "
        f"{skipped} unchanged"
    )

    return report
