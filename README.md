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
- **REST API + Swagger UI** — FastAPI server exposes graph queries, diff analysis, and chat
- **LangGraph multi-agent pipeline** — change_investigator → risk_analyst → explainer

---

## Demo (5-minute walkthrough)

This walks through a live demo against a real codebase already indexed into Neo4j (7.5k files, 50k symbols, 1.5M relationships).

### 0. One-time setup — start Neo4j + the API server

You need two long-running processes. Open two terminals.

**Terminal A — Neo4j** (Java 21 portable + Neo4j Community 5.24 zip works without admin):

```powershell
# Windows / PowerShell
$env:JAVA_HOME = "C:\Users\<you>\codepulse_tools\jdk\jdk-21.0.5+11"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
& "C:\Users\<you>\codepulse_tools\neo4j\neo4j-community-5.24.0\bin\neo4j.bat" console
```

```bash
# Or with Docker (any OS)
docker run -d --name neo4j-codepulse \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/neo4jadmin neo4j:5.24
```

**Terminal B — CodePulse API server**:

```powershell
$env:CODEPULSE_NEO4J_URI = "bolt://localhost:7687"
$env:CODEPULSE_NEO4J_USER = "neo4j"
$env:CODEPULSE_NEO4J_PASSWORD = "neo4jadmin"
cd <path-to-codepulse>
python -m uvicorn codepulse.api.server:app --host 127.0.0.1 --port 8000 --reload
```

Smoke check: `Invoke-RestMethod http://127.0.0.1:8000/health` → `status: ok`.

Open these tabs:
- **Neo4j Browser:** http://localhost:7474 (login `neo4j` / `neo4jadmin`)
- **Swagger UI:** http://localhost:8000/docs

### 1. Index a repo into Neo4j

```powershell
python -m codepulse.cli.main index "C:\path\to\your-repo" --to-graph --full
```

Expected output (real numbers from the Voyager UI repo):
```
Neo4j ingestion complete:
  Files: 7517
  Symbols: 50805
  Packages: 10537
  Relationships: 1473887
```

### 2. Show the graph (Neo4j Browser — visual wow)

In http://localhost:7474, paste:

```cypher
// Schema overview
CALL db.schema.visualization()
```

Then a real blast-radius subgraph for a heavily-called symbol:

```cypher
MATCH path = (caller:Symbol)-[:CALLS*1..2]->(target:Symbol {name: "getActualUrl"})
RETURN path LIMIT 50
```

Find heavy-hitter symbols to demo on:

```cypher
MATCH (s:Symbol)<-[:CALLS]-(other)
RETURN s.name AS name, count(other) AS callers
ORDER BY callers DESC LIMIT 10
```

### 3. Hit the REST API

In Swagger UI (http://localhost:8000/docs), or via curl/PowerShell:

```powershell
# Real blast-radius — pulls live from Neo4j
Invoke-RestMethod "http://127.0.0.1:8000/graph/blast-radius?symbol=getActualUrl&max_depth=2"

# Test-coverage check
Invoke-RestMethod "http://127.0.0.1:8000/graph/test-coverage?symbol=getActualUrl"

# Conversational Q&A (template fallback if ANTHROPIC_API_KEY is unset)
$body = @{question="Should I be worried about changing handleError?"; symbol_hint="handleError"} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/chat/ -Method Post -Body $body -ContentType application/json

# Run the full risk pipeline on the last commit
$body = @{repo_path="C:\path\to\your-repo"; commit_ref="HEAD~1"} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/analysis/diff -Method Post -Body $body -ContentType application/json
```

### 4. CLI demo — diff analysis with rich output

```powershell
python -m codepulse.cli.main diff HEAD~1 --repo "C:\path\to\your-repo" --pr
```

This:
1. Parses the last commit's diff
2. Extracts changed symbols (Python, TS, JS)
3. Queries Neo4j for blast radius
4. Scores risk (low / medium / high) deterministically
5. Generates an explanation + PR description (LLM-backed if `ANTHROPIC_API_KEY` is set, template fallback otherwise)

### 5. (Optional) Enable LLM-backed answers

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
# Restart the API server; chat + explainer now use Claude instead of templates
```

### Demo talk-track (60s)

> "CodePulse indexes a codebase into a Neo4j knowledge graph, then uses LangGraph agents to answer the one question every reviewer cares about: **if I change this function, what else breaks?** Here's the Voyager UI codebase — 7.5k files, 50k symbols, 1.5M call/import edges, indexed in ~12 minutes. Every node is a real symbol parsed by tree-sitter. Every edge is a real relationship. The REST API exposes blast-radius queries; the CLI runs the full risk pipeline on a git diff; the LangGraph agents stitch the data into a plain-English risk summary."

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

Scan and parse a repository into SQLite.

```bash
codepulse index                 # incremental index of current directory (skips unchanged files)
codepulse index /path/to/repo   # index a specific path
codepulse index --full           # force full re-index, ignore snapshot cache
```

### `codepulse index --to-graph`

Index and push changes to Neo4j.

```bash
codepulse index --to-graph             # push only uncommitted working-tree changes to Neo4j
codepulse index --full --to-graph      # full re-index + push ALL files to Neo4j
```

- `--to-graph` alone pushes **only uncommitted edits** (staged + unstaged vs HEAD). Use this for day-to-day development.
- `--full --to-graph` re-parses every file and pushes the entire codebase. Use this for **initial graph population** or to ensure Neo4j has the complete picture.
- Existing Neo4j nodes are preserved via `MERGE` — incremental pushes upsert alongside existing data.

### `codepulse repos`

List all indexed repositories with stats.

```bash
codepulse repos                 # show all registered repos (files, symbols, last indexed)
codepulse repos list            # same as above
```

### `codepulse remove`

Unregister a repo from the local SQLite registry. Does **not** delete Neo4j data.

```bash
codepulse remove                # remove current directory from registry
codepulse remove /path/to/repo  # remove a specific repo
```

### `codepulse graph clear`

Wipe all nodes and relationships from Neo4j. Does **not** affect SQLite.

```bash
codepulse graph clear
```

### `codepulse diff`

Run blast-radius + risk analysis on a git diff. Calls the LangGraph pipeline.

```bash
codepulse diff                                  # diff HEAD~1 in current dir
codepulse diff HEAD~3                           # diff 3 commits back
codepulse diff abc123 --repo /path/to/repo      # specific SHA + explicit repo
codepulse diff HEAD~1 --pr                      # also print generated PR description
codepulse diff HEAD~1 --json                    # raw JSON output
```

### `codepulse ui`

Start the FastAPI REST server (Swagger UI at `/docs`).

```bash
codepulse ui                                    # http://127.0.0.1:8000
codepulse ui --port 9000 --no-reload
```

Endpoints:

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health`                  | Liveness check |
| GET  | `/repos/`                  | List indexed repos |
| GET  | `/graph/blast-radius`      | `?symbol=X&max_depth=N` — downstream impact |
| GET  | `/graph/test-coverage`     | `?symbol=X` — does it have tests? |
| POST | `/analysis/diff`           | `{repo_path, commit_ref}` — full risk pipeline |
| POST | `/chat/`                   | `{question, symbol_hint?}` — Q&A over the graph |

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

## Neo4j / graph reference

This section adds graph-specific details only. Setup, install, basic commands, and the core indexing architecture are already documented above.

### Start Neo4j

```bash
docker run -d --name neo4j-codepulse \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/neo4jadmin neo4j:latest
```

Neo4j browser: [http://localhost:7474](http://localhost:7474)

### Push a repo to Neo4j

```bash
codepulse index /path/to/your/project --to-graph
```

### `codepulse index` and graph-related commands

```bash
codepulse index                         # incremental index to SQLite (skips unchanged files)
codepulse index /path/to/repo           # index a specific path
codepulse index --full                  # full re-index, ignore snapshot cache
codepulse index --to-graph              # push uncommitted working-tree changes to Neo4j
codepulse index --full --to-graph       # full re-index + push ALL files to Neo4j
```

- `--to-graph` pushes **only uncommitted edits** (staged + unstaged vs HEAD). Ideal for iterative development.
- `--full --to-graph` re-parses every file and pushes the entire codebase. Use for **initial graph population**.
- In a **non-git** directory, both modes parse the whole tree (snapshot mode).

```bash
codepulse graph clear                   # wipe every node + relationship in Neo4j
```

```bash
codepulse repos                         # list indexed repos with stats
codepulse remove /path/to/repo          # unregister + clear local snapshot (does NOT touch Neo4j)
```

### Configuration (environment variables)


| Variable                   | Default                                |
| -------------------------- | -------------------------------------- |
| `CODEPULSE_NEO4J_URI`      | `bolt://localhost:7687`                |
| `CODEPULSE_NEO4J_USER`     | `neo4j`                                |
| `CODEPULSE_NEO4J_PASSWORD` | `neo4jadmin`                           |
| `CODEPULSE_DATA_DIR`       | `~/.codepulse` (SQLite snapshot cache) |


Neo4j browser: [http://localhost:7474](http://localhost:7474)

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


| Node      | Key                                    |
| --------- | -------------------------------------- |
| `Repo`    | `id`                                   |
| `Commit`  | `(repo_id, id)`                        |
| `Change`  | `(repo_id, commit_id, file_path)`      |
| `File`    | `(repo_id, commit_id, path)`           |
| `Symbol`  | `(repo_id, commit_id, qualified_name)` |
| `Package` | `(repo_id, commit_id, name)`           |


`Symbol.qualified_name` is prefixed with `repo_id` (for example `a1b2c3d4e5.codepulse.cli.index_cmd.index`) so names do not clash across repos. The human-readable name is on the `repo` property.

**Multi-repo behavior:** Indexing repo A, then repo B, stores both in the same Neo4j instance as two separate subgraphs. Filter with `repo_id` in Cypher, or run `codepulse graph clear` to start empty.

### Handy Cypher

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

### Graph push flow

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

### Troubleshooting

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
