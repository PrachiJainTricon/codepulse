# CodePulse — Demo Guide

> **What it does:** Scan your last git commit → find every symbol downstream of the change → score the risk → explain what might break in plain English.

---

## Quick start (2 minutes)

### 1. Install

```bash
pip install -e ".[dev]"
```

### 2. Create `.env` in the repo root

```env
ANTHROPIC_API_KEY=sk-ant-...        # required for LLM explanation
NEO4J_URI=bolt://localhost:7687     # optional — uses mock data without it
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
```

Without `ANTHROPIC_API_KEY` the tool still runs — it uses a template explanation instead of Claude.

### 3. Run against any repo

```bash
cd /path/to/any-git-repo

python -m codepulse.cli.main diff HEAD~1
```

---

## Commands

| Command | What it does |
|---|---|
| `diff HEAD~1` | Analyse the last commit |
| `diff HEAD~3` | Analyse 3 commits back |
| `diff abc1234` | Analyse a specific SHA |
| `diff HEAD~1 --pr` | Also generate a PR description |
| `diff HEAD~1 --json` | Raw JSON output (pipe-friendly) |
| `diff HEAD~1 --repo ./my-app` | Point at a different repo path |

---

## Demo script (show this in order)

### Step 1 — Show the diff

```bash
git diff HEAD~1 --stat
```

Show the audience: "Here's what changed in the last commit — just raw Git output."

### Step 2 — Run CodePulse on it

```bash
python -m codepulse.cli.main diff HEAD~1 --repo .
```

**What they'll see:**

- **Changed Symbols** table — every function/class touched in the diff, mapped to file + change type (added / modified / deleted)
- **Downstream Impact** table — symbols reachable from the changed ones in the code graph (mock data for now; real Neo4j once P2 wires it in)
- **Risk Assessment** panel — LOW / MEDIUM / HIGH label with a numeric score and bullet reasons
- **Explanation** panel — plain-English summary of what's impacted and why the risk is what it is

### Step 3 — Show the PR description

```bash
python -m codepulse.cli.main diff HEAD~1 --repo . --pr
```

A ready-to-paste PR description appears at the bottom.

### Step 4 — Show JSON output (optional, for technical audience)

```bash
python -m codepulse.cli.main diff HEAD~1 --repo . --json
```

Shows the raw structured result — useful for piping into CI systems.

---

## How it works (3 layers)

```
git diff HEAD~1
      │
      ▼
 ┌─────────────┐
 │  P3: Diff   │  diff_resolver.py  →  parse raw diff  →  list[ChangedSymbol]
 │  resolver   │  symbol_diff.py    →  regex-extract function/class names
 └──────┬──────┘
        │  changed_symbols
        ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │  P4: LangGraph pipeline                                         │
 │                                                                 │
 │  investigator_node  →  Neo4j blast-radius query (mock now)     │
 │       │                fan_out, max_depth, cross_module        │
 │       ▼                                                         │
 │  risk_analyst_node  →  deterministic score + LOW/MED/HIGH      │
 │       ▼                                                         │
 │  explainer_node     →  Claude API → plain-English explanation  │
 └──────────────────────────────────────────────────────────────────┘
        │
        ▼
   RiskResult  →  Rich CLI output
```

---

## File ownership (who built what)

| Layer | Files | Owner |
|---|---|---|
| Shared contracts | `codepulse/agents/state.py` | P3 + P4 (frozen Day 1) |
| Diff parsing | `codepulse/git/diff_resolver.py` | P3 |
| Symbol extraction | `codepulse/git/symbol_diff.py` | P3 |
| Commit metadata | `codepulse/git/commit_meta.py` | P3 |
| Investigator node | `codepulse/agents/change_investigator.py` | P4 |
| Risk analyst node | `codepulse/agents/risk_analyst.py` | P4 |
| LLM prompts | `codepulse/agents/prompts.py` | P4 |
| Explainer node | `codepulse/agents/explainer.py` | P4 |
| LangGraph pipeline | `codepulse/agents/pipeline.py` | P4 |
| Neo4j queries | `codepulse/graph/queries.py` | P2 (stub ready) |
| CLI command | `codepulse/cli/diff_cmd.py` | P5 |

---

## Risk score formula

```
score = fan_out × 2  +  max_depth × 3  +  cross_module × 5  −  has_tests × 4

LOW    → score < 8
MEDIUM → score 8–15
HIGH   → score > 15
```

- **fan_out** — number of downstream symbols impacted
- **max_depth** — how many hops the impact travels through the graph
- **cross_module** — impact crosses top-level package boundary
- **has_tests** — test coverage detected (reduces score)

---

## What's mocked vs. real

| Component | Status |
|---|---|
| Git diff parsing | **Real** — runs actual `git diff` |
| Symbol name extraction | **Real** — regex on diff lines (Python + TS) |
| Commit metadata | **Real** — `git log` |
| Neo4j blast radius | **Mock** — hardcoded graph in `graph/queries.py`. Replace when P2 sets up Neo4j. |
| Risk scoring | **Real** — deterministic formula |
| LLM explanation | **Real** when `ANTHROPIC_API_KEY` is set; template fallback otherwise |
| PR description | **Real** when `ANTHROPIC_API_KEY` is set; template fallback otherwise |

---

## Swapping in real Neo4j (P2 handoff)

In `codepulse/graph/queries.py`, set `_MOCK_MODE = False` (it happens automatically when `NEO4J_URI` env var is set) and fill in:

```python
def _neo4j_blast_radius(symbol_name: str, max_depth: int = 3) -> list[ImpactedSymbol]:
    # Replace with real Cypher query using neo4j driver
    ...

def _neo4j_has_tests(symbol_name: str) -> bool:
    # Replace with real Cypher query
    ...
```

The pipeline won't change — only these two functions.

---

## Adding a real demo repo

For the best demo, point at a real codebase with multiple commits:

```bash
git clone https://github.com/some/real-repo /tmp/demo-repo
cd /tmp/demo-repo

# Make a small change
# e.g. edit a core service class

git add . && git commit -m "test: tweak payment logic"

python -m codepulse.cli.main diff HEAD~1 --repo . --pr
```

The more the repo has been indexed in Neo4j, the richer the downstream impact will be.
