"""
CodePulse CLI entry point.

Commands:
    codepulse diff [REF]   — blast-radius analysis for a git diff
    codepulse ask  QUERY   — conversational query (stub for now)
"""

from __future__ import annotations

import typer
from codepulse.cli.diff_cmd import diff_command

app = typer.Typer(
    name="codepulse",
    help="Understand the impact of your code changes.",
    add_completion=False,
    no_args_is_help=True,
)

# Register as a named subcommand so `codepulse diff HEAD~1` works correctly.
app.command("diff", help="Analyse blast radius and risk for a git diff.")(diff_command)


@app.command("version", hidden=True)
def _version() -> None:
    """Print version and exit."""
    typer.echo("codepulse 0.1.0")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
