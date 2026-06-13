"""main.py — hoard CLI entry point.

Usage: hoard --help
       hoard init --name 'Stoneyfield Farm 2026' --jurisdiction historic_england_cl3
       hoard run --input ./field_records/ --project stoneyfield_2026
       hoard run --project stoneyfield_2026 --phase 3
       hoard run --project stoneyfield_2026 --from-phase 3
       hoard review --project stoneyfield_2026
       hoard export --project stoneyfield_2026 --format docx,pdf
       hoard templates list

exports: app  (typer.Typer) — registered as `hoard` console_scripts entry
used_by: pyproject.toml → [project.scripts] hoard
rules:   All subcommands must produce a non-error help message when their
         full implementation is not yet available. Never import GPU-bound
         modules at CLI import time.
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Initial scaffold
"""

import json
from pathlib import Path
from typing import Any

import typer
import yaml
from rich.console import Console
from rich.table import Table

from hoard import __version__
from hoard.cli.keys import keys_app
from hoard.cli.run import run_pipeline, run_single_phase
from hoard.config import Config, init_project_config
from hoard.helpers import emit as hoard_emit, set_gui_mode
from hoard.templates.engine import TemplateEngine

app = typer.Typer(
    name="hoard",
    help="Heritage Observation And Report Drafter — archaeological grey literature pipeline",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


app.add_typer(keys_app)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"hoard v{__version__}")
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
        "./hoard_workspace", "--output", "-o",
        help="Working directory root",
    ),
    detect_hardware: bool = typer.Option(
        True, "--detect/--no-detect",
        help="Auto-detect hardware and suggest model tier",
    ),
) -> None:
    """Initialise a new HOARD project."""
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

    # Hardware detection and tier suggestion
    if detect_hardware:
        try:
            from hoard.providers import get_router
            router = get_router(force_reinit=True)
            console.print("\n[bold]Hardware Profile:[/]")
            for line in router.summary.split("\n"):
                console.print(f"  {line}")
        except ImportError:
            pass  # providers module not yet available (dev install without deps)

    console.print(f"\n[yellow]ℹ[/] Ready. Run [bold]hoard run --project {project_id} --phase 0[/] to run Ingestion & Triage.")


@app.command()
def run(
    project: str = typer.Option(..., "--project", "-p", help="Project ID (from hoard init)"),
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
        "./hoard_workspace", "--workspace", "-w",
        help="Working directory root",
    ),
    gui_mode: bool = typer.Option(
        False, "--gui-mode",
        help="Suppress Rich console output; emit structured JSON events to stdout",
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
        run_single_phase(cfg, phase, gui_mode=gui_mode)
    else:
        run_pipeline(cfg, gui_mode=gui_mode)


@app.command(name="import-ark")
def import_ark(
    project: str = typer.Option(..., "--project", "-p", help="Project ID"),
    input_dir: str = typer.Option(
        "./input", "--input", "-i",
        help="Directory containing ARK export files (context.csv, finds.csv, etc.)",
    ),
    workspace: str = typer.Option(
        "./hoard_workspace", "--workspace", "-w",
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

    from hoard.ark import import_ark_export

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
        "./hoard_workspace", "--workspace", "-w",
        help="Working directory root",
    ),
    reset: bool = typer.Option(
        False, "--reset", "-r",
        help="Reset all review decisions and start fresh",
    ),
    gui_mode: bool = typer.Option(
        False, "--gui-mode",
        help="Suppress Rich console output; emit structured JSON events to stdout",
    ),
) -> None:
    """Open the review dashboard for flagged items.

    In normal mode: runs an interactive TUI for the site director to
    accept, correct, or defer flagged items.

    In --gui-mode: emits each flagged item as a JSON event to stdout
    for consumption by desktop GUI tools (Trowel). Use --apply-decisions
    to write corrections back after GUI-side review.
    """
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
        console.print("  Initialise it first with: [bold]hoard init --name '...' --project {project}[/]")
        raise typer.Exit(1)

    from hoard.review import ReviewItem, ReviewSession

    session = ReviewSession(cfg)
    session.load()

    if session.total == 0:
        if gui_mode:
            # Emit empty review event so Trowel knows there's nothing to do
            print('{"event": "review_start", "total": 0}')
            print('{"event": "review_complete", "accepted": 0, "corrected": 0, "deferred": 0, "pending": 0}')
        else:
            console.print(f"[yellow]ℹ[/] No flagged items found for project '{project}'.")
            console.print("  Run [bold]hoard run --project {project} --phase 0[/] first to generate a manifest.")
        return

    if gui_mode:
        _run_review_gui_mode(session)
    else:
        session.run_interactive()


def _run_review_gui_mode(session: Any) -> None:
    """Emit review items as JSON events to stdout for GUI tools."""
    from hoard.review import ReviewDecision

    print(f'{{"event": "review_start", "total": {session.total}}}')

    for item in session.items:
        print(json.dumps({
            "event": "review_item",
            "item_id": item.item_id,
            "phase": item.phase,
            "source": item.source.value,
            "source_file": item.source_file,
            "field": item.field,
            "issue": item.issue,
            "confidence": item.confidence,
            "current_value": item.current_value,
            "corrected_value": item.corrected_value,
            "decision": item.decision.value,
            "notes": item.notes,
        }, default=str))

    # Tally current state
    accepted = sum(1 for i in session.items if i.decision == ReviewDecision.ACCEPTED)
    corrected = sum(1 for i in session.items if i.decision == ReviewDecision.CORRECTED)
    deferred = sum(1 for i in session.items if i.decision == ReviewDecision.DEFERRED)
    pending = sum(1 for i in session.items if i.decision == ReviewDecision.PENDING)

    print(json.dumps({
        "event": "review_complete",
        "accepted": accepted,
        "corrected": corrected,
        "deferred": deferred,
        "pending": pending,
    }))

    # Emit the workspace path so Trowel can write decisions back directly
    print(json.dumps({
        "event": "review_workspace",
        "project_dir": str(session.ws.path),
        "manifest_dir": str(session.config.manifest_dir),
        "digitised_dir": str(session.config.digitised_dir),
        "spatial_dir": str(session.config.spatial_dir),
        "draft_dir": str(session.config.draft_dir),
        "refined_dir": str(session.config.refined_dir),
    }))


@app.command()
def export(
    project: str = typer.Option(..., "--project", "-p", help="Project ID"),
    fmt: str = typer.Option(
        "docx,pdf", "--format", "-f",
        help="Output formats (comma-separated: docx, pdf, tei-xml, zip)",
    ),
    workspace: str = typer.Option(
        "./hoard_workspace", "--workspace", "-w",
        help="Working directory root",
    ),
) -> None:
    """Export final report in specified formats.

    Runs Phase 5 assembly and export for an already-processed project.
    Requires that Phases 0-4 have been completed first.
    """
    workspace_root = Path(workspace).resolve()
    formats = [f.strip() for f in fmt.split(",")]

    from hoard.config import load_config
    cfg = load_config(project, workspace_root)
    if cfg is None:
        console.print(f"[red]✗[/] Project '{project}' not found at {workspace_root / project}")
        console.print("  Initialise it first with: [bold]hoard init --name '...' -j <jurisdiction>[/]")
        raise typer.Exit(1)

    from hoard.phases.phase5 import run_phase5
    console.print(f"[blue]→[/] Running Phase 5 assembly & export for [bold]{project}[/]")
    console.print(f"  Formats: {', '.join(formats)}")

    result = run_phase5(cfg, formats=formats)
    export_paths = result.get("export_paths", {})

    if export_paths:
        console.print("[green]✓[/] Export complete")
        for fmt_name, path in export_paths.items():
            console.print(f"  • {fmt_name}: {path}")
    else:
        console.print("[yellow]ℹ[/] No output files generated. Has the pipeline been run?")
        console.print("  Run [bold]hoard run --project {project} --from-phase 0[/] first.")

    if result.get("harris_matrix"):
        console.print(f"\n  Harris Matrix: {result['harris_matrix']}")
    if result.get("appendices_generated"):
        console.print(f"\n  Appendices: {', '.join(result['appendices_generated'])}")


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
        engine = TemplateEngine()
        template = engine.get_extended_template(name)
        if template is None:
            console.print(f"[red]✗[/] Template '[bold]{name}[/]' not found")
            console.print("  Run [bold]hoard templates list[/] to see available templates.")
            raise typer.Exit(1)
        from rich.syntax import Syntax
        from io import StringIO
        buf = StringIO()
        yaml.dump(template, buf, default_flow_style=False, allow_unicode=True)
        syntax = Syntax(buf.getvalue(), "yaml", theme="monokai", line_numbers=True)
        console.print(f"[bold]Template: {name}[/]")
        console.print(syntax)
    elif action == "validate":
        if not file:
            console.print("[red]✗[/] Use --file <path> to specify a template file")
            raise typer.Exit(1)
        file_path = Path(file)
        if not file_path.exists():
            console.print(f"[red]✗[/] File not found: {file}")
            raise typer.Exit(1)
        try:
            raw = yaml.safe_load(file_path.read_text())
        except yaml.YAMLError as e:
            console.print(f"[red]✗[/] YAML parse error: {e}")
            raise typer.Exit(1)
        if not isinstance(raw, dict):
            console.print("[red]✗[/] Template is empty or not a valid YAML dictionary")
            raise typer.Exit(1)
        # Run structural checks via TemplateEngine
        engine = TemplateEngine(template_dir=file_path.parent)
        code = file_path.stem
        report = engine.check_all("", code)
        if report.passed:
            console.print(f"[green]✓[/] Template '[bold]{code}[/]' is valid")
            console.print(f"  Sections defined: {len(raw.get('mandatory_sections', []))}")
        else:
            console.print(f"[yellow]⚠[/] Template '[bold]{code}[/]' has {len(report.errors)} error(s)")
            for f in report.errors:
                console.print(f"  [red]•[/] {f.message}")
            for f in report.warnings:
                console.print(f"  [yellow]•[/] {f.message}")
    else:
        console.print(f"[red]✗[/] Unknown action: {action}. Use: list, show, validate")


def entry_point() -> None:
    """Console-scripts entry point."""
    app()


if __name__ == "__main__":
    app()
