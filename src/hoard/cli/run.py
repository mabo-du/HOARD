"""run.py — Pipeline orchestrator.

Invokes phases in sequence, managing pipeline state and error handling.
Each phase is loaded and cleared before the next begins.

exports: run_pipeline(config), run_single_phase(config, phase)
used_by: hoard.cli.main  → `hoard run` command
rules:   Check PipelineState before running any phase. Skip completed
         phases unless --rerun-phase is set. Never load two models
         into VRAM simultaneously.
         In --gui-mode, emits structured JSON events to stdout for
         parsing by desktop GUI tools (Trowel).
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Initial scaffold
"""

from __future__ import annotations

from typing import Any

from rich.console import Console

from hoard.config import Config
from hoard.helpers import emit, set_gui_mode
from hoard.phases.phase0 import run_phase0
from hoard.phases.phase1 import run_phase1
from hoard.phases.phase2 import run_phase2
from hoard.phases.phase3 import run_phase3
from hoard.phases.phase4 import run_phase4
from hoard.phases.phase5 import run_phase5
from hoard.workspace import Workspace

try:
    from hoard.benchmark import VRAMProfiler, get_ollama_model_stats
    _HAS_PROFILER = True
except ImportError:
    _HAS_PROFILER = False

console = Console()


def run_pipeline(config: Config, benchmark: bool = False, gui_mode: bool = False) -> None:
    """Run all phases sequentially, respecting pipeline state.

    If benchmark=True, wraps each GPU phase with VRAM profiling.
    If gui_mode=True, emits structured JSON events to stdout instead of
    Rich-formatted console output.
    """
    set_gui_mode(gui_mode)

    ws = Workspace(config.project_dir)
    ws.ensure_dirs()

    profiler = VRAMProfiler() if benchmark and _HAS_PROFILER else None

    def _profile_phase(name: str, phase_fn, *args):
        """Run a phase with optional VRAM profiling."""
        if profiler:
            profiler.start()
        result = phase_fn(*args)
        if profiler:
            report = profiler.stop()
            ollama_stats = get_ollama_model_stats() if _HAS_PROFILER else []
            _log_benchmark(config, name, report, ollama_stats, result)
        return result

    # Phase 0
    if not ws.state.is_phase_complete(0):
        emit("phase_start", phase=0, name="Ingestion & Triage")
        manifest = run_phase0(config)
        if manifest.get("halt"):
            emit("pipeline_halt", phase=0, reason="Phase 0 checks failed")
            console.print("[red]✗[/] Pipeline halted by Phase 0 checks.")
            _print_halt_reasons(manifest)
            ws.state.fail_phase(0, "Halt conditions triggered")
            return
        ws.state.complete_phase(0, f"{len(manifest['files'])} files processed")
        emit("phase_complete", phase=0, status="success",
             files=len(manifest["files"]),
             quality_warnings=manifest.get("quality_warnings", 0))
        if manifest.get("quality_warnings", 0) > 0:
            emit("review_required", phase=0,
                 flagged_count=manifest["quality_warnings"],
                 path=str(config.project_dir))
        console.print(f"[green]✓[/] Phase 0 complete — {len(manifest['files'])} files, "
                      f"{manifest.get('quality_warnings', 0)} quality warnings")
    else:
        emit("phase_skip", phase=0, name="Ingestion & Triage")
        console.print("[dim]Phase 0: already complete (skipping)[/]")

    # Phase 1 (Multi-Modal Digitisation — GLM-OCR + Docling)
    if not ws.state.is_phase_complete(1):
        emit("phase_start", phase=1, name="Multi-Modal Digitisation")
        try:
            result = _profile_phase("phase1", run_phase1, config)
            status = result.get("status", "failed")
            processed = result.get("processed", 0)
            failed = result.get("failed", 0)

            if status == "failed":
                emit("phase_error", phase=1, error=result.get("error", "Unknown error"))
                console.print(f"[red]✗[/] Phase 1 failed: {result.get('error', 'Unknown error')}")
                ws.state.fail_phase(1, result.get("error", ""))
                return

            emit("phase_complete", phase=1, status="success",
                 processed=processed, failed=failed)
            if failed > 0:
                emit("review_required", phase=1,
                     flagged_count=failed, path=str(config.project_dir))
            console.print("[green]✓[/] Phase 1 complete")
            console.print(f"  Processed: {processed} documents ({failed} failed)")
            console.print(f"  Output: {result.get('output_dir', 'N/A')}")
            if failed > 0:
                console.print(f"  [yellow]⚠  {failed} document(s) failed extraction[/]")

            ws.state.complete_phase(1, f"{processed} documents digitised, {failed} failed")

        except RuntimeError as e:
            emit("phase_error", phase=1, error=str(e), hint="Ensure Ollama is running")
            console.print(f"[red]✗[/] Phase 1 error: {e}")
            console.print("  Ensure Ollama is running: [bold]ollama serve[/]")
            ws.state.fail_phase(1, str(e))
            return
    else:
        emit("phase_skip", phase=1, name="Multi-Modal Digitisation")
        console.print("[dim]Phase 1: already complete (skipping)[/]")

    # Phase 2 (Spatial Reconstruction — Florence-2 + Qwen3-VL-4B)
    if not ws.state.is_phase_complete(2):
        emit("phase_start", phase=2, name="Spatial Reconstruction")
        try:
            result = _profile_phase("phase2", run_phase2, config)
            status = result.get("status", "error")
            processed = result.get("processed", 0)
            failed = result.get("failed", 0)
            svg_count = result.get("svg_generated", 0)

            if status == "failed":
                emit("phase_error", phase=2, error=result.get("error", "Unknown error"))
                console.print(f"[red]✗[/] Phase 2 failed: {result.get('error', 'Unknown error')}")
                ws.state.fail_phase(2, result.get("error", ""))
                return
            if status == "skipped":
                emit("phase_skip", phase=2, name="Spatial Reconstruction", reason="no images")
                console.print("[yellow]ℹ[/] Phase 2: no images in assets/ — skipping")
                ws.state.complete_phase(2, "Skipped — no images found")
            else:
                emit("phase_complete", phase=2, status="success",
                     processed=processed, failed=failed, svg=svg_count)
                if failed > 0:
                    emit("review_required", phase=2,
                         flagged_count=failed, path=str(config.project_dir))
                console.print("[green]✓[/] Phase 2 complete")
                console.print(f"  Photos processed: {processed} ({failed} failed)")
                console.print(f"  SVG drawings: {svg_count}")
                console.print(f"  Output: {result.get('output_dir')}")
                ws.state.complete_phase(
                    2,
                    f"{processed} photos, {svg_count} SVG, {failed} failed",
                )

        except RuntimeError as e:
            emit("phase_error", phase=2, error=str(e), hint="Ensure Ollama is running")
            console.print(f"[red]✗[/] Phase 2 error: {e}")
            console.print("  Ensure Ollama is running: [bold]ollama serve[/]")
            ws.state.fail_phase(2, str(e))
            return
    else:
        emit("phase_skip", phase=2, name="Spatial Reconstruction")
        console.print("[dim]Phase 2: already complete (skipping)[/]")

    # Phase 3 (Synthesis & Drafting — using Ollama)
    if not ws.state.is_phase_complete(3):
        emit("phase_start", phase=3, name="Synthesis & Drafting")
        try:
            result = _profile_phase("phase3", run_phase3, config)
            if result.get("status") == "failed":
                emit("phase_error", phase=3, error=result.get("error", "Unknown error"))
                console.print(f"[red]✗[/] Phase 3 failed: {result.get('error', 'Unknown error')}")
                ws.state.fail_phase(3, result.get("error", "Unknown error"))
                return

            sections = result.get("sections", {})
            emit("phase_complete", phase=3, status="success",
                 sections=len(sections), model=result.get("model"),
                 tokens=result.get("total_tokens", 0))
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

            if triggers:
                emit("review_required", phase=3,
                     flagged_count=len(triggers), path=str(config.project_dir))

            ws.state.complete_phase(3, f"{len(sections)} sections from {result.get('model')}")

        except RuntimeError as e:
            emit("phase_error", phase=3, error=str(e), hint="Ensure Ollama is running")
            console.print(f"[red]✗[/] Phase 3 error: {e}")
            console.print("  Ensure Ollama is running: [bold]ollama serve[/]")
            ws.state.fail_phase(3, str(e))
            return
    else:
        emit("phase_skip", phase=3, name="Synthesis & Drafting")
        console.print("[dim]Phase 3: already complete (skipping)[/]")

    # Phase 4 (Compliance Refinement — using Gemma 4 via Ollama)
    if not ws.state.is_phase_complete(4):
        emit("phase_start", phase=4, name="Compliance Refinement")
        try:
            result = _profile_phase("phase4", run_phase4, config)
            if result.get("status") == "no_draft":
                emit("phase_error", phase=4, error=result.get("error", "No draft found"))
                console.print(f"[yellow]ℹ[/] {result.get('error', 'No draft found')}")
                ws.state.fail_phase(4, "No Phase 3 draft available")
                return

            sections = result.get("sections", {})
            missing = result.get("missing_sections", [])
            placeholders = result.get("placeholder_count", 0)
            prohibited = result.get("prohibited_flags", [])

            emit("phase_complete", phase=4, status="success",
                 sections=len(sections), missing=len(missing),
                 prohibited=len(prohibited), placeholders=placeholders)
            console.print(f"[green]✓[/] Phase 4 complete — {len(sections)} sections processed")
            console.print(f"  Template: {result.get('template')} v{result.get('template_version')}")
            console.print(f"  Compliant report: {result.get('compliant_path')}")
            console.print(f"  Duration: {result.get('duration_ms', 0) / 1000:.1f}s")

            if missing:
                console.print("\n[yellow]⚠  Missing sections (placeholders inserted):[/]")
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

            flagged_4 = len(prohibited) + placeholders
            if flagged_4 > 0:
                emit("review_required", phase=4,
                     flagged_count=flagged_4, path=str(config.project_dir))

            ws.state.complete_phase(4, f"{len(sections)} sections, {len(missing)} missing, {len(prohibited)} prohibited terms")

        except RuntimeError as e:
            emit("phase_error", phase=4, error=str(e), hint="Ensure Ollama is running")
            console.print(f"[red]✗[/] Phase 4 error: {e}")
            console.print("  Ensure Ollama is running: [bold]ollama serve[/]")
            ws.state.fail_phase(4, str(e))
            return
    else:
        emit("phase_skip", phase=4, name="Compliance Refinement")
        console.print("[dim]Phase 4: already complete (skipping)[/]")

    # Phase 5 (rule-based, available now)
    if not ws.state.is_phase_complete(5):
        emit("phase_start", phase=5, name="Assembly & Export")
        try:
            result = run_phase5(config)
        except RuntimeError as e:
            emit("phase_error", phase=5, error=str(e), hint="Check disk space and write permissions")
            console.print(f"[red]✗[/] Phase 5 failed: {e}")
            console.print("  Check disk space and write permissions.")
            ws.state.fail_phase(5, str(e))
            return
        ws.state.complete_phase(5, f"Report exported: {result.get('export_paths', {}).get('docx', 'N/A')}")
        emit("phase_complete", phase=5, status="success",
             export_paths=result.get("export_paths", {}))
        console.print("[green]✓[/] Phase 5 complete.")
        for fmt, path in result.get("export_paths", {}).items():
            console.print(f"  {fmt}: {path}")
    else:
        emit("phase_skip", phase=5, name="Assembly & Export")
        console.print("[dim]Phase 5: already complete (skipping)[/]")


def run_single_phase(config: Config, phase: int, gui_mode: bool = False) -> None:
    """Run exactly one phase."""
    set_gui_mode(gui_mode)

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
        emit("info", message=f"Phase {phase} is not yet implemented.")
        console.print(f"[yellow]ℹ[/] Phase {phase} is not yet implemented.")
        return

    name, fn = phases[phase]
    emit("phase_start", phase=phase, name=name)
    console.print(f"[blue]→[/] Phase {phase}: {name}")
    try:
        result = fn()
    except RuntimeError as e:
        emit("phase_error", phase=phase, error=str(e))
        console.print(f"[red]✗[/] Phase {phase} failed: {e}")
        ws.state.fail_phase(phase, str(e))
        return
    except Exception as e:
        emit("phase_error", phase=phase, error=str(e))
        console.print(f"[red]✗[/] Phase {phase} failed with unexpected error: {e}")
        ws.state.fail_phase(phase, str(e))
        return

    if isinstance(result, dict) and result.get("halt"):
        emit("pipeline_halt", phase=phase, reason="Phase 0 checks failed")
        console.print("[red]✗[/] Pipeline halted by Phase 0 checks.")
        _print_halt_reasons(result)
        ws.state.fail_phase(phase, "Halt conditions triggered")
        return

    ws.state.complete_phase(phase, f"Phase {phase} run complete")
    emit("phase_complete", phase=phase, status="success")
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
        console.print(f"  [red]{pct:.0f}% of context sheets flagged (threshold: 90%)[/]")

    issues = manifest.get("finds_validation_issues", [])
    if issues:
        console.print(f"  [red]{len(issues)} finds catalogue validation issue(s)[/]")


def _log_benchmark(
    config: Config,
    phase_name: str,
    report: Any,
    ollama_stats: list[dict[str, Any]],
    phase_result: dict[str, Any],
) -> None:
    """Log VRAM benchmark data for a completed phase."""
    import json
    from datetime import datetime, timezone

    benchmark_dir = config.logs_dir / "benchmarks"
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = benchmark_dir / f"{phase_name}_{timestamp}.json"

    log_entry = {
        "phase": phase_name,
        "timestamp": timestamp,
        "vram": {
            "peak_mb": report.peak_vram_mb,
            "avg_mb": report.avg_vram_mb,
            "snapshots": report.snapshot_count,
            "duration_s": report.duration_s,
        },
        "thermal": {
            "peak_gpu_temp_c": report.peak_temp_c,
            "peak_power_w": report.peak_power_w,
        },
        "ollama_models": ollama_stats,
        "phase_result": {
            k: str(v)[:200] for k, v in phase_result.items()
            if k in ("status", "processed", "failed", "duration_ms", "total_tokens", "model")
        },
    }

    log_path.write_text(json.dumps(log_entry, indent=2))

    console.print(
        f"  [dim]📊 VRAM: peak {report.peak_vram_mb:.0f} MB, "
        f"avg {report.avg_vram_mb:.0f} MB, "
        f"temp {report.peak_temp_c}°C[/]"
    )
