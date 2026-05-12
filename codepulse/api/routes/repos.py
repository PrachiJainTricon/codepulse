"""
GET /repos  —  list all indexed repositories.
"""

from __future__ import annotations

from fastapi import APIRouter

from codepulse.db.run_store import RepoStore

router = APIRouter()


@router.get("/")
def list_repos() -> list[dict]:
    """Return all repositories registered in the local SQLite store."""
    store = RepoStore()
    return [
        {
            "id": r.id,
            "name": r.name,
            "root_path": r.root_path,
            "languages": r.languages,
            "total_files": r.total_files,
            "total_symbols": r.total_symbols,
            "last_indexed": r.last_indexed,
        }
        for r in store.list_all()
    ]
