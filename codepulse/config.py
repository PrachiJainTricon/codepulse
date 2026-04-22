"""
Central config — reads from environment / .env file.

Load once at startup:
    from codepulse.config import settings
    print(settings.neo4j_uri)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv() -> None:
    """Best-effort .env loader — works without python-dotenv installed."""
    env_path = Path(".env")
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        # Manual fallback
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    # LLM
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    openai_api_key: str    = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))

    # Neo4j
    neo4j_uri:      str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    neo4j_username: str = field(default_factory=lambda: os.getenv("NEO4J_USERNAME", "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "password"))

    # Analysis defaults
    blast_radius_depth: int = field(
        default_factory=lambda: int(os.getenv("BLAST_RADIUS_DEPTH", "3"))
    )

    @property
    def has_llm(self) -> bool:
        return bool(self.anthropic_api_key or self.openai_api_key)

    @property
    def has_neo4j(self) -> bool:
        return bool(os.getenv("NEO4J_URI"))


settings = Settings()
