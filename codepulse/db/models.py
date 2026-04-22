"""
SQLite table definitions for codepulse local storage.

Tables:
    repos            — registered repositories + metadata
    file_snapshots   — per-file hashes for incremental indexing
"""

from __future__ import annotations

# ── Repos table ───────────────────────────────────────────────

CREATE_REPOS_TABLE = """
CREATE TABLE IF NOT EXISTS repos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    root_path     TEXT NOT NULL UNIQUE,
    languages     TEXT NOT NULL DEFAULT '',
    total_files   INTEGER NOT NULL DEFAULT 0,
    total_symbols INTEGER NOT NULL DEFAULT 0,
    total_imports INTEGER NOT NULL DEFAULT 0,
    total_calls   INTEGER NOT NULL DEFAULT 0,
    total_exports INTEGER NOT NULL DEFAULT 0,
    last_indexed  TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# ── Snapshot table ────────────────────────────────────────────

CREATE_SNAPSHOT_TABLE = """
CREATE TABLE IF NOT EXISTS file_snapshots (
    repo_root  TEXT NOT NULL,
    file_path  TEXT NOT NULL,
    hash       TEXT NOT NULL,
    indexed_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (repo_root, file_path)
);
"""

CREATE_SNAPSHOT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_snapshot_repo
    ON file_snapshots (repo_root);
"""
