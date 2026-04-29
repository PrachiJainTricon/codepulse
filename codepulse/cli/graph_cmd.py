"""
codepulse graph — CLI commands for Neo4j graph management.

Usage:
    codepulse graph clear    # Clear all nodes from Neo4j
"""

from __future__ import annotations

import typer
from rich.console import Console

from neo4j import GraphDatabase

from codepulse.config import settings

graph_app = typer.Typer(name="graph", help="Manage Neo4j graph.")
console = Console()


@graph_app.command(name="clear")
def clear_graph() -> None:
    """Clear all nodes and relationships from Neo4j."""
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )

    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
        console.print("[green]Neo4j graph cleared![/]")

    driver.close()