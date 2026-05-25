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
from erd.phases.phase1 import run_phase1
from erd.phases.phase2 import run_phase2
from erd.phases.phase3 import run_phase3
from erd.phases.phase4 import run_phase4
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

    # Phase 1 (Multi-Modal Digitisation — GLM-OCR + Docling)
    if not ws.state.is_phase_complete(1):
        console.print("[blue]→[/] Phase 1: Multi-Modal Digitisation")
        try:
            result = run_phase1(config)
            status = result.get("status", "failed")
            processed = result.get("processed", 0)
            failed = result.get("failed", 0)
            total = result.get("total_files", 0)

            if status == "failed":
                console.print(f"[red]✗[/] Phase 1 failed: {result.get('error', 'Unknown error')}")
                ws.state.fail_phase(1, result.get("error", ""))
                return

            console.print(f"[green]✓[/] Phase 1 complete")
            console.print(f"  Processed: {processed} documents ({failed} failed)")
            console.print(f"  Output: {result.get('output_dir', 'N/A')}")
            if failed > 0:
                console.print(f"  [yellow]⚠  {failed} document(s) failed extraction[/]")

            ws.state.complete_phase(1, f"{processed} documents digitised, {failed} failed")

        except RuntimeError as e:
            console.print(f"[red]✗[/] Phase 1 error: {e}")
            console.print("  Ensure Ollama is running: [bold]ollama serve[/]")
            ws.state.fail_phase(1, str(e))
            return
    else:
        console.print("[dim]Phase 1: already complete (skipping)[/]")

    # Phase 2 (Spatial Reconstruction — Florence-2 + Qwen3-VL-4B)
    if not ws.state.is_phase_complete(2):
        console.print("[blue]→[/] Phase 2: Spatial Reconstruction")
        try:
            result = run_phase2(config)
            status = result.get("status", "error")
            processed = result.get("processed", 0)
            failed = result.get("failed", 0)
            svg_count = result.get("svg_generated", 0)

            if status == "failed":
                console.print(f"[red]✗[/] Phase 2 failed: {result.get('error', 'Unknown error')}")
                ws.state.fail_phase(2, result.get("error", ""))
                return
            if status == "skipped":
                console.print("[yellow]ℹ[/] Phase 2: no images in assets/ — skipping")
                ws.state.complete_phase(2, "Skipped — no images found")
            else:
                console.print(f"[green]✓[/] Phase 2 complete")
                console.print(f"  Photos processed: {processed} ({failed} failed)")
                console.print(f"  SVG drawings: {svg_count}")
                console.print(f"  Output: {result.get('output_dir')}")
                ws.state.complete_phase(
                    2,
                    f"{processed} photos, {svg_count} SVG, {failed} failed",
                )

        except RuntimeError as e:
            console.print(f"[red]✗[/] Phase 2 error: {e}")
            console.print("  Ensure Ollama is running: [bold]ollama serve[/]")
            ws.state.fail_phase(2, str(e))
            return
    else:
        console.print("[dim]Phase 2: already complete (skipping)[/]")

    # Phase 3 (Synthesis & Drafting — using Ollama)
    if not ws.state.is_phase_complete(3):
        console.print("[blue]→[/] Phase 3: Synthesis & Drafting")
        try:
            result = run_phase3(config)
            if result.get("status") == "failed":
                console.print(f"[red]✗[/] Phase 3 failed: {result.get('error', 'Unknown error')}")
                ws.state.fail_phase(3, result.get("error", "Unknown error"))
                return

            sections = result.get("sections", {})
            console.print(f"[green]✓[/] Phase 3 complete — {len(sections)} sections generated")
            console.print(f"  Model: {result.get('model')}")
            console.print(f"  Draft: {result.get('draft_path')}")
            console.print(f"  Tokens: {result.get('total_tokens', 0)}")
            console.print(f"  Duration: {result.get('duration_ms', 0) / 1000:.1f}s")

            if result.get("chunked"):
                periods = result.get("chunk_periods", [])
                console.print(f"  [bold]Chunked:[/] {result.get('chunk_count')} periods ({', '.join(periods[:5])}{'...' if len(periods) > 5 else ''})")

            if result.get("reasoning"):
                console.print(f"  Reasoning chain: {result.get('reasoning_path')}")

            triggers = result.get("triggers", [])
            if triggers:
                console.print(f"\n[yellow]⚠  {len(triggers)} review trigger(s) fired:[/]")
                for t in triggers[:5]:
                    console.print(f"  [yellow]•[/] [{t['section']}] {t['issue']}: {t['detail'][:80]}")

            ws.state.complete_phase(3, f"{len(sections)} sections from {result.get('model')}")

        except RuntimeError as e:
            console.print(f"[red]✗[/] Phase 3 error: {e}")
            console.print("  Ensure Ollama is running: [bold]ollama serve[/]")
            ws.state.fail_phase(3, str(e))
            return
    else:
        console.print("[dim]Phase 3: already complete (skipping)[/]")

    # Phase 4 (Compliance Refinement — using Gemma 4 via Ollama)
    if not ws.state.is_phase_complete(4):
        console.print("[blue]→[/] Phase 4: Compliance Refinement")
        try:
            result = run_phase4(config)
            if result.get("status") == "no_draft":
                console.print(f"[yellow]ℹ[/] {result.get('error', 'No draft found')}")
                ws.state.fail_phase(4, "No Phase 3 draft available")
                return

            sections = result.get("sections", {})
            missing = result.get("missing_sections", [])
            placeholders = result.get("placeholder_count", 0)
            prohibited = result.get("prohibited_flags", [])

            console.print(f"[green]✓[/] Phase 4 complete — {len(sections)} sections processed")
            console.print(f"  Template: {result.get('template')} v{result.get('template_version')}")
            console.print(f"  Compliant report: {result.get('compliant_path')}")
            console.print(f"  Duration: {result.get('duration_ms', 0) / 1000:.1f}s")

            if missing:
                console.print(f"\n[yellow]⚠  Missing sections (placeholders inserted):[/]")
                for s in missing:
                    console.print(f"  [yellow]•[/] {s}")

            if prohibited:
                console.print(f"\n[yellow]⚠  {len(prohibited)} prohibited term(s) found:[/]")
                seen_terms = set()
                for flag in prohibited:
                    term = flag["term"]
                    if term not in seen_terms:
                        console.print(f"  [yellow]•[/] '{term}' in section '{flag.get('section', '?')}'")
                        seen_terms.add(term)

            if placeholders:
                console.print(f"\n[yellow]ℹ  {placeholders} placeholder(s) need attention[/]")

            ws.state.complete_phase(4, f"{len(sections)} sections, {len(missing)} missing, {len(prohibited)} prohibited terms")

        except RuntimeError as e:
            console.print(f"[red]✗[/] Phase 4 error: {e}")
            console.print("  Ensure Ollama is running: [bold]ollama serve[/]")
            ws.state.fail_phase(4, str(e))
            return
    else:
        console.print("[dim]Phase 4: already complete (skipping)[/]")

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
        1: ("Multi-Modal Digitisation", lambda: run_phase1(config)),
        2: ("Spatial Reconstruction", lambda: run_phase2(config)),
        3: ("Synthesis & Drafting", lambda: run_phase3(config)),
        4: ("Compliance Refinement", lambda: run_phase4(config)),
        5: ("Assembly & Export", lambda: run_phase5(config)),
    }

    if phase not in phases:
        console.print(f"[yellow]ℹ[/] Phase {phase} is not yet implemented.")
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
