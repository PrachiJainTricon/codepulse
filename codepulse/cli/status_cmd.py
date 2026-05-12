"""
CLI — `codepulse status` command.

Shows graph health: total nodes/edges, last index timestamp,
Neo4j connection status, and SQLite size.
Usage:
    codepulse status
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from codepulse.config import settings
from codepulse.db.run_store import RepoStore

console = Console()


def status_command() -> None:
    """Show graph health, registered repos, and connection status."""

    # ── SQLite info ──────────────────────────────────────────────────────────
    db_path = settings.db_path
    db_exists = db_path.exists()
    db_size = f"{db_path.stat().st_size / 1024:.1f} KB" if db_exists else "N/A"

    # ── Repos ────────────────────────────────────────────────────────────────
    repos = []
    if db_exists:
        try:
            store = RepoStore()
            repos = store.list_all()
        except Exception:
            pass

    # ── Neo4j connection ─────────────────────────────────────────────────────
    neo4j_ok = False
    node_count = 0
    edge_count = 0
    try:
        from codepulse.graph.client import Neo4jClient
        with Neo4jClient() as client:
            with client.driver.session(database=client.database) as session:
                node_count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
                edge_count = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            neo4j_ok = True
    except Exception:
        pass

    # ── Display ──────────────────────────────────────────────────────────────
    t = Table(title="CodePulse Status", box=box.ROUNDED, show_header=False)
    t.add_column("Key", style="bold")
    t.add_column("Value")

    t.add_row("Neo4j", f"[green]Connected[/] ({settings.neo4j_uri})" if neo4j_ok else "[red]Not reachable[/]")
    t.add_row("Graph nodes", str(node_count) if neo4j_ok else "—")
    t.add_row("Graph edges", str(edge_count) if neo4j_ok else "—")
    t.add_row("SQLite", f"{db_path}" if db_exists else "[yellow]Not created yet[/]")
    t.add_row("SQLite size", db_size)
    t.add_row("Registered repos", str(len(repos)))

    console.print(t)

    if repos:
        rt = Table(title="Repos", box=box.SIMPLE, show_header=True)
        rt.add_column("Name", style="bold")
        rt.add_column("Path", style="dim")
        rt.add_column("Files")
        rt.add_column("Symbols")
        rt.add_column("Last indexed")
        for r in repos:
            rt.add_row(
                r.name,
                r.root_path,
                str(r.total_files),
                str(r.total_symbols),
                r.last_indexed or "never",
            )
        console.print(rt)
