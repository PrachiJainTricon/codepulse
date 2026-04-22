"""
codepulse CLI — entry point.

All sub-commands are registered here into the Typer app.
Run with:
    codepulse help
    codepulse index
    codepulse repos
    codepulse remove /path/to/repo
"""

import typer

app = typer.Typer(
    name="codepulse",
    help="Code intelligence powered by graph analysis.",
    add_completion=False,
    invoke_without_command=True,
)

# ── Register sub-commands ─────────────────────────────────────

from codepulse.cli.index_cmd import index                    # noqa: E402
from codepulse.cli.repos_cmd import repos_app, repos_remove  # noqa: E402

app.command(name="index")(index)
app.command(name="remove")(repos_remove)      # top-level shortcut
app.add_typer(repos_app, name="repos")


@app.command(name="help", hidden=True)
def show_help(ctx: typer.Context) -> None:
    """Show this help message."""
    # Walk up to root context to get the main help
    root = ctx
    while root.parent is not None:
        root = root.parent
    typer.echo(root.get_help())


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Code intelligence powered by graph analysis."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
