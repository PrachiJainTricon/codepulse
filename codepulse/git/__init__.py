"""Git helpers: repo identity, commit context, diff resolution."""

from codepulse.git.commit_meta import (
    CommitContext,
    compute_snapshot_commit_id,
    resolve_commit_context,
)
from codepulse.git.diff_resolver import (
    ChangeEntry,
    git_diff_changes,
    git_initial_commit_changes,
)
from codepulse.git.repo_identity import (
    get_current_repo,
    get_repo_id,
    get_repo_name,
)

__all__ = [
    "ChangeEntry",
    "CommitContext",
    "compute_snapshot_commit_id",
    "get_current_repo",
    "get_repo_id",
    "get_repo_name",
    "git_diff_changes",
    "git_initial_commit_changes",
    "resolve_commit_context",
]
