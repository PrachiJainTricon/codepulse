"""
codepulse index — CLI wrapper around the index service.

This module only handles user interaction (arguments, pretty-printing).
All indexing logic lives in `indexer.index_service`; graph-payload and
ingestion logic lives under `codepulse.graph`.

Usage:
    cd /any/project && codepulse index        # index current directory
    codepulse index /path/to/any-repo         # index a specific repo
    codepulse index --full                    # force full re-index
    codepulse index --to-graph                # index and push to Neo4j
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from codepulse.graph import Neo4jIngestion, build_graph_payload
from codepulse.indexer.index_service import IndexReport, run_index

console = Console()
_snapshot_warning_emitted = False


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
    if repo_path is None:
        repo_path = Path.cwd()
    console.print(
        f"\n[bold]codepulse index[/] — scanning [cyan]{repo_path}[/]\n"
    )

    report = run_index(repo_path, full=full)
    _print_report(report)

    if to_graph:
        _push_to_graph(repo_path)


# ── Graph push ────────────────────────────────────────────────


def _push_to_graph(repo_path: Path) -> None:
    """Build the ingestion payload and stream it to Neo4j."""
    console.print("\n[bold]Pushing to Neo4j...[/]\n")
    try:
        payload = build_graph_payload(repo_path)
        _warn_if_snapshot(payload.get("mode"))

        with Neo4jIngestion() as ingestion:
            ingestion.initialize_schema()
            stats = ingestion.ingest_from_json(payload)

        console.print("[green]Neo4j ingestion complete:[/]")
        console.print(f"  Files: {stats['files_processed']}")
        console.print(f"  Symbols: {stats['symbols_created']}")
        console.print(f"  Packages: {stats['packages_created']}")
        console.print(f"  Relationships: {stats['relationships_created']}")
    except Exception as exc:
        console.print(f"[red]Neo4j push failed: {exc}[/]")


def _warn_if_snapshot(mode: str | None) -> None:
    """Emit a one-shot warning when we're in non-git snapshot mode."""
    global _snapshot_warning_emitted
    if mode == "snapshot" and not _snapshot_warning_emitted:
        console.print(
            "[yellow]No git repo detected — running in snapshot mode "
            "(diff disabled)[/]"
        )
        _snapshot_warning_emitted = True


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

    table.add_section()
    table.add_row(
        "[bold]Total[/]", "",
        f"[bold]{report.total_symbols}[/]",
        f"[bold]{report.total_imports}[/]",
        f"[bold]{report.total_calls}[/]",
        f"[bold]{report.total_exports}[/]",
    )

    console.print(table)

    console.print(
        f"\n  Repo registered as [bold]{report.repo.name}[/]"
        f"  (id={report.repo.id})"
    )
    console.print(
        f"  Languages: [magenta]{report.repo.languages}[/]"
    )
    console.print()
