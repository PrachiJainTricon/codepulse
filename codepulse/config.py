"""
Central configuration for codepulse.

All paths, URIs, and tunables live here so every module
imports one source of truth.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Immutable application configuration."""

    # ── Neo4j (used later, not in week-1 scope) ──────────────
    neo4j_uri: str = os.getenv("CODEPULSE_NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("CODEPULSE_NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("CODEPULSE_NEO4J_PASSWORD", "codepulse")

    # ── SQLite snapshot store ─────────────────────────────────
    data_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("CODEPULSE_DATA_DIR", str(Path.home() / ".codepulse"))
        )
    )

    @property
    def db_path(self) -> Path:
        """Path to the SQLite database for snapshot hashes."""
        return self.data_dir / "codepulse.db"

    # ── Indexer tunables ──────────────────────────────────────
    max_file_size_kb: int = 512   # skip files larger than this
    batch_size: int = 50          # files per graph-write batch


# Module-level singleton — import this everywhere
settings = Settings()
