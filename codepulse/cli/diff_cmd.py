"""
CLI — `codepulse diff` command.

Usage:
    codepulse diff                      # diff HEAD~1 (default)
    codepulse diff HEAD~3               # diff 3 commits back
    codepulse diff abc123               # diff a specific SHA
    codepulse diff HEAD~1 --repo ./app  # explicit repo path
    codepulse diff HEAD~1 --pr          # also print PR description
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from codepulse.git.diff_resolver import resolve_diff
from codepulse.agents.pipeline import run_pipeline
from codepulse.agents.state import RiskResult

console = Console()

_LEVEL_COLOR = {"low": "green", "medium": "yellow", "high": "red"}


def diff_command(
    ref: str = typer.Argument("HEAD~1", help="Git ref to diff against"),
    repo: str = typer.Option(".", "--repo", "-r", help="Path to the git repo"),
    show_pr: bool = typer.Option(False, "--pr", help="Print generated PR description"),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Analyse the blast radius of a git diff and explain the risk."""

    repo_path = str(Path(repo).resolve())

    with console.status(f"[bold blue]Parsing diff {ref}…"):
        try:
            changed = resolve_diff(repo_path, commit_ref=ref)
        except RuntimeError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)

    if not changed:
        console.print("[yellow]No changed symbols detected in this diff.[/yellow]")
        raise typer.Exit(0)

    with console.status("[bold blue]Running impact analysis…"):
        result: RiskResult = run_pipeline(
            repo_path=repo_path,
            commit_ref=ref,
            changed_symbols=changed,
        )

    if json_out:
        import json
        console.print_json(json.dumps(result))
        return

    _print_result(result, show_pr=show_pr)


# ── Rich output helpers ───────────────────────────────────────────────────────

def _print_result(result: RiskResult, show_pr: bool) -> None:
    level = result["level"]
    color = _LEVEL_COLOR.get(level, "white")

    # ── Changed symbols ──────────────────────────────────────────────────────
    t = Table(title="Changed Symbols", box=box.SIMPLE, show_header=True)
    t.add_column("Symbol", style="bold")
    t.add_column("Kind")
    t.add_column("File", style="dim")
    t.add_column("Change")
    for sym in result["changed_symbols"]:
        t.add_row(
            sym["symbol"],
            sym.get("kind", "?"),
            sym.get("file", "?"),
            sym.get("change_type", "?"),
        )
    console.print(t)

    # ── Impacted symbols ─────────────────────────────────────────────────────
    if result["impacted_symbols"]:
        t2 = Table(title="Downstream Impact", box=box.SIMPLE, show_header=True)
        t2.add_column("Symbol", style="bold")
        t2.add_column("Kind")
        t2.add_column("File", style="dim")
        t2.add_column("Depth")
        for imp in result["impacted_symbols"]:
            t2.add_row(
                imp["name"],
                imp.get("kind", "?"),
                imp.get("file", "?"),
                str(imp.get("depth", "?")),
            )
        console.print(t2)
    else:
        console.print("[dim]No downstream symbols found.[/dim]")

    # ── Risk summary ─────────────────────────────────────────────────────────
    console.print(
        Panel(
            f"[bold {color}]Risk: {level.upper()}[/bold {color}]  "
            f"(score: {result['score']})\n\n"
            + "\n".join(f"• {r}" for r in result["reasons"]),
            title="Risk Assessment",
            border_style=color,
        )
    )

    # ── Explanation ──────────────────────────────────────────────────────────
    console.print(Panel(result["explanation"], title="Explanation", border_style="blue"))

    # ── PR description (opt-in) ──────────────────────────────────────────────
    if show_pr and result.get("pr_description"):
        console.print(Panel(result["pr_description"], title="PR Description", border_style="magenta"))
