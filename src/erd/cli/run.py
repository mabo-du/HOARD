"""run.py — Pipeline orchestrator.

Invokes phases in sequence, managing pipeline state and error handling.
Each phase is loaded and cleared before the next begins.

exports: run_pipeline(config), run_single_phase(config, phase)
used_by: erd.cli.main  → `erd run` command
rules:   Check PipelineState before running any phase. Skip completed
         phases unless --rerun-phase is set. Never load two models
         into VRAM simultaneously.
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Initial scaffold
"""

from __future__ import annotations


from rich.console import Console

from erd.config import Config
from erd.phases.phase0 import run_phase0
from erd.phases.phase5 import run_phase5
from erd.workspace import Workspace

console = Console()


def run_pipeline(config: Config) -> None:
    """Run all phases sequentially, respecting pipeline state."""
    ws = Workspace(config.project_dir)
    ws.ensure_dirs()

    # Phase 0
    if not ws.state.is_phase_complete(0):
        console.print("[blue]→[/] Phase 0: Ingestion & Triage")
        manifest = run_phase0(config)
        if manifest.get("halt"):
            console.print("[red]✗[/] Pipeline halted by Phase 0 checks.")
            _print_halt_reasons(manifest)
            ws.state.fail_phase(0, "Halt conditions triggered")
            return
        ws.state.complete_phase(0, f"{len(manifest['files'])} files processed")
        console.print(f"[green]✓[/] Phase 0 complete — {len(manifest['files'])} files, "
                      f"{manifest.get('quality_warnings', 0)} quality warnings")
    else:
        console.print("[dim]Phase 0: already complete (skipping)[/]")

    # Phase 1-4 (GPU-dependent)
    for ph, name in [(1, "Multi-Modal Digitisation"),
                     (2, "Spatial Reconstruction"),
                     (3, "Synthesis & Drafting"),
                     (4, "Compliance Refinement")]:
        if not ws.state.is_phase_complete(ph):
            console.print(f"[yellow]ℹ[/] Phase {ph} ({name}): not yet implemented")
            console.print("  Requires GPU — will be available after model training completes.")
            break
        else:
            console.print(f"[dim]Phase {ph}: already complete (skipping)[/]")

    # Phase 5 (rule-based, available now)
    if not ws.state.is_phase_complete(5):
        console.print("[blue]→[/] Phase 5: Assembly & Export")
        result = run_phase5(config)
        ws.state.complete_phase(5, f"Report exported: {result.get('export_paths', {}).get('docx', 'N/A')}")
        console.print("[green]✓[/] Phase 5 complete.")
        for fmt, path in result.get("export_paths", {}).items():
            console.print(f"  {fmt}: {path}")
    else:
        console.print("[dim]Phase 5: already complete (skipping)[/]")


def run_single_phase(config: Config, phase: int) -> None:
    """Run exactly one phase."""
    ws = Workspace(config.project_dir)
    ws.ensure_dirs()

    phases = {
        0: ("Ingestion & Triage", lambda: run_phase0(config)),
        5: ("Assembly & Export", lambda: run_phase5(config)),
    }

    if phase not in phases:
        console.print(f"[yellow]ℹ[/] Phase {phase} is not yet implemented.")
        if phase in (1, 2, 3, 4):
            console.print("  Requires GPU — check back after model training (~24h).")
        return

    name, fn = phases[phase]
    console.print(f"[blue]→[/] Phase {phase}: {name}")
    result = fn()

    if isinstance(result, dict) and result.get("halt"):
        console.print("[red]✗[/] Pipeline halted by Phase 0 checks.")
        _print_halt_reasons(result)
        ws.state.fail_phase(phase, "Halt conditions triggered")
        return

    ws.state.complete_phase(phase, f"Phase {phase} run complete")
    console.print(f"[green]✓[/] Phase {phase} complete.")


def _print_halt_reasons(manifest: dict) -> None:
    """Print human-readable halt reasons."""
    missing = manifest.get("missing_mandatory", [])
    if missing:
        console.print(f"  [red]Missing mandatory types:[/] {', '.join(missing)}")

    files = manifest.get("files", [])
    context_sheets = [f for f in files if f.get("type") == "context_sheet"]
    flagged = [f for f in context_sheets if f.get("quality", {}).get("flag")]
    if flagged and len(context_sheets) > 0:
        pct = len(flagged) / len(context_sheets) * 100
        console.print(f"  [red]{pct:.0f}% of context sheets flagged (threshold: 30%)[/]")

    issues = manifest.get("finds_validation_issues", [])
    if issues:
        console.print(f"  [red]{len(issues)} finds catalogue validation issue(s)[/]")
