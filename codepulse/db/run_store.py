"""
Repo registry — tracks which repositories codepulse knows about.

Every repo you index gets an entry here with stats and timestamps.
Both the CLI and the future API/UI read from this same store.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from codepulse.config import settings
from codepulse.logging import get_logger

log = get_logger(__name__)


@dataclass
class RepoRecord:
    """One registered repository."""
    id: int
    name: str
    root_path: str
    languages: str
    total_files: int
    total_symbols: int
    total_imports: int
    total_calls: int
    total_exports: int
    last_indexed: str | None
    created_at: str


class RepoStore:
    """
    CRUD operations on the repos table.

    Usage::

        store = RepoStore()
        store.register("/home/user/my-project")
        store.update_stats("/home/user/my-project", ...)
        repos = store.list_all()
        store.close()
    """

    def __init__(self) -> None:
        self._conn = sqlite3.connect(str(settings.db_path))
        self._conn.row_factory = sqlite3.Row

    # ── Register / upsert a repo ──────────────────────────────

    def register(self, repo_root: Path) -> RepoRecord:
        """
        Register a repo (or return existing).

        The repo name defaults to the directory name.
        """
        root_str = str(repo_root.resolve())
        name = repo_root.resolve().name

        self._conn.execute(
            """
            INSERT INTO repos (name, root_path)
            VALUES (?, ?)
            ON CONFLICT (root_path) DO NOTHING
            """,
            (name, root_str),
        )
        self._conn.commit()
        return self.get_by_path(root_str)  # type: ignore[return-value]

    # ── Update stats after indexing ───────────────────────────

    def update_stats(
        self,
        repo_root: str,
        *,
        languages: str,
        total_files: int,
        total_symbols: int,
        total_imports: int,
        total_calls: int,
        total_exports: int,
    ) -> None:
        """Update the stats columns after a successful index run."""
        self._conn.execute(
            """
            UPDATE repos
            SET languages     = ?,
                total_files   = ?,
                total_symbols = ?,
                total_imports = ?,
                total_calls   = ?,
                total_exports = ?,
                last_indexed  = datetime('now')
            WHERE root_path = ?
            """,
            (
                languages,
                total_files,
                total_symbols,
                total_imports,
                total_calls,
                total_exports,
                repo_root,
            ),
        )
        self._conn.commit()

    def touch(self, repo_root: str) -> None:
        """Bump ``last_indexed`` without changing stats."""
        self._conn.execute(
            "UPDATE repos SET last_indexed = datetime('now') WHERE root_path = ?",
            (repo_root,),
        )
        self._conn.commit()

    # ── Queries ───────────────────────────────────────────────

    def get_by_path(self, root_path: str) -> RepoRecord | None:
        """Look up a repo by its absolute root path."""
        row = self._conn.execute(
            "SELECT * FROM repos WHERE root_path = ?", (root_path,)
        ).fetchone()
        return self._to_record(row) if row else None

    def get_by_id(self, repo_id: int) -> RepoRecord | None:
        """Look up a repo by its numeric id."""
        row = self._conn.execute(
            "SELECT * FROM repos WHERE id = ?", (repo_id,)
        ).fetchone()
        return self._to_record(row) if row else None

    def list_all(self) -> list[RepoRecord]:
        """Return all registered repos, newest first."""
        rows = self._conn.execute(
            "SELECT * FROM repos ORDER BY last_indexed DESC NULLS LAST"
        ).fetchall()
        return [self._to_record(r) for r in rows]

    def remove(self, root_path: str) -> bool:
        """
        Unregister a repo and delete its snapshot hashes.
        Returns True if the repo existed.
        """
        cursor = self._conn.execute(
            "DELETE FROM repos WHERE root_path = ?", (root_path,)
        )
        self._conn.execute(
            "DELETE FROM file_snapshots WHERE repo_root = ?", (root_path,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # ── Lifecycle ─────────────────────────────────────────────

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ── Internal ──────────────────────────────────────────────

    @staticmethod
    def _to_record(row: sqlite3.Row) -> RepoRecord:
        return RepoRecord(
            id=row["id"],
            name=row["name"],
            root_path=row["root_path"],
            languages=row["languages"],
            total_files=row["total_files"],
            total_symbols=row["total_symbols"],
            total_imports=row["total_imports"],
            total_calls=row["total_calls"],
            total_exports=row["total_exports"],
            last_indexed=row["last_indexed"],
            created_at=row["created_at"],
        )
