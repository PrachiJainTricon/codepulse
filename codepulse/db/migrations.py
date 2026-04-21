"""
Run SQLite schema migrations on first use.

Ensures all required tables exist before the indexer
starts writing data.
"""

from __future__ import annotations

import sqlite3

from codepulse.config import settings
from codepulse.db.models import (
    CREATE_REPOS_TABLE,
    CREATE_SNAPSHOT_INDEX,
    CREATE_SNAPSHOT_TABLE,
)
from codepulse.logging import get_logger

log = get_logger(__name__)


def run_migrations() -> None:
    """
    Create or update the SQLite schema.

    Safe to call multiple times — every statement uses
    IF NOT EXISTS.
    """
    # Ensure the data directory exists
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(settings.db_path))
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_REPOS_TABLE)
        cursor.execute(CREATE_SNAPSHOT_TABLE)
        cursor.execute(CREATE_SNAPSHOT_INDEX)
        conn.commit()
        log.info(f"Database ready at [bold]{settings.db_path}[/]")
    finally:
        conn.close()
