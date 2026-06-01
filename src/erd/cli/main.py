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

from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from erd import __version__
from erd.config import Config, init_project_config
from erd.cli.run import run_pipeline, run_single_phase

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
    cfg = init_project_config(
        project_id=project_id,
        project_name=name,
        jurisdiction=jurisdiction,
        workspace_root=Path(output).resolve(),
        input_dir=Path("./input").resolve(),
    )
    console.print(f"[green]✓[/] Initialised project [bold]{name}[/]")
    console.print(f"  Project ID:  {project_id}")
    console.print(f"  Jurisdiction: {jurisdiction}")
    console.print(f"  Workspace:    {cfg.project_dir}")
    console.print("\n[yellow]ℹ[/] Ready. Run [bold]erd run --project {project_id} --phase 0[/] to run Ingestion & Triage.")


@app.command()
def run(
    project: str = typer.Option(..., "--project", "-p", help="Project ID (from erd init)"),
    input_dir: str = typer.Option(
        "./input", "--input", "-i",
        help="Directory containing field records",
    ),
    strict: bool = typer.Option(
        False, "--strict", "-s",
        help="Halt Phase 1 if schema contract validation fails",
    ),
    extractor: str = typer.Option(
        "glm-ocr", "--extractor", "-e",
        help="Phase 1 extraction model: glm-ocr (default) or nuextract3",
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
    workspace_root = Path(workspace).resolve()
    input_path = Path(input_dir).resolve()

    # Auto-init if project doesn't exist yet
    cfg = Config(
        project_id=project,
        project_name=project,
        jurisdiction="historic_england_cl3",
        workspace_root=workspace_root,
        input_dir=input_path,
        strict=strict,
        extractor=extractor,
    )

    if phase is not None:
        run_single_phase(cfg, phase)
    else:
        run_pipeline(cfg)


@app.command(name="import-ark")
def import_ark(
    project: str = typer.Option(..., "--project", "-p", help="Project ID"),
    input_dir: str = typer.Option(
        "./input", "--input", "-i",
        help="Directory containing ARK export files (context.csv, finds.csv, etc.)",
    ),
    workspace: str = typer.Option(
        "./erd_workspace", "--workspace", "-w",
        help="Working directory root",
    ),
) -> None:
    """Import structured data from ARK system exports.

    Bypasses Phase 0 (file ingestion) and Phase 1 (OCR) for digital-first
    excavations. Accepts CSV or JSON exports matching ARK conventions.
    """
    workspace_root = Path(workspace).resolve()
    input_path = Path(input_dir).resolve()

    if not input_path.is_dir():
        console.print(f"[red]✗[/] Input directory not found: {input_path}")
        raise typer.Exit(1)

    cfg = Config(
        project_id=project,
        project_name=project,
        jurisdiction="historic_england_cl3",
        workspace_root=workspace_root,
        input_dir=input_path,
    )

    project_dir = cfg.project_dir
    project_dir.mkdir(parents=True, exist_ok=True)

    from erd.ark import import_ark_export

    result = import_ark_export(cfg)

    if result.errors and result.total_records == 0:
        console.print("[red]✗[/] ARK import failed.")
        for err in result.errors:
            console.print(f"  [red]•[/] {err}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/] ARK import complete for [bold]{project}[/]")
    console.print(f"  Files found:    {result.files_found}")
    console.print(f"  Files parsed:   {result.files_parsed}")
    console.print(f"  Records imported: {result.total_records}")

    if result.records_by_type:
        console.print("\n  [underline]By type:[/]")
        for source_type, count in sorted(result.records_by_type.items()):
            hoard_type = {
                "context": "Context sheets",
                "finds": "Finds catalogue",
                "samples": "Sample records",
                "photos": "Photo log",
                "drawings": "Drawings/plans",
            }.get(source_type, source_type)
            console.print(f"    • {hoard_type}: {count}")

    if result.warnings:
        console.print("\n[yellow]Warnings:[/]")
        for w in result.warnings:
            console.print(f"  [yellow]•[/] {w}")

    if result.errors:
        console.print(f"\n[yellow]Errors ({len(result.errors)}):[/]")
        for e in result.errors:
            console.print(f"  [yellow]•[/] {e}")

    console.print(f"\n  Manifest: {result.manifest_path}")
    console.print("\n[yellow]ℹ[/] Phases 0 and 1 have been marked as bypassed. "
                  "You can proceed with Phase 2+ as normal.")


@app.command()
def review(
    project: str = typer.Option(..., "--project", "-p", help="Project ID"),
    workspace: str = typer.Option(
        "./erd_workspace", "--workspace", "-w",
        help="Working directory root",
    ),
    reset: bool = typer.Option(
        False, "--reset", "-r",
        help="Reset all review decisions and start fresh",
    ),
) -> None:
    """Open the review dashboard for flagged items."""
    workspace_root = Path(workspace).resolve()
    cfg = Config(
        project_id=project,
        project_name=project,
        jurisdiction="historic_england_cl3",
        workspace_root=workspace_root,
        input_dir=Path("./input"),
    )

    if not cfg.project_dir.exists():
        console.print(f"[red]✗[/] Project '{project}' not found at {cfg.project_dir}")
        console.print("  Initialise it first with: [bold]erd init --name '...' --project {project}[/]")
        raise typer.Exit(1)

    from erd.review import ReviewSession

    session = ReviewSession(cfg)
    session.load()

    if session.total == 0:
        console.print(f"[yellow]ℹ[/] No flagged items found for project '{project}'.")
        console.print("  Run [bold]erd run --project {project} --phase 0[/] first to generate a manifest.")
        return

    session.run_interactive()


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

        template_dir = Path(__file__).resolve().parent.parent.parent.parent / "templates"
        if template_dir.is_dir():
            rows = []
            for yaml_file in sorted(template_dir.glob("*.yaml")):
                try:
                    data = yaml.safe_load(yaml_file.read_text())
                    code = yaml_file.stem
                    jurisdiction = data.get("jurisdiction", "Unknown")
                    version = data.get("version", "?")
                    rows.append((code, jurisdiction, version))
                except Exception:
                    rows.append((yaml_file.stem, "Error loading template", "?"))

            for code, jurisdiction, version in rows:
                table.add_row(code, jurisdiction, version)

        console.print(table)
        console.print("\n[yellow]ℹ[/] Add new templates by creating *.yaml files in the templates/ directory.")
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
