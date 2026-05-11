"""
Conversational Q&A agent over the code graph.

Accepts a plain-English question about the indexed codebase and returns
an answer backed by blast-radius data and LLM reasoning.

Automatically extracts file/symbol names from the question and queries
Neo4j for context. Falls back to a template answer if no LLM API key is configured.
"""

from __future__ import annotations

import os
import re

from codepulse.graph.queries import get_blast_radius, get_test_coverage
from codepulse.llm import call_llm

_SYSTEM_PROMPT = """\
You are CodePulse, an expert code intelligence assistant.
You have access to a code knowledge graph that indexes repositories.
Answer the user's question concisely and accurately based on the provided context.
If the context contains file contents or symbol information, use that to answer.
If you don't know the answer from the context, say so honestly.
"""


def _call(question: str, context: str) -> str:
    try:
        return call_llm(
            system=_SYSTEM_PROMPT,
            user=f"Graph context:\n{context}\n\nQuestion: {question}",
        )
    except EnvironmentError:
        return _fallback_answer(question, context)


def _fallback_answer(question: str, context: str) -> str:
    return (
        f"(LLM unavailable — set your provider API key. See CODEPULSE_LLM_PROVIDER)\n"
        f"Context gathered:\n{context}"
    )


def _query_graph_for_file(file_name: str) -> list[str]:
    """Query Neo4j for symbols in a file matching the name. Falls back to disk read."""
    lines: list[str] = []

    # Try Neo4j first
    try:
        from codepulse.graph.client import Neo4jClient

        cypher = """
        MATCH (f:File)
        WHERE f.path CONTAINS $file_name
        OPTIONAL MATCH (f)-[:CONTAINS]->(s:Symbol)
        OPTIONAL MATCH (f)-[:IMPORTS]->(p:Package)
        RETURN f.path AS file, 
               collect(DISTINCT {name: s.name, type: s.type, line: s.start_line}) AS symbols,
               collect(DISTINCT p.name) AS imports
        LIMIT 5
        """

        def _tx(tx):
            return list(tx.run(cypher, file_name=file_name))

        with Neo4jClient() as client:
            with client.driver.session(database=client.database) as session:
                records = session.execute_read(_tx)

        if records:
            for r in records:
                file_path = r["file"]
                symbols = [s for s in r["symbols"] if s.get("name")]
                imports = [i for i in r["imports"] if i]

                lines.append(f"File: {file_path}")
                if imports:
                    lines.append(f"Imports: {', '.join(imports)}")
                if symbols:
                    lines.append(f"Symbols ({len(symbols)}):")
                    for s in symbols:
                        lines.append(f"  - {s['name']} ({s['type']}) at line {s['line']}")
                else:
                    lines.append("(No function/class definitions found in graph)")
                    # # Disk fallback — uncomment to re-enable
                    # disk_lines = _read_file_from_repos(file_path)
                    # if disk_lines:
                    #     lines.extend(disk_lines)
    except Exception:
        pass

    # # Disk fallback — uncomment to re-enable
    # if not lines:
    #     disk_lines = _read_file_from_repos(file_name)
    #     if disk_lines:
    #         lines.extend(disk_lines)

    return lines


def _read_file_from_repos(file_path: str) -> list[str]:
    """Try to read a file from registered repos and return a summary."""
    try:
        from codepulse.db.run_store import RepoStore
        store = RepoStore()
        repos = store.list_all()

        from pathlib import Path
        for repo in repos:
            candidate = Path(repo.root_path) / file_path
            if candidate.exists():
                content = candidate.read_text(errors="replace")
                # Provide a summary (first 80 lines to stay within context limits)
                source_lines = content.splitlines()[:80]
                result = [f"File content ({len(content.splitlines())} total lines):"]
                result.append("```python")
                result.extend(source_lines)
                result.append("```")
                return result

            # Also try partial match  
            for f in Path(repo.root_path).rglob(f"*{file_path}"):
                if f.is_file():
                    content = f.read_text(errors="replace")
                    source_lines = content.splitlines()[:80]
                    result = [f"File: {f.relative_to(Path(repo.root_path))} ({len(content.splitlines())} total lines):"]
                    result.append("```python")
                    result.extend(source_lines)
                    result.append("```")
                    return result
    except Exception:
        pass
    return []


def _query_graph_for_symbol(symbol_name: str) -> list[str]:
    """Query Neo4j for info about a specific symbol: what it calls AND who calls it."""
    try:
        from codepulse.graph.client import Neo4jClient

        # Query 1: symbol info + what it calls
        cypher_out = """
        MATCH (s:Symbol)
        WHERE s.name = $symbol_name OR s.qualified_name CONTAINS $symbol_name
        OPTIONAL MATCH (s)<-[:CONTAINS]-(f:File)
        OPTIONAL MATCH (s)-[:CALLS]->(callee:Symbol)
        RETURN s.name AS name, s.type AS kind, s.start_line AS line,
               f.path AS file, collect(DISTINCT callee.name) AS calls
        LIMIT 10
        """

        # Query 2: who calls this symbol (callers)
        cypher_in = """
        MATCH (caller:Symbol)-[:CALLS]->(s:Symbol)
        WHERE s.name = $symbol_name OR s.qualified_name CONTAINS $symbol_name
        OPTIONAL MATCH (caller)<-[:CONTAINS]-(f:File)
        RETURN caller.name AS name, caller.type AS kind, f.path AS file
        LIMIT 10
        """

        def _tx_out(tx):
            return list(tx.run(cypher_out, symbol_name=symbol_name))

        def _tx_in(tx):
            return list(tx.run(cypher_in, symbol_name=symbol_name))

        with Neo4jClient() as client:
            with client.driver.session(database=client.database) as session:
                records = session.execute_read(_tx_out)
                callers = session.execute_read(_tx_in)

        lines = []
        for r in records:
            lines.append(f"Symbol: {r['name']} ({r['kind']}) in {r['file']} at line {r['line']}")
            if r['calls']:
                calls = [c for c in r['calls'] if c]
                if calls:
                    lines.append(f"  Calls: {', '.join(calls)}")

        if callers:
            caller_names = [f"{r['name']} ({r['kind']}) in {r['file']}" for r in callers if r['name']]
            if caller_names:
                lines.append(f"Called by: {', '.join(caller_names)}")

        return lines
    except Exception:
        return []


def _extract_hints(question: str) -> tuple[list[str], list[str]]:
    """Extract likely file names and symbol names from the question."""
    # File patterns: anything.py, anything.ts, anything.java, etc.
    files = re.findall(r'[\w\-/]+\.(?:py|ts|js|java|cpp|c|h|tsx|jsx)', question)

    # Symbol patterns: words that look like function/class names (camelCase, snake_case)
    # Exclude common English words
    _stop = {'what', 'does', 'this', 'that', 'how', 'many', 'the', 'are', 'for', 'has',
             'have', 'here', 'there', 'where', 'which', 'with', 'from', 'into', 'line',
             'method', 'methods', 'function', 'functions', 'class', 'classes', 'file',
             'code', 'project', 'about', 'explain', 'describe', 'show', 'change',
             'will', 'get', 'impacted', 'calls', 'called', 'call', 'who', 'why',
             'can', 'could', 'should', 'would', 'all', 'any', 'some', 'every',
             'if', 'is', 'it', 'its', 'my', 'me', 'no', 'not', 'of', 'on', 'or',
             'our', 'out', 'so', 'to', 'up', 'use', 'was', 'we', 'you', 'your'}
    words = re.findall(r'\b[a-zA-Z_]\w*\b', question)
    symbols = [w for w in words
               if w.lower() not in _stop
               and len(w) > 2
               and (  # camelCase, PascalCase, snake_case, or domain-specific word
                   '_' in w
                   or w[0].isupper()
                   or any(c.isupper() for c in w[1:])  # camelCase
                   or w not in _stop  # any non-stop word longer than 2 chars
               )]

    return files, symbols


def answer(question: str, symbol_hint: str | None = None) -> str:
    """
    Answer *question* about the codebase.

    Automatically extracts file/symbol references from the question
    and queries the graph. If *symbol_hint* is provided, that takes priority.
    """
    context_lines: list[str] = []

    # Explicit symbol hint
    if symbol_hint:
        impacted = get_blast_radius(symbol_hint)
        has_tests = get_test_coverage(symbol_hint)
        context_lines.append(f"Symbol: {symbol_hint}")
        context_lines.append(f"Has test coverage: {has_tests}")
        if impacted:
            context_lines.append("Downstream symbols:")
            for sym in impacted:
                context_lines.append(
                    f"  - {sym['name']} ({sym['kind']}) in {sym['file']} [depth {sym['depth']}]"
                )
        else:
            context_lines.append("No downstream symbols found in the graph.")

    # Auto-detect files and symbols from the question
    if not context_lines:
        files, symbols = _extract_hints(question)

        for f in files:
            file_context = _query_graph_for_file(f)
            context_lines.extend(file_context)

        for s in symbols:
            sym_context = _query_graph_for_symbol(s)
            context_lines.extend(sym_context)

        # If still no context, try treating the whole question as a file search
        if not context_lines and files:
            context_lines.append(f"No data found in graph for: {', '.join(files)}")

    context = "\n".join(context_lines) if context_lines else "No symbol context provided."
    return _call(question, context)
