"""
CLI — `codepulse ask` command.

Single-shot question against the code graph.
Usage:
    codepulse ask "what calls validate()"
    codepulse ask "which tests cover charge_card" --symbol charge_card
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from codepulse.agents.chat_agent import answer

console = Console()


def ask_command(
    question: str = typer.Argument(..., help="Natural-language question about the codebase"),
    symbol: str = typer.Option(None, "--symbol", "-s", help="Symbol to use as context hint"),
) -> None:
    """Ask a single question about your indexed codebase."""
    console.print()
    console.print(f"[green]●[/green] [cyan]chat_agent[/cyan]  [dim]translating query…[/dim]")

    result = answer(question, symbol_hint=symbol)

    console.print(f"[green]●[/green] [cyan]chat_agent[/cyan]  [dim]graph query complete[/dim]")
    console.print()

    console.print(Panel(
        Markdown(result),
        title=f"[bold cyan]codepulse[/]",
        border_style="blue",
        padding=(1, 2),
    ))

    console.print(f"\n[dim]next →[/dim] [cyan]codepulse chat[/cyan] [dim]for follow-ups |[/dim] [cyan]codepulse diff[/cyan] [dim]for blast radius[/dim]")
    console.print()
