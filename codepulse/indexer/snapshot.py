"""
SHA-256 based snapshot store for incremental indexing.

On each index run we compare file hashes against the last
recorded snapshot.  Only new or changed files are re-parsed.
After a successful parse, the snapshot is updated.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from codepulse.config import settings
from codepulse.logging import get_logger

log = get_logger(__name__)

# Read files in 64 KB chunks for hashing
_HASH_CHUNK_SIZE = 65_536


def compute_hash(file_path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(_HASH_CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


class SnapshotStore:
    """
    Thin wrapper around the SQLite file_snapshots table.

    Usage::

        with SnapshotStore(repo_root) as store:
            if store.has_changed(file_path, current_hash):
                # parse the file ...
                store.upsert(file_path, current_hash)
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo_key = str(repo_root.resolve())
        self._conn = sqlite3.connect(str(settings.db_path))

    # ── Public API ────────────────────────────────────────────

    def has_changed(self, file_path: Path, current_hash: str) -> bool:
        """
        Return True if the file is new or its hash differs
        from the stored snapshot.
        """
        cursor = self._conn.execute(
            "SELECT hash FROM file_snapshots "
            "WHERE repo_root = ? AND file_path = ?",
            (self._repo_key, str(file_path)),
        )
        row = cursor.fetchone()
        if row is None:
            return True   # new file
        return row[0] != current_hash

    def upsert(self, file_path: Path, file_hash: str) -> None:
        """Insert or update the hash for a single file."""
        self._conn.execute(
            """
            INSERT INTO file_snapshots (repo_root, file_path, hash)
            VALUES (?, ?, ?)
            ON CONFLICT (repo_root, file_path)
            DO UPDATE SET hash       = excluded.hash,
                          indexed_at = datetime('now')
            """,
            (self._repo_key, str(file_path), file_hash),
        )
        self._conn.commit()

    def upsert_batch(self, items: list[tuple[Path, str]]) -> None:
        """Batch upsert multiple (file_path, hash) pairs."""
        self._conn.executemany(
            """
            INSERT INTO file_snapshots (repo_root, file_path, hash)
            VALUES (?, ?, ?)
            ON CONFLICT (repo_root, file_path)
            DO UPDATE SET hash       = excluded.hash,
                          indexed_at = datetime('now')
            """,
            [(self._repo_key, str(fp), h) for fp, h in items],
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()

    # ── Context manager ───────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
