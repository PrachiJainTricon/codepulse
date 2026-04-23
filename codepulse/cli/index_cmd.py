"""
codepulse index — CLI wrapper around the index service.

This module handles ONLY user interaction (arguments, printing).
All indexing logic lives in `indexer.index_service`.

Usage:
    cd /any/project && codepulse index        # index current directory
    codepulse index /path/to/any-repo          # index a specific repo
    codepulse index --full                     # force full re-index
    codepulse index --to-graph                  # index and push to Neo4j
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from codepulse.graph.client import Neo4jIngestion
from codepulse.indexer.index_service import IndexReport, run_index
from codepulse.tree_parser import to_legacy_file_result

console = Console()


def index(
    repo_path: Path = typer.Argument(
        None,
        help="Path to the repository to index. Defaults to current directory.",
        exists=True,
        file_okay=False,
        resolve_path=True,
    ),
    full: bool = typer.Option(
        False,
        "--full",
        help="Force full re-index, ignoring the snapshot cache.",
    ),
    to_graph: bool = typer.Option(
        False,
        "--to-graph",
        help="After indexing, push results to Neo4j graph.",
    ),
) -> None:
    """
    Index a repository: scan files, parse ASTs, extract symbols.

    Run inside any project directory, or pass a path.
    Unchanged files are skipped automatically unless --full is set.
    Use --to-graph to push results to Neo4j.
    """
    # Default to current working directory
    if repo_path is None:
        repo_path = Path.cwd()
    console.print(
        f"\n[bold]codepulse index[/] — scanning [cyan]{repo_path}[/]\n"
    )

    # All real work happens in the service layer
    report = run_index(repo_path, full=full)

    _print_report(report)

    # Push to Neo4j if requested
    if to_graph and report.results:
        console.print("\n[bold]Pushing to Neo4j...[/]\n")
        try:
            repo_name = repo_path.name
            json_data = {
                "root": str(repo_path),
                "repo_name": repo_name,
                "files_parsed": len(report.results),
                "results": [to_legacy_file_result(r, repo_name) for r in report.results],
            }
            with Neo4jIngestion() as ingestion:
                ingestion.initialize_schema()
                stats = ingestion.ingest_from_json(json_data)
            console.print(f"[green]Neo4j ingestion complete:[/]")
            console.print(f"  Files: {stats['files_processed']}")
            console.print(f"  Symbols: {stats['symbols_created']}")
            console.print(f"  Packages: {stats['packages_created']}")
            console.print(f"  Relationships: {stats['relationships_created']}")
        except Exception as e:
            console.print(f"[red]Neo4j push failed: {e}[/]")


# ── Display helpers (CLI-only) ────────────────────────────────


def _print_report(report: IndexReport) -> None:
    """Pretty-print the index results to the terminal."""
    if not report.results:
        console.print("[yellow]No new or changed files to index.[/]")
        if report.skipped_files:
            console.print(
                f"  ({report.skipped_files} file(s) unchanged)\n"
            )
        return

    console.print(
        f"[bold green]Parsed {report.total_files} file(s)[/]"
        f"  ({report.skipped_files} unchanged, skipped)\n"
    )

    # ── Per-file breakdown table ──────────────────────────────
    table = Table(title="Parse Results", show_lines=False)
    table.add_column("File",     style="cyan",    no_wrap=True)
    table.add_column("Language", style="magenta")
    table.add_column("Symbols",  justify="right")
    table.add_column("Imports",  justify="right")
    table.add_column("Calls",    justify="right")
    table.add_column("Exports",  justify="right")

    for r in report.results:
        table.add_row(
            r.file.path,
            r.file.language.value,
            str(len(r.symbols)),
            str(len(r.imports)),
            str(len(r.calls)),
            str(len(r.exports)),
        )

    # Totals row
    table.add_section()
    table.add_row(
        "[bold]Total[/]", "",
        f"[bold]{report.total_symbols}[/]",
        f"[bold]{report.total_imports}[/]",
        f"[bold]{report.total_calls}[/]",
        f"[bold]{report.total_exports}[/]",
    )

    console.print(table)

    # Repo info
    console.print(
        f"\n  Repo registered as [bold]{report.repo.name}[/]"
        f"  (id={report.repo.id})"
    )
    console.print(
        f"  Languages: [magenta]{report.repo.languages}[/]"
    )
    console.print()
