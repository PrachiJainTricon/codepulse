"""
codepulse repos — manage indexed repositories.

Sub-commands:
    codepulse repos list              — show all registered repos
    codepulse repos remove <path>     — unregister a repo + clear its cache
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from codepulse.db.migrations import run_migrations
from codepulse.db.run_store import RepoStore

console = Console()

# Typer sub-app for "codepulse repos ..."
repos_app = typer.Typer(
    name="repos",
    help="List and manage indexed repositories.",
    invoke_without_command=True,
)


@repos_app.callback(invoke_without_command=True)
def repos_default(ctx: typer.Context) -> None:
    """Show indexed repos (shortcut for `codepulse repos list`)."""
    if ctx.invoked_subcommand is None:
        repos_list()


@repos_app.command(name="list")
def repos_list() -> None:
    """List all repositories that codepulse has indexed."""
    run_migrations()

    with RepoStore() as store:
        repos = store.list_all()

    if not repos:
        console.print(
            "[yellow]No repos indexed yet. "
            "Run:[/]  codepulse index /path/to/repo"
        )
        return

    table = Table(title="Indexed Repositories", show_lines=False)
    table.add_column("ID",          justify="right", style="dim")
    table.add_column("Name",        style="bold cyan")
    table.add_column("Path",        style="white", no_wrap=True)
    table.add_column("Languages",   style="magenta")
    table.add_column("Files",       justify="right")
    table.add_column("Symbols",     justify="right")
    table.add_column("Last Indexed", style="green")

    for r in repos:
        table.add_row(
            str(r.id),
            r.name,
            r.root_path,
            r.languages or "—",
            str(r.total_files),
            str(r.total_symbols),
            r.last_indexed or "never",
        )

    console.print(table)
    console.print()


@repos_app.command(name="remove")
def repos_remove(
    repo_path: Path = typer.Argument(
        None,
        help="Path to the repository to unregister. Defaults to current directory.",
        resolve_path=True,
    ),
) -> None:
    """Unregister a repo and clear its snapshot cache."""
    if repo_path is None:
        repo_path = Path.cwd()

    run_migrations()
    root_str = str(repo_path.resolve())

    with RepoStore() as store:
        removed = store.remove(root_str)

    if removed:
        console.print(
            f"[green]Removed[/] repo [cyan]{root_str}[/] "
            "and cleared its snapshot cache."
        )
    else:
        console.print(f"[yellow]No repo found at[/] {root_str}")
