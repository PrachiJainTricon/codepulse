"""
POST /analysis/diff  —  run blast-radius analysis on a git diff.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from codepulse.git.diff_resolver import resolve_diff
from codepulse.agents.pipeline import run_pipeline
from codepulse.agents.state import RiskResult

router = APIRouter()


class DiffRequest(BaseModel):
    repo_path: str
    commit_ref: str = "HEAD~1"


@router.post("/diff", response_model=None)
def analyse_diff(body: DiffRequest) -> RiskResult:
    """Analyse the blast radius of *commit_ref* in *repo_path*."""
    repo_path = str(Path(body.repo_path).resolve())

    try:
        changed = resolve_diff(repo_path, commit_ref=body.commit_ref)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not changed:
        raise HTTPException(status_code=204, detail="No changed symbols detected in this diff.")

    result: RiskResult = run_pipeline(
        repo_path=repo_path,
        commit_ref=body.commit_ref,
        changed_symbols=changed,
    )
    return result
