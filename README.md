# codepulse

**Code intelligence powered by graph analysis.**

codepulse indexes codebases into a Neo4j knowledge graph, extracts symbols (classes, functions, methods), imports, calls, and uses AI agents to analyze blast radius of changes, score risk, suggest tests, and generate PR descriptions.

---

## 🚀 Quick Start

```bash
# 1. Clone and setup
git clone <repo-url>
cd codepulse

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -e "."

# 4. Start Neo4j
docker run -d --name neo4j-codepulse -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/neo4jadmin neo4j:latest

# 5. Index your first repo
codepulse index /path/to/your/project --to-graph

# 6. View in browser: http://localhost:7474
```

---

## 📋 CLI Commands

### codepulse index

```bash
# Index current directory
codepulse index

# Index specific path
codepulse index /path/to/repo

# Force full re-index
codepulse index --full

# Index and push to Neo4j
codepulse index --to-graph
```

### codepulse graph

```bash
# Clear all nodes from Neo4j
codepulse graph clear
```

### codepulse repos

```bash
# List indexed repos
codepulse repos

# Remove a repo
codepulse remove /path/to/repo
```

---

## 🐳 Neo4j Setup

### Access

| Port | Service | URL |
|------|---------|-----|
| 7474 | HTTP | http://localhost:7474 |
| 7687 | Bolt | bolt://localhost:7687 |

### Credentials

Update in `codepulse/config.py` or set environment variables:

```bash
export CODEPULSE_NEO4J_USER=neo4j
export CODEPULSE_NEO4J_PASSWORD=neo4jadmin
```

| Variable | Default |
|----------|---------|
| `CODEPULSE_NEO4J_URI` | `bolt://localhost:7687` |
| `CODEPULSE_NEO4J_USER` | `neo4j` |
| `CODEPULSE_NEO4J_PASSWORD` | `neo4jadmin` |

---

## 📁 Project Structure

```
codepulse/
├── cli/                    # CLI commands
│   ├── main.py            # Entry point
│   ├── index_cmd.py     # codepulse index
│   ├── repos_cmd.py    # codepulse repos
│   └── graph_cmd.py   # codepulse graph
├── codepulse/
│   ├── indexer/          # Indexing pipeline
│   ├── parsers/          # Tree-sitter parsers (python, ts, java, cpp)
│   ├── graph/           # Neo4j client + schema
│   ├── tree_parser.py   # ParseResult → JSON
│   └── config.py      # Settings
└── pyproject.toml
```

---

## Architecture

```
codepulse index
  → repo_scanner      → snapshot       → parser_worker   → parsers
  → tree_parser      → graph/client  → Neo4j
```

---

## ❓ Troubleshooting

### No nodes after indexing

Make sure to use `--to-graph`:

```bash
codepulse index /path/to/repo --to-graph
```

### Check Neo4j

Browser: http://localhost:7474

```cypher
MATCH (n) RETURN n LIMIT 25
```