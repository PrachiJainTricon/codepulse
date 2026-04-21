# codepulse

**Code intelligence powered by graph analysis.**

codepulse indexes any codebase into a knowledge graph, then uses AI agents to analyze blast radius of changes, score risk, suggest tests, and generate PR descriptions.

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
