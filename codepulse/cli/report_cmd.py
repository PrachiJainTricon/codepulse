"""
CLI — `codepulse report` command.

Displays the last diff analysis result with Rich formatting.
Usage:
    codepulse report
    codepulse report --format markdown
    codepulse report --format json
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from codepulse.config import settings

console = Console()

_LEVEL_COLOR = {"low": "green", "medium": "yellow", "high": "red"}

_REPORT_FILE = settings.data_dir / "last_report.json"


def report_command(
    format: str = typer.Option("rich", "--format", "-f", help="Output format: rich, markdown, json"),
) -> None:
    """Display the last analysis report."""
    if not _REPORT_FILE.exists():
        console.print("[yellow]No report found. Run `codepulse diff` first.[/yellow]")
        raise typer.Exit(1)

    data = json.loads(_REPORT_FILE.read_text())

    if format == "json":
        console.print_json(json.dumps(data, indent=2))
        return

    if format == "markdown":
        console.print(_to_markdown(data))
        return

    _print_rich(data)


def save_report(result: dict) -> None:
    """Persist a report so `codepulse report` can display it later."""
    _REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_FILE.write_text(json.dumps(result, indent=2))


def _print_rich(result: dict) -> None:
    level = result.get("level", "unknown")
    color = _LEVEL_COLOR.get(level, "white")

    # Changed symbols
    changed = result.get("changed_symbols", [])
    if changed:
        t = Table(title="Changed Symbols", box=box.SIMPLE, show_header=True)
        t.add_column("Symbol", style="bold")
        t.add_column("Kind")
        t.add_column("File", style="dim")
        t.add_column("Change")
        for sym in changed:
            t.add_row(
                sym.get("symbol", "?"),
                sym.get("kind", "?"),
                sym.get("file", "?"),
                sym.get("change_type", "?"),
            )
        console.print(t)

    # Impacted symbols
    impacted = result.get("impacted_symbols", [])
    if impacted:
        t2 = Table(title="Downstream Impact", box=box.SIMPLE, show_header=True)
        t2.add_column("Symbol", style="bold")
        t2.add_column("Kind")
        t2.add_column("File", style="dim")
        t2.add_column("Depth")
        for imp in impacted:
            t2.add_row(
                imp.get("name", "?"),
                imp.get("kind", "?"),
                imp.get("file", "?"),
                str(imp.get("depth", "?")),
            )
        console.print(t2)

    # Risk
    console.print(
        Panel(
            f"[bold {color}]Risk: {level.upper()}[/bold {color}]  "
            f"(score: {result.get('score', '?')})\n\n"
            + "\n".join(f"• {r}" for r in result.get("reasons", [])),
            title="Risk Assessment",
            border_style=color,
        )
    )

    # Test recommendations
    tests_to_run = result.get("tests_to_run", [])
    test_gaps = result.get("test_gaps", [])
    if tests_to_run or test_gaps:
        t3 = Table(title="Test Recommendations", box=box.SIMPLE, show_header=True)
        t3.add_column("Action", style="bold")
        t3.add_column("Target")
        for tf in tests_to_run:
            t3.add_row("[green]MUST RUN[/green]", tf)
        for gap in test_gaps:
            t3.add_row("[yellow]WRITE NEW[/yellow]", gap)
        console.print(t3)

    # Explanation
    if result.get("explanation"):
        console.print(Panel(result["explanation"], title="Explanation", border_style="blue"))

    # PR description
    if result.get("pr_description"):
        console.print(Panel(result["pr_description"], title="PR Description", border_style="magenta"))


def _to_markdown(result: dict) -> str:
    level = result.get("level", "unknown")
    lines = [
        f"# Analysis Report",
        f"",
        f"## Risk: {level.upper()} (score: {result.get('score', '?')})",
        f"",
    ]
    for r in result.get("reasons", []):
        lines.append(f"- {r}")

    lines.append("")
    lines.append("## Changed Symbols")
    lines.append("")
    for sym in result.get("changed_symbols", []):
        lines.append(f"- **{sym.get('symbol', '?')}** ({sym.get('kind', '?')}) in `{sym.get('file', '?')}` — {sym.get('change_type', '?')}")

    impacted = result.get("impacted_symbols", [])
    if impacted:
        lines.append("")
        lines.append("## Downstream Impact")
        lines.append("")
        for imp in impacted:
            lines.append(f"- {imp.get('name', '?')} ({imp.get('kind', '?')}) in `{imp.get('file', '?')}` — depth {imp.get('depth', '?')}")

    if result.get("explanation"):
        lines.append("")
        lines.append("## Explanation")
        lines.append("")
        lines.append(result["explanation"])

    if result.get("pr_description"):
        lines.append("")
        lines.append("## PR Description")
        lines.append("")
        lines.append(result["pr_description"])

    return "\n".join(lines)
