# codepulse

**Code intelligence powered by graph analysis.**

codepulse indexes codebases into a Neo4j knowledge graph — extracting files,
symbols (classes, functions, methods), imports, and call relationships —
and tracks how those evolve commit-by-commit. Designed as the retrieval
foundation for AI agents that reason about blast radius, risk, and tests.

---

## Quick Start

```bash
# 1. Clone and setup
git clone <repo-url>
cd codepulse

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows

# 3. Install
pip install -e .

# 4. Start Neo4j
docker run -d --name neo4j-codepulse \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/neo4jadmin neo4j:latest

# 5. Index a repo and push to Neo4j
codepulse index /path/to/your/project --to-graph

# 6. Browse: http://localhost:7474
```

---

## CLI Commands

### `codepulse index`

```bash
codepulse index                         # index current directory
codepulse index /path/to/repo           # index a specific path
codepulse index --full                  # ignore the snapshot cache
codepulse index --to-graph              # also push to Neo4j
```

In a **git** repo, `--to-graph` runs in **commit mode**: it parses only the
files changed between `HEAD~1` and `HEAD` and tags every node with the
current commit id. In a **non-git** directory it falls back to
**snapshot mode** and parses everything.

### `codepulse graph`

```bash
codepulse graph clear                   # wipe every node + relationship in Neo4j
```

### `codepulse repos`

```bash
codepulse repos                         # list indexed repos
codepulse remove /path/to/repo          # unregister + clear snapshot (does NOT touch Neo4j)
```

---

## Configuration

Settings are driven by environment variables (`codepulse/config.py`):

| Variable | Default |
|---|---|
| `CODEPULSE_NEO4J_URI` | `bolt://localhost:7687` |
| `CODEPULSE_NEO4J_USER` | `neo4j` |
| `CODEPULSE_NEO4J_PASSWORD` | `neo4jadmin` |
| `CODEPULSE_DATA_DIR` | `~/.codepulse` (SQLite snapshot cache) |

Neo4j browser: http://localhost:7474

---

## Graph Model

Every node carries a `repo_id` (stable sha1 of the git remote URL, or of
the absolute path for non-git repos) and a `commit_id`. This is how multiple
repos and multiple commit snapshots coexist in the same database.

```
 (Repo)-[:HAS_COMMIT]->(Commit)-[:HAS_CHANGE]->(Change)
   |
   +-[:CONTAINS]->(File)-[:CONTAINS]->(Symbol)-[:CALLS]->(Symbol)
                                         |
                                         +-[:IMPORTS]->(Package)
```

Unique keys (MERGE targets):

| Node | Key |
|---|---|
| `Repo` | `id` |
| `Commit` | `(repo_id, id)` |
| `Change` | `(repo_id, commit_id, file_path)` |
| `File` | `(repo_id, commit_id, path)` |
| `Symbol` | `(repo_id, commit_id, qualified_name)` |
| `Package` | `(repo_id, commit_id, name)` |

`Symbol.qualified_name` is prefixed with `repo_id` (e.g.
`a1b2c3d4e5.codepulse.cli.index_cmd.index`) so identical names across repos
never collide. The human-readable repo name lives on the `repo` property.

**Multi-repo behavior:** Indexing repo A and then repo B leaves both in
the same Neo4j database as two independent subgraphs (no shared nodes).
Filter by `repo_id` in the browser, or run `codepulse graph clear`
between runs to view only one at a time.

### Handy Cypher queries

```cypher
// Everything for one repo
MATCH (n {repo_id: "abc1234567"}) RETURN n

// Who calls `foo`?
MATCH (caller:Symbol)-[:CALLS]->(target:Symbol)
WHERE target.name = "foo" AND target.deleted = false
RETURN caller.qualified_name, target.qualified_name

// Files touched in a commit
MATCH (c:Commit {id: "<sha>"})-[:HAS_CHANGE]->(ch:Change)
RETURN ch.file_path, ch.type
```

---

## Project Structure

```
codepulse/
  cli/                            # Typer commands (UI only, no business logic)
    main.py                       # entry point, sub-command registration
    index_cmd.py                  # codepulse index
    graph_cmd.py                  # codepulse graph
    repos_cmd.py                  # codepulse repos

  indexer/                        # Scan + parse pipeline
    repo_scanner.py               # walk tree, respect .gitignore
    language_detector.py          # extension → Language enum
    snapshot.py                   # SQLite hash cache for incremental indexing
    parser_worker.py              # parse_file + parse_all_files + parse_changed_files
    index_service.py              # orchestrates full indexing run

  parsers/                        # Tree-sitter language parsers
    base.py                       # ParseResult, SymbolInfo, ImportInfo
    python_parser.py
    typescript_parser.py
    java_parser.py
    cpp_parser.py

  git/                            # All git-related helpers
    repo_identity.py              # get_repo_id, get_repo_name
    commit_meta.py                # resolve_commit_context, snapshot fallback
    diff_resolver.py              # git diff --name-status → ChangeEntry list
    _gitcli.py                    # internal subprocess wrapper

  graph/                          # Neo4j layer
    client.py                     # Neo4jClient, Neo4jIngestion
    schema.py                     # node dataclasses + constraints + Cypher queries
    payload.py                    # ParseResult → ingestion JSON (build_graph_payload)

  db/                             # SQLite (snapshot cache + repo registry)
    migrations.py
    run_store.py
    models.py

  config.py                       # env-driven Settings singleton
  logging.py
```

---

## Architecture

```
codepulse index [--to-graph]
       │
       ▼
  run_index  (indexer.index_service)
       │
       ├─ repo_scanner  ──►  snapshot  ──►  parser_worker  ──►  parsers
       │
       ▼                                                 (builds ParseResult)
  IndexReport ──► pretty-printed to terminal

       │   (if --to-graph)
       ▼
  build_graph_payload  (graph.payload)
       │
       ├─ git.resolve_commit_context    (commit sha + changed files, or snapshot)
       ├─ parser_worker.parse_all_files | parse_changed_files
       └─ to_legacy_file_result         (per-file → ingestion dict)
       │
       ▼
  Neo4jIngestion.ingest_from_json  (graph.client → graph.schema queries)
       │
       ▼
     Neo4j
```

Each layer has a single job:
- `cli/` — argument parsing + printing only.
- `indexer/` — how to find and parse source files.
- `parsers/` — per-language AST extraction.
- `git/` — everything that shells out to `git`.
- `graph/` — everything that speaks to Neo4j.

---

## Troubleshooting

### "No nodes after indexing"
Make sure you passed `--to-graph`:
```bash
codepulse index /path/to/repo --to-graph
```

### "Two repos show up combined in the browser"
Expected — they coexist in one Neo4j database, separated by `repo_id`.
Filter: `MATCH (n {repo_id: "<hash>"}) RETURN n`, or wipe with
`codepulse graph clear`.

### "`codepulse remove` didn't delete from Neo4j"
Correct. `remove` only unregisters the repo from the local SQLite cache.
Use `codepulse graph clear` to wipe Neo4j (currently an all-or-nothing
operation).

### Check Neo4j quickly
Browser: http://localhost:7474
```cypher
MATCH (n) RETURN n LIMIT 25
```
