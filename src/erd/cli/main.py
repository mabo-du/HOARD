"""main.py — erd CLI entry point.

Usage: erd --help
       erd init --name 'Stoneyfield Farm 2026' --jurisdiction historic_england_cl3
       erd run --input ./field_records/ --project stoneyfield_2026
       erd run --project stoneyfield_2026 --phase 3
       erd run --project stoneyfield_2026 --from-phase 3
       erd review --project stoneyfield_2026
       erd export --project stoneyfield_2026 --format docx,pdf
       erd templates list

exports: app  (typer.Typer) — registered as `erd` console_scripts entry
used_by: pyproject.toml → [project.scripts] erd
rules:   All subcommands must produce a non-error help message when their
         full implementation is not yet available. Never import GPU-bound
         modules at CLI import time.
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Initial scaffold
"""

import typer
from rich.console import Console
from rich.table import Table

from erd import __version__

app = typer.Typer(
    name="erd",
    help="Heritage Observation And Report Drafter — archaeological grey literature pipeline",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"erd v{__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", "-V", help="Show version and exit", callback=_version_callback,
    ),
) -> None:
    """Heritage Observation And Report Drafter."""


@app.command()
def init(
    name: str = typer.Argument(..., help="Project name, e.g. 'Stoneyfield Farm 2026'"),
    jurisdiction: str = typer.Option(
        "historic_england_cl3", "--jurisdiction", "-j",
        help="Jurisdiction template code",
    ),
    output: str = typer.Option(
        "./erd_workspace", "--output", "-o",
        help="Working directory root",
    ),
) -> None:
    """Initialise a new ERD project."""
    project_id = name.lower().replace(" ", "_").replace("'", "")
    console.print(f"[green]✓[/] Initialised project [bold]{name}[/]")
    console.print(f"  Project ID:  {project_id}")
    console.print(f"  Jurisdiction: {jurisdiction}")
    console.print(f"  Workspace:    {output}/{project_id}/")
    console.print("\n[yellow]ℹ[/] Ready. Run [bold]erd run --project {project_id}[/] to start the pipeline.")
    console.print("  (Full implementation coming — Phase 0 is available now.)")


@app.command()
def run(
    project: str = typer.Option(..., "--project", "-p", help="Project ID (from erd init)"),
    input_dir: str = typer.Option(
        "./input", "--input", "-i",
        help="Directory containing field records",
    ),
    phase: int | None = typer.Option(None, "--phase", help="Run a single phase only"),
    from_phase: int | None = typer.Option(
        None, "--from-phase", help="Run from this phase onward",
    ),
    workspace: str = typer.Option(
        "./erd_workspace", "--workspace", "-w",
        help="Working directory root",
    ),
) -> None:
    """Run the pipeline (full or partial)."""
    if phase is not None:
        console.print(f"[blue]→[/] Running phase {phase} only for project [bold]{project}[/]")
    elif from_phase is not None:
        console.print(f"[blue]→[/] Running phases {from_phase}–5 for project [bold]{project}[/]")
    else:
        console.print(f"[blue]→[/] Running full pipeline for project [bold]{project}[/]")
    console.print(f"  Input:    {input_dir}")
    console.print(f"  Workspace: {workspace}/{project}/")

    # Phase routing — Phase 0 is the only one implemented so far
    if phase is None or phase == 0:
        console.print("\n[yellow]ℹ[/] Phase 0 (Ingestion & Triage): available")
        console.print("  Use [bold]erd run --project {project} --phase 0[/] to run it.")
    if phase is None or phase in (1, 2, 3, 4):
        console.print(f"\n[yellow]ℹ[/] Phase {phase or '1–4'} (Digitisation/Spatial/Drafting/Compliance):")
        console.print("  Requires GPU. Training in progress — check back after ~24h.")
    if phase is None or phase == 5:
        console.print("\n[yellow]ℹ[/] Phase 5 (Assembly & Export): not yet implemented")


@app.command()
def review(
    project: str = typer.Option(..., "--project", "-p", help="Project ID"),
    workspace: str = typer.Option(
        "./erd_workspace", "--workspace", "-w",
        help="Working directory root",
    ),
) -> None:
    """Open the review dashboard for flagged items."""
    console.print(f"[blue]→[/] Opening review dashboard for [bold]{project}[/]")
    console.print(f"  Workspace: {workspace}/{project}/")
    console.print("\n[yellow]ℹ[/] Review dashboard will be available after Phase 0 produces its first manifest.")
    console.print("  (Terminal TUI — coming in a later sprint.)")


@app.command()
def export(
    project: str = typer.Option(..., "--project", "-p", help="Project ID"),
    fmt: str = typer.Option(
        "docx,pdf", "--format", "-f",
        help="Output formats (comma-separated: docx, pdf, tei-xml, zip)",
    ),
    workspace: str = typer.Option(
        "./erd_workspace", "--workspace", "-w",
        help="Working directory root",
    ),
) -> None:
    """Export final report in specified formats."""
    formats = [f.strip() for f in fmt.split(",")]
    console.print(f"[blue]→[/] Exporting [bold]{project}[/] as: {', '.join(formats)}")
    console.print(f"  Output: {workspace}/{project}/05_final/")
    console.print("\n[yellow]ℹ[/] Export requires Phase 5 implementation (not yet built).")


@app.command(name="templates")
def templates_cmd(
    action: str = typer.Argument(
        "list", help="Action: list, show <name>, validate <file>",
    ),
    name: str | None = typer.Option(None, "--name", "-n", help="Template name (for 'show')"),
    file: str | None = typer.Option(None, "--file", "-f", help="Template file path (for 'validate')"),
) -> None:
    """List, show, or validate jurisdiction templates."""
    if action == "list":
        table = Table(title="Available Jurisdiction Templates")
        table.add_column("Code", style="cyan")
        table.add_column("Jurisdiction", style="green")
        table.add_column("Version")
        table.add_row("historic_england_cl3", "Historic England — Evaluation (CL3 compliant)", "2024")
        console.print(table)
        console.print("\n[yellow]ℹ[/] More templates can be added to templates/*.yaml")
    elif action == "show":
        if not name:
            console.print("[red]✗[/] Use --name <code> to specify a template")
            raise typer.Exit(1)
        console.print(f"[blue]→[/] Showing template [bold]{name}[/] (not yet loaded)")
    elif action == "validate":
        if not file:
            console.print("[red]✗[/] Use --file <path> to specify a template file")
            raise typer.Exit(1)
        console.print(f"[blue]→[/] Validating [bold]{file}[/] (validator not yet implemented)")
    else:
        console.print(f"[red]✗[/] Unknown action: {action}. Use: list, show, validate")


def entry_point() -> None:
    """Console-scripts entry point."""
    app()


if __name__ == "__main__":
    app()
