# AGENTS.md

## Project facts (do not re-discover)
- Python package entrypoint is `codepulse = codepulse.cli.main:app` (`pyproject.toml`).
- CLI commands currently registered: `index`, `remove`, `repos`, `graph`.
- `index` supports `--full` and `--to-graph`.
- `graph clear` exists.
- Neo4j settings come from env vars: `CODEPULSE_NEO4J_URI`, `CODEPULSE_NEO4J_USER`, `CODEPULSE_NEO4J_PASSWORD` (`codepulse/config.py`).
- `run_index` auto-runs SQLite migrations and uses snapshot-based incremental indexing.
- Repo scanning respects `.gitignore`, always-skip dirs, and `max_file_size_kb`.

## Module layout (where things live)
- `codepulse/cli/` — Typer commands only (no business logic). Thin UI layer.
- `codepulse/indexer/` — scan + parse pipeline. Shared parse helpers (`parse_all_files`, `parse_changed_files`) live in `parser_worker.py`.
- `codepulse/parsers/` — tree-sitter language parsers.
- `codepulse/git/` — all git-related helpers:
  - `repo_identity.py` → `get_repo_id`, `get_repo_name`, `get_current_repo`
  - `commit_meta.py` → `CommitContext`, `resolve_commit_context`, `compute_snapshot_commit_id`
  - `diff_resolver.py` → `ChangeEntry`, `git_diff_changes`, `git_initial_commit_changes`
  - `_gitcli.py` → internal `git_output`, `is_git_repo`
- `codepulse/graph/` — Neo4j layer:
  - `client.py` → `Neo4jClient`, `Neo4jIngestion`
  - `schema.py` → node dataclasses, constraints/indexes, Cypher `IngestQueries`
  - `payload.py` → `build_graph_payload`, `to_legacy_file_result` (ParseResult → ingestion JSON)
- `codepulse/db/` — SQLite snapshot cache + repo registry.

## Ingestion flow (canonical path)
1. `cli.index_cmd.index` parses arguments, calls `run_index`.
2. If `--to-graph`: `cli.index_cmd._push_to_graph` calls `graph.build_graph_payload(repo_path)`.
3. `build_graph_payload` resolves commit context via `git.resolve_commit_context`, then parses with `indexer.parser_worker.parse_all_files` (snapshot mode) or `parse_changed_files` (commit mode).
4. `graph.Neo4jIngestion.ingest_from_json(payload)` upserts Repo/Commit/Change/File/Symbol/Package and relationships.

## Key graph model facts
- Every non-Repo node carries `(repo_id, commit_id)`; MERGE keys are scoped by these.
- `Symbol.qualified_name` is prefixed with `repo_id` (not `repo_name`) for cross-repo uniqueness.
- Symbols from a deleted file get tombstoned (`deleted=true, deleted_in_commit=<sha>`) rather than removed.
- One Neo4j database holds many repos; filter by `repo_id` when querying.

## Setup commands (run in this order)
- `python -m venv .venv`
- Windows PowerShell: `.\.venv\Scripts\Activate.ps1`
- `python -m pip install -U pip`
- `pip install -e .`

## Focused verification commands
- CLI wiring: `codepulse --help`
- Check command registration: `codepulse index --help`, `codepulse remove --help`, `codepulse repos --help`, `codepulse graph --help`
- Validate index flags: `codepulse index --help` (confirm `--full` and `--to-graph`)
- Validate graph clear command: `codepulse graph clear --help`

## When editing indexing/ingestion code: required command order
- 1) `codepulse index --help` (confirm CLI surface first)
- 2) Run an index pass on a target repo: `codepulse index <repo_path>`
- 3) Validate incremental behavior: rerun `codepulse index <repo_path>` (should use snapshot-based incremental path)
- 4) If graph-related changes: run `codepulse index <repo_path> --to-graph`
- 5) If resetting graph state during testing: `codepulse graph clear`

## Do not assume (critical gotchas)
- `codepulse remove` only unregisters from SQLite/snapshots; it does **not** delete Neo4j nodes.
- To wipe Neo4j data, use `codepulse graph clear`.
- Changing `Symbol.qualified_name` formatting requires clearing Neo4j (old nodes become orphans since `qualified_name` is part of the MERGE key).
- `codepulse/tree_parser.py` and `codepulse/utils.py` no longer exist; their contents moved to `codepulse/graph/payload.py` and `codepulse/git/` respectively.

## Current quality gates in this repo
- No CI workflows detected.
- No lint/typecheck configs detected.
- `tests/` exists, but current test files are empty placeholders.
