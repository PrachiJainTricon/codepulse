# CodePulse — Demo Guide

> **What it does:** Scan your last git commit → find every downstream symbol via Neo4j graph traversal → score the risk → explain what might break in plain English.
>
> **Status: Fully live MVP.** Real Neo4j graph, real git diff parsing, real LangGraph pipeline, real FastAPI server. No mocks in the demo path.

---

## What was built (summary)

| Feature | Detail |
|---|---|
| **CLI diff pipeline** | `codepulse diff <ref>` parses `git diff`, extracts symbols via tree-sitter, queries Neo4j blast radius, runs LangGraph agents, outputs Rich panels |
| **LangGraph multi-agent** | 4 nodes: `investigator → risk_analyst → explainer → pr_writer` |
| **Real Neo4j queries** | `_neo4j_blast_radius` traverses `(:Symbol)<-[:CALLS\|IMPORTS*1..N]-(:Symbol)` up to configurable depth |
| **FastAPI server** | 4 routers: `/repos/`, `/graph/blast-radius`, `/graph/test-coverage`, `/chat/`, `/health` |
| **Chat agent** | Enriches question with Neo4j blast-radius context → Claude (or fallback template) |
| **Indexed corpus** | Voyager apps repo — **7,517 files / 50,805 symbols / ~1.47M relationships** |
| **Neo4j mode switch** | `_MOCK_MODE` flips automatically when `CODEPULSE_NEO4J_URI` is set |
| **Warning suppression** | `warn_notification_severity="OFF"` on the Neo4j driver — clean terminal output |

---

## Prerequisites

### Neo4j (running locally)
Neo4j Community 5.24 with portable Temurin JDK 21 at:
```
C:\Users\adarsh.goyal\codepulse_tools\neo4j\neo4j-community-5.24.0\
C:\Users\adarsh.goyal\codepulse_tools\jdk\jdk-21.0.5+11\
```

Start Neo4j:
```powershell
$env:JAVA_HOME = "C:\Users\adarsh.goyal\codepulse_tools\jdk\jdk-21.0.5+11"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
& "C:\Users\adarsh.goyal\codepulse_tools\neo4j\neo4j-community-5.24.0\bin\neo4j.bat" console
```

> **Preferred (future):** Run Neo4j via Docker — no host Java needed:
> ```powershell
> docker run -d --name codepulse-neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/neo4jadmin neo4j:5.24.0-community
> ```
> Docker Desktop must be installed for this. Once installed, this is the recommended startup.

### Python venv
```powershell
cd C:\Users\adarsh.goyal\codepulse
.\.venv\Scripts\Activate.ps1
```

### Environment variables (set once per session)
```powershell
$env:CODEPULSE_NEO4J_URI      = "bolt://localhost:7687"
$env:CODEPULSE_NEO4J_USER     = "neo4j"
$env:CODEPULSE_NEO4J_PASSWORD = "neo4jadmin"
# Optional — enables Claude LLM explanation instead of template fallback:
# $env:ANTHROPIC_API_KEY = "sk-ant-..."
```

---

## Demo walkthrough (5 steps)

### Step 1 — Verify connectivity

```powershell
Test-NetConnection localhost -Port 7687 | Select-Object TcpTestSucceeded
python -m codepulse.cli.main --help
```

**What to see:**
- `TcpTestSucceeded : True` — Neo4j Bolt is live
- 6 registered commands: `index`, `remove`, `diff`, `ui`, `repos`, `graph`

**Why it matters:** Setting `CODEPULSE_NEO4J_URI` disables `_MOCK_MODE` in `graph/queries.py`. Every subsequent command uses real Cypher.

---

### Step 2 — Indexed repository

```powershell
python -m codepulse.cli.main repos list
```

**What to see:**
```
Indexed Repositories
┌──────────────────────────────────────────────────────────────────────┐
│ C:\Users\adarsh.goyal\mvh\Voyager_Main\Voyager_UI\VoyagerApp\apps   │
└──────────────────────────────────────────────────────────────────────┘
```

**Cross-check in Neo4j Browser** (http://localhost:7474, login `neo4j`/`neo4jadmin`):
```cypher
MATCH (s:Symbol) RETURN count(s) AS symbols;
MATCH (f:File)   RETURN count(f) AS files;
```
Expected: ~50,805 symbols, ~7,517 files.

---

### Step 3 — Full diff pipeline (the headline demo)

```powershell
python -m codepulse.cli.main diff HEAD~1 `
  --repo "C:\Users\adarsh.goyal\mvh\Voyager_Main\Voyager_UI\VoyagerApp\apps" `
  --pr
```

**Output panels:**

| Panel | What it shows | Proof of real data |
|---|---|---|
| **Changed Symbols** | Symbols extracted from `git diff HEAD~1` via tree-sitter | File paths from actual Voyager diff hunks |
| **Downstream Impact** | Symbols impacted up to depth 2 via Neo4j CALLS/IMPORTS traversal | Names like `checkForTooltip`, `printPainBCSData` — not in mock data |
| **Risk Assessment** | `MEDIUM` (score 9) — 3 downstream, depth 1, no tests | Deterministic formula on real graph counts |
| **Explanation** | Plain-English summary of what broke | Template (add `ANTHROPIC_API_KEY` for Claude) |
| **PR Description** | Ready-to-paste markdown PR body | Auto-generated from agent state |

**Last run results:**
- 11 changed symbols (`ResourceScheduleManagerV2`, `Constant`, …)
- 3 downstream symbols impacted (`checkForTooltip`, `printPainBCSData`, `checkShowTooltip`)
- Risk: **MEDIUM**, score: **9**

---

### Step 4 — REST API

Start the server (in a separate terminal):
```powershell
$env:CODEPULSE_NEO4J_URI="bolt://localhost:7687"
$env:CODEPULSE_NEO4J_USER="neo4j"
$env:CODEPULSE_NEO4J_PASSWORD="neo4jadmin"
python -m codepulse.cli.main ui
```

Then call the endpoints:
```powershell
# Health
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"

# Indexed repos (7,517 files, 50,805 symbols)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/repos/" | ConvertTo-Json -Depth 5

# Graph blast radius — 200 downstream symbols from real Neo4j
$r = Invoke-RestMethod -Uri "http://127.0.0.1:8000/graph/blast-radius?symbol=getActualUrl&max_depth=2"
"count = $($r.count)"

# Swagger UI
Start-Process "http://127.0.0.1:8000/docs"
```

**Key proof:** `/graph/blast-radius?symbol=getActualUrl` returns **count=200** — mock mode for this symbol returns 0.

### Step 4.5 — Web Frontend

With the backend running, start the Streamlit frontend in another terminal:
```powershell
streamlit run ui/app.py
```

This opens a web interface at `http://localhost:8501` with tabs for all API endpoints:
- **Health**: Check server status
- **Repos**: View indexed repositories
- **Graph**: Query blast radius and test coverage
- **Chat**: Ask questions about the codebase
- **Analysis**: Analyze git diffs for risk assessment

**Note:** Ensure the backend is running on `http://127.0.0.1:8000` (or update the Base URL in the sidebar if different).

---

### Step 5 — Chat endpoint (graph-enriched Q&A)

```powershell
$body = @{ question = "What breaks if I change getActualUrl?"; symbol_hint = "getActualUrl" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat/" -ContentType "application/json" -Body $body
```

**What to see:**
- `Context gathered:` block lists ~200 real downstream symbols fetched from Neo4j
- Without `ANTHROPIC_API_KEY` → template answer wrapping the context
- With `ANTHROPIC_API_KEY` → Claude generates a natural-language risk explanation using the graph context

---

## Commands reference

| Command | What it does |
|---|---|
| `codepulse index <repo>` | Scan + parse repo, store snapshot in SQLite |
| `codepulse index <repo> --to-graph` | Also push symbols/relationships into Neo4j |
| `codepulse repos list` | Show all indexed repos |
| `codepulse diff HEAD~1` | Analyse last commit (risk panels) |
| `codepulse diff HEAD~3 --pr` | Analyse + generate PR description |
| `codepulse diff <sha> --repo <path>` | Target specific commit + repo |
| `codepulse ui` | Start FastAPI server on port 8000 |
| `codepulse graph clear` | Wipe all Neo4j nodes |
| `codepulse remove <repo>` | Unregister repo from SQLite (does NOT wipe Neo4j) |

---

## How it works (architecture)

```
git diff HEAD~1
      │
      ▼
 diff_resolver.py ──► tree-sitter AST parse ──► list[ChangedSymbol]
      │
      ▼
 LangGraph pipeline
 ┌─────────────────────────────────────────────────────────────┐
 │  investigator_node  →  Neo4j Cypher blast-radius query     │
 │       │                (CALLS|IMPORTS*1..N traversal)      │
 │       ▼                                                     │
 │  risk_analyst_node  →  score = fan_out×2 + depth×3        │
 │       ▼                − has_tests×4 → LOW/MED/HIGH        │
 │  explainer_node     →  Claude (or template fallback)       │
 │       ▼                                                     │
 │  pr_writer_node     →  markdown PR description             │
 └─────────────────────────────────────────────────────────────┘
        │
        ▼
   RiskResult  →  Rich CLI panels  /  JSON  /  REST API
```

---

## Risk score formula

```
score = fan_out × 2  +  max_depth × 3  +  cross_module × 5  −  has_tests × 4

LOW    → score < 8
MEDIUM → score 8–15
HIGH   → score > 15
```

---

## What's real vs. what can be improved

| Component | Status |
|---|---|
| Git diff parsing | **Real** — `git diff` + tree-sitter |
| Symbol extraction | **Real** — Python, TypeScript, Java, C/C++ |
| Commit metadata | **Real** — `git log` |
| Neo4j blast radius | **Real** — live Cypher traversal |
| Test coverage detection | **Partial** — `TESTED_BY` relationship not yet ingested; always returns False |
| Symbol `kind` / `file` in tables | **Partial** — ingested under different property names; columns show `unknown`/blank |
| Risk scoring | **Real** — deterministic formula |
| LLM explanation | **Real** with `ANTHROPIC_API_KEY`; template fallback without |
| Docker for Neo4j | **Planned** — Docker Desktop install required (blocked on admin elevation) |

The more the repo has been indexed in Neo4j, the richer the downstream impact will be.
