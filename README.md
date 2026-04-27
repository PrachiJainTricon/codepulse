# Codepulse

**Code intelligence powered by graph analysis.**

codepulse indexes any codebase into a knowledge graph, then uses AI agents to analyze blast radius of changes, score risk, suggest tests, and generate PR descriptions.

In a **git** repository, graph ingestion with `--to-graph` records **commit-by-commit** context (per-commit nodes and, when the diff has files, change records). The graph is also intended as a **retrieval foundation** for future agents and tools that need structural code context.

---

## What it does (so far)

- **Tree-sitter AST parsing** — extracts symbols (classes, functions, methods), imports, function calls, and exports from source files
- **Multi-language support** — Python, JavaScript, TypeScript, Java, C/C++
- **Incremental indexing** — SHA-256 hash check skips unchanged files on re-index
- **Repo registry** — tracks all indexed repos with stats in a local SQLite database
- **CLI tool** — works globally from any project directory (like `git`)

## Architecture

```
codepulse index (CLI)
  → repo_scanner.py        walk tree, filter .gitignore, detect language
  → snapshot.py            SHA-256 hash check vs SQLite (skip unchanged)
  → parser_worker.py       route to correct language parser
  → python_parser.py       Tree-sitter AST → ParseResult
     typescript_parser.py
     java_parser.py
     cpp_parser.py
  → index_service.py       orchestrates everything, returns IndexReport
  → run_store.py           registers repo + updates stats in SQLite
```

The service layer (`index_service.py`) is decoupled from the CLI — the future API/UI will call the same `run_index()` function.

---

## Setup

### Prerequisites

- Python 3.11+
- Git

### Install

```bash
# Clone the repo
git clone <repo-url>
cd codepulse

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode (all dependencies auto-installed)
pip install -e "."
```

### Make it globally available (optional)

This lets you run `codepulse` from any directory without activating the venv:

```bash
mkdir -p ~/.local/bin
ln -sf $(pwd)/.venv/bin/codepulse ~/.local/bin/codepulse

# Add to PATH (if not already there)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

## Commands

### `codepulse index`

Scan and parse a repository.

```bash
# Index the current directory
cd /path/to/any-project
codepulse index

# Index a specific path
codepulse index /path/to/repo

# Force full re-index (ignore cache)
codepulse index --full
```

**Output:** A table showing per-file breakdown of symbols, imports, calls, and exports extracted.

### `codepulse graph`

Manage the Neo4j graph (e.g. wipe the database during testing).

```bash
# Clear all nodes and relationships in Neo4j (does not affect local SQLite / repo registry)
codepulse graph clear
```

### `codepulse repos`

Manage indexed repositories.

```bash
# List all indexed repos
codepulse repos
codepulse repos list

# Remove a repo from the registry
codepulse remove              # removes current directory
codepulse remove /path/to/repo
```

### `codepulse help`

```bash
codepulse help
codepulse --help
```

---

## Project Structure

```
codepulse/
├── cli/                    # CLI commands (thin wrappers over services)
│   ├── main.py             # Typer app entry point
│   ├── index_cmd.py        # codepulse index
│   ├── graph_cmd.py        # codepulse graph (e.g. clear Neo4j)
│   └── repos_cmd.py        # codepulse repos / remove
├── indexer/                # Core indexing pipeline
│   ├── index_service.py    # Orchestrator — run_index() returns IndexReport
│   ├── repo_scanner.py     # Walk file tree, respect .gitignore
│   ├── snapshot.py         # SHA-256 hash-based change detection
│   ├── parser_worker.py    # Dispatch files to language parsers
│   └── language_detector.py# File extension → Language mapping
├── parsers/                # Tree-sitter based parsers
│   ├── base.py             # ParseResult dataclass + BaseParser ABC
│   ├── python_parser.py    # Python (.py)
│   ├── typescript_parser.py# TypeScript/JavaScript (.ts/.js/.tsx/.jsx)
│   ├── java_parser.py      # Java (.java)
│   └── cpp_parser.py       # C/C++ (.cpp/.c/.h/.hpp)
├── db/                     # SQLite storage
│   ├── models.py           # Table schemas (repos, file_snapshots)
│   ├── migrations.py       # Schema creation
│   └── run_store.py        # RepoStore — CRUD for repo registry
├── config.py               # Central settings
└── logging.py              # Rich-based logging
```

## What's next

- **Neo4j graph writer** — persist ParseResults as nodes + edges
- **Graph queries** — "who calls function X", blast radius traversal
- **Diff analysis** — extract changed symbols from git diff
- **LangGraph agents** — Change Investigator, Risk Analyst, Explainer, PR Writer
- **Web UI** — React dashboard with graph explorer and chat interface

---

> **Note:** The standalone `codepulse/README.md` was removed. Everything important from that file is merged into *this* document. The next section is the long-form **Neo4j / graph** reference; it stays self-contained and extends (it does not replace) the setup and architecture above.

## Reference — migrated from `codepulse/README.md` (archived; file removed)

The sections below mirror the former project `README` so this file stays a single place for the full quick reference.

### Quick Start (index + Neo4j)

```bash
# 1. Clone and setup (if not already)
git clone <repo-url>
cd codepulse

# 2. Virtual environment
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

### `codepulse index` and graph-related commands

```bash
codepulse index                         # index current directory
codepulse index /path/to/repo           # index a specific path
codepulse index --full                  # ignore the snapshot cache
codepulse index --to-graph              # also push to Neo4j
```

- In a **git** repo, `--to-graph` runs in **commit mode**: it parses the files that changed between `HEAD~1` and `HEAD` and tags every node with the current commit id.
- In a **non-git** directory (or if git is unavailable), it uses **snapshot mode** and parses the whole tree.

```bash
codepulse graph clear                   # wipe every node + relationship in Neo4j
```

```bash
codepulse repos                         # list indexed repos
codepulse remove /path/to/repo          # unregister + clear local snapshot (does NOT touch Neo4j)
```

### Configuration (environment variables)

| Variable | Default |
|---|---|
| `CODEPULSE_NEO4J_URI` | `bolt://localhost:7687` |
| `CODEPULSE_NEO4J_USER` | `neo4j` |
| `CODEPULSE_NEO4J_PASSWORD` | `neo4jadmin` |
| `CODEPULSE_DATA_DIR` | `~/.codepulse` (SQLite snapshot cache) |

Neo4j browser: http://localhost:7474

### Graph model (Neo4j)

Every node carries a `repo_id` (stable SHA-1 of the git remote URL, or of the absolute path for non-git repos) and a `commit_id` so multiple repos and commits can share one database.

```
 (Repo)-[:HAS_COMMIT]->(Commit)-[:HAS_CHANGE]->(Change)
   |
   +-[:CONTAINS]->(File)-[:CONTAINS]->(Symbol)-[:CALLS]->(Symbol)
                                         |
                                         +-[:IMPORTS]->(Package)
```

**Unique keys (MERGE targets):**

| Node | Key |
|---|---|
| `Repo` | `id` |
| `Commit` | `(repo_id, id)` |
| `Change` | `(repo_id, commit_id, file_path)` |
| `File` | `(repo_id, commit_id, path)` |
| `Symbol` | `(repo_id, commit_id, qualified_name)` |
| `Package` | `(repo_id, commit_id, name)` |

`Symbol.qualified_name` is prefixed with `repo_id` (for example `a1b2c3d4e5.codepulse.cli.index_cmd.index`) so names do not clash across repos. The human-readable name is on the `repo` property.

**Multi-repo behavior:** Indexing repo A, then repo B, stores both in the same Neo4j instance as two separate subgraphs. Filter with `repo_id` in Cypher, or run `codepulse graph clear` to start empty.

### Handy Cypher (replace placeholders with real values from your data)

Do not use angle-bracket placeholders like `'<sha>'` as literal strings — copy a real `Commit.id` from a query.

```cypher
// List commits you have ingested
MATCH (c:Commit) RETURN c.id, c.repo_id, c.mode ORDER BY c.ingested_at DESC LIMIT 20

// Everything for one repo (use your real repo_id from a Repo or Commit node)
MATCH (n {repo_id: "abc1234567"}) RETURN n

// Who calls `foo`?
MATCH (caller:Symbol)-[:CALLS]->(target:Symbol)
WHERE target.name = "foo" AND coalesce(target.deleted, false) = false
RETURN caller.qualified_name, target.qualified_name

// File-level changes (Change nodes exist only in git *commit* mode when the
// diff reported files; non-git snapshot ingests have no :Change nodes)
MATCH (c:Commit)-[:HAS_CHANGE]->(ch:Change)
RETURN c.id, ch.file_path, ch.type
LIMIT 50
```

### Extended project structure (graph + git layers)

The tree below supplements the "Project structure" section earlier in this file.

```
codepulse/
  cli/
    main.py
    index_cmd.py
    graph_cmd.py
    repos_cmd.py
  indexer/
    repo_scanner.py
    language_detector.py
    snapshot.py
    parser_worker.py
    index_service.py
  parsers/
    base.py
    python_parser.py
    typescript_parser.py
    java_parser.py
    cpp_parser.py
  git/
    repo_identity.py
    commit_meta.py
    diff_resolver.py
    _gitcli.py
  graph/
    client.py
    schema.py
    payload.py
  db/
    migrations.py
    run_store.py
    models.py
  config.py
  logging.py
```

### End-to-end architecture (index + graph push)

```
codepulse index [--to-graph]
       │
       ▼
  run_index  (indexer.index_service)
       │
       ├─ repo_scanner  ──►  snapshot  ──►  parser_worker  ──►  parsers
       │
       ▼
  IndexReport  ──►  printed in the terminal

       │  (if --to-graph)
       ▼
  build_graph_payload  (graph.payload)
       │
       ├─ resolve_commit_context    (commit SHA + changed files, or snapshot)
       ├─ parse_all_files | parse_changed_files
       └─ to_legacy_file_result
       │
       ▼
  Neo4jIngestion.ingest_from_json  (graph.client / graph.schema)
       │
       ▼
     Neo4j
```

**Layering:** `cli/` handles arguments and printing only. `indexer/` finds and parses source. `parsers/` implement per-language AST rules. `git/` wraps `git` and commit metadata. `graph/` talks to Neo4j.

### Troubleshooting (same content as the former `codepulse/README.md`)

**No nodes after indexing:** use `--to-graph`.

```bash
codepulse index /path/to/repo --to-graph
```

**Two repos look “combined” in the browser:** expected — one database, many `repo_id` values. Filter, e.g. `MATCH (n {repo_id: "your10charid"}) RETURN n`, or `codepulse graph clear`.

**`codepulse remove` did not clear Neo4j:** by design. `remove` only updates the local SQLite registry. Use `codepulse graph clear` to delete graph data (currently all nodes).

**Quick sanity check in Neo4j:**

```cypher
MATCH (n) RETURN n LIMIT 25
```


Each layer has a single job:

- `cli/` — argument parsing + printing only.
- `indexer/` — how to find and parse source files.
- `parsers/` — per-language AST extraction.
- `git/` — everything that shells out to `git`.
- `graph/` — everything that speaks to Neo4j.
