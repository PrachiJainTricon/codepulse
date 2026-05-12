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

import time
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from codepulse.git.diff_resolver import resolve_diff
from codepulse.git._gitcli import git_output
from codepulse.agents.pipeline import run_pipeline
from codepulse.agents.state import RiskResult

console = Console()

_LEVEL_COLOR = {"low": "green", "medium": "yellow", "high": "red"}
_LEVEL_ICON = {"low": "✅", "medium": "⚠️", "high": "⚠️"}
_DEPTH_COLOR = {1: "red", 2: "yellow", 3: "green"}


def diff_command(
    ref: str = typer.Argument("HEAD~1", help="Git ref to diff against"),
    repo: str = typer.Option(".", "--repo", "-r", help="Path to the git repo"),
    show_pr: bool = typer.Option(False, "--pr", help="Print generated PR description"),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Analyse the blast radius of a git diff and explain the risk."""

    repo_path = str(Path(repo).resolve())
    start_time = time.time()

    # ── Phase 1: Git resolution ──────────────────────────────────────────────
    console.print()
    console.print("[dim]───────────── ⎇ git resolution ─────────────[/dim]")

    # Resolve the short SHA
    short_sha = git_output(Path(repo_path), "rev-parse", "--short", ref) or ref
    console.print(f"[green]●[/green] resolving {ref}  →  commit {short_sha}")

    try:
        changed = resolve_diff(repo_path, commit_ref=ref)
    except RuntimeError as exc:
        console.print(f"[red]●[/red] Error: {exc}")
        raise typer.Exit(1)

    if not changed:
        console.print("[yellow]●[/yellow] No changed symbols detected in this diff.")
        raise typer.Exit(0)

    # Show changed files and symbols
    changed_files = list({s["file"] for s in changed if s.get("file")})
    changed_names = list({s["symbol"] for s in changed})
    console.print(f"[green]●[/green] changed files: {len(changed_files)}  ({', '.join(changed_files[:4])}{'…' if len(changed_files) > 4 else ''})")
    console.print(f"[green]●[/green] changed symbols: {', '.join(changed_names[:5])}{'…' if len(changed_names) > 5 else ''}")

    # ── Phase 2: Agent pipeline ──────────────────────────────────────────────
    console.print()
    console.print("[dim]───────────── ⬡ agent pipeline ─────────────[/dim]")

    result: RiskResult = run_pipeline(
        repo_path=repo_path,
        commit_ref=ref,
        changed_symbols=changed,
    )

    fan_out = len(result["impacted_symbols"])
    test_gaps = result.get("test_gaps", [])
    tests_to_run = result.get("tests_to_run", [])

    console.print(f"[green]●[/green] [cyan]change_investigator[/cyan]  [dim]blast radius: {fan_out} symbols[/dim]")
    if fan_out >= 5:
        console.print(f"[green]●[/green] [cyan]risk_analyst[/cyan]  [dim]fan-out {fan_out} · coverage gaps: {len(test_gaps)}[/dim]")
        console.print(f"[green]●[/green] [cyan]test_advisor[/cyan]  [dim]mapped {fan_out} symbols · {len(test_gaps)} with no test coverage[/dim]")
    else:
        console.print(f"[dim]  ↳ blast radius < 5 — skipping risk_analyst[/dim]")
        console.print(f"[green]●[/green] [cyan]test_advisor[/cyan]  [dim]{len(test_gaps)} gaps found[/dim]")
    console.print(f"[green]●[/green] [cyan]explainer[/cyan]  [dim]impact paths written[/dim]")
    console.print(f"[green]●[/green] [cyan]pr_writer[/cyan]  [dim]description generated[/dim]")

    elapsed = time.time() - start_time

    if json_out:
        import json
        console.print_json(json.dumps(result))
        return

    # Persist for `codepulse report`
    from codepulse.cli.report_cmd import save_report
    save_report(result)

    _print_result(result, show_pr=show_pr, elapsed=elapsed)


# ── Rich output ──────────────────────────────────────────────────────────────

def _print_result(result: RiskResult, show_pr: bool, elapsed: float) -> None:
    level = result["level"]
    color = _LEVEL_COLOR.get(level, "white")
    icon = _LEVEL_ICON.get(level, "●")

    # ── Risk banner ──────────────────────────────────────────────────────────
    console.print()
    fan_out = len(result["impacted_symbols"])
    test_gaps = result.get("test_gaps", [])
    tests_to_run = result.get("tests_to_run", [])
    reasons = result.get("reasons", [])
    changed_files = list({s.get("file", "") for s in result["changed_symbols"]})
    impacted_files = list({s.get("file", "") for s in result["impacted_symbols"] if s.get("file")})

    risk_text = Text()
    risk_text.append(f"{icon} {level.upper()} RISK\n", style=f"bold {color}")
    if reasons:
        risk_text.append("; ".join(reasons), style="dim")
    else:
        summary_parts = []
        if fan_out:
            summary_parts.append(f"{fan_out} downstream symbols impacted")
        if test_gaps:
            summary_parts.append(f"{len(test_gaps)} uncovered paths")
        risk_text.append(". ".join(summary_parts) if summary_parts else "Minimal impact.", style="dim")

    console.print(Panel(risk_text, border_style=color))

    # ── Blast radius table ───────────────────────────────────────────────────
    impacted = result["impacted_symbols"]
    if impacted:
        console.print(f"\n[dim bold]BLAST RADIUS — {fan_out} impacted symbols[/dim bold]")
        t = Table(box=box.SIMPLE, show_header=True, header_style="dim")
        t.add_column("Symbol", style="bold cyan")
        t.add_column("Kind", style="dim")
        t.add_column("File", style="blue")
        t.add_column("Hops")
        t.add_column("Test Coverage")

        shown = impacted[:7]
        for imp in shown:
            depth = imp.get("depth", 0)
            depth_color = _DEPTH_COLOR.get(depth, "white")
            # Check if this symbol is in test_gaps
            gap_key = f"{imp.get('file', '?')}::{imp['name']}"
            has_cov = gap_key not in test_gaps
            cov_text = f"[green]✓ covered[/green]" if has_cov else f"[red]✗ no coverage[/red]"

            t.add_row(
                imp["name"],
                imp.get("kind", "?"),
                imp.get("file", "?"),
                f"[{depth_color}]{depth}[/{depth_color}]",
                cov_text,
            )

        if len(impacted) > 7:
            t.add_row(
                f"[dim]+ {len(impacted) - 7} more[/dim]", "", "", "",
                "[dim]run codepulse report --format json[/dim]",
            )
        console.print(t)

    # ── Explanation (impact paths) ───────────────────────────────────────────
    if result.get("explanation"):
        console.print(Panel(
            result["explanation"],
            title="[bold]WHY — impact paths explained[/]",
            border_style="cyan",
            padding=(1, 2),
        ))

    # ── Test recommendations ─────────────────────────────────────────────────
    if tests_to_run or test_gaps:
        console.print("\n[dim bold]TEST RECOMMENDATIONS[/dim bold]")
        for tf in tests_to_run:
            console.print(f"  [green]▶ MUST RUN[/green]   {tf}")
        for gap in test_gaps:
            console.print(f"  [yellow]⚠ WRITE NEW[/yellow]  {gap}")
        console.print()

    # ── PR description ───────────────────────────────────────────────────────
    if show_pr and result.get("pr_description"):
        console.print(Panel(
            result["pr_description"],
            title="[bold magenta]Generated PR Description[/]",
            border_style="magenta",
            padding=(1, 2),
        ))

    # ── Summary footer ───────────────────────────────────────────────────────
    console.print(f"[dim]{'─' * 60}[/dim]")
    parts = [
        f"[{color}]{level.upper()}[/{color}] risk",
        f"[bold]{fan_out}[/bold] impacted",
        f"{len(impacted_files)} files",
        f"[red]{len(test_gaps)}[/red] uncovered" if test_gaps else "[green]0[/green] uncovered",
        f"[green]{len(tests_to_run)}[/green] tests to run",
        f"[dim]{elapsed:.1f}s[/dim]",
    ]
    console.print("  " + "  ·  ".join(parts))

    # ── Next actions ─────────────────────────────────────────────────────────
    console.print(f"\n[dim]next →[/dim] [cyan]codepulse report --format json[/cyan] [dim]|[/dim] [cyan]codepulse ask \"...\"[/cyan] [dim]|[/dim] [cyan]codepulse ui[/cyan]")
    console.print()
