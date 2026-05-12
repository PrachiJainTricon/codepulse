"""CLI — `codepulse ui` command. Starts the FastAPI dev server."""

from __future__ import annotations

import typer


def ui_command(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on"),
    reload: bool = typer.Option(True, "--reload/--no-reload", help="Enable auto-reload"),
) -> None:
    """Start the CodePulse REST API server."""
    try:
        import uvicorn
    except ImportError:
        typer.echo("[red]uvicorn not installed. Run: pip install uvicorn[standard][/red]")
        raise typer.Exit(1)

    typer.echo(f"Starting CodePulse API at http://{host}:{port}")
    typer.echo("Docs available at http://{host}:{port}/docs")
    uvicorn.run(
        "codepulse.api.server:app",
        host=host,
        port=port,
        reload=reload,
    )
