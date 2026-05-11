"""
CLI — `codepulse chat` command.

Interactive REPL for conversational Q&A over the code graph.
Usage:
    codepulse chat
    codepulse chat --symbol charge_card
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from codepulse.agents.chat_agent import answer

console = Console()


def chat_command(
    symbol: str = typer.Option(None, "--symbol", "-s", help="Default symbol context for queries"),
) -> None:
    """Open an interactive chat session to explore your codebase."""
    console.print(
        Panel(
            "[bold cyan]CodePulse Chat[/]\n"
            "Ask questions about your indexed codebase.\n"
            "Type [bold]exit[/] or [bold]quit[/] to leave.\n"
            "Type [bold]/symbol <name>[/] to set context.",
            border_style="blue",
        )
    )

    while True:
        try:
            question = console.input("\n[bold green]you >[/] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/]")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            console.print("[dim]Goodbye![/]")
            break

        # Allow switching symbol context inline
        current_symbol = symbol
        if question.startswith("/symbol "):
            current_symbol = question.split(" ", 1)[1].strip()
            symbol = current_symbol
            console.print(f"[dim]Context set to symbol: {current_symbol}[/]")
            continue

        console.print(f"[green]●[/green] [cyan]chat_agent[/cyan]  [dim]querying graph…[/dim]")
        result = answer(question, symbol_hint=current_symbol)
        console.print(f"[green]●[/green] [cyan]chat_agent[/cyan]  [dim]done[/dim]")

        console.print(Panel(
            Markdown(result),
            title="[bold cyan]codepulse[/]",
            border_style="blue",
            padding=(1, 2),
        ))
