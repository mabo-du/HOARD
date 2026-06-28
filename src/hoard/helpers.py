"""helpers.py — Shared utilities for phase modules.

Centralises duplicate functions previously copied across phase3.py and phase5.py
(_load_json_safe, _find_json_files) and phase1.py and phase2.py
(_evict_ollama_model). Also provides generate_via_provider() which routes
inference requests through the provider abstraction (audit logging, cost
tracking, provider selection) instead of raw requests.post() calls.

Also provides the GUI-mode event system (emit, set_gui_mode) used by the
CLI pipeline and phases to emit structured JSON events for desktop GUI tools.

exports: load_json_safe, find_json_files, evict_ollama_model,
         generate_via_provider, emit, set_gui_mode, OLLAMA_BASE_URL
used_by: hoard.phases.*, hoard.cli.run
rules:   Must never import torch or any GPU-bound library.
"""

from __future__ import annotations

import asyncio
import gc
import json
import logging
import re
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ── Ollama endpoint (shared across phases) ─────────────────────────────────

OLLAMA_BASE_URL = "http://localhost:11434"


# ── JSON Utilities ─────────────────────────────────────────────────────────

def load_json_safe(path: Path) -> dict[str, Any]:
    """Load JSON file, returning empty dict if missing or corrupt."""
    try:
        if path.exists() and path.suffix == ".json":
            return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def find_json_files(directory: Path, pattern: str = "*.json") -> list[Path]:
    """Find JSON files in a directory, sorted by name."""
    if not directory.is_dir():
        return []
    return sorted(directory.glob(pattern))


# ── Ollama VRAM Management ────────────────────────────────────────────────

def evict_ollama_model(model_name: str) -> None:
    """Force-unload an Ollama model from VRAM using keep_alive=0."""
    try:
        requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": model_name, "prompt": "", "keep_alive": 0},
            timeout=5,
        )
    except Exception as e:
        logger.warning(f"VRAM eviction failed for '{model_name}': {e}")
    gc.collect()


# ── Provider-Based Inference ──────────────────────────────────────────────
# NOTE: ProviderRouter (providers/router.py) is fully built but deliberately
# NOT wired into the phase call path — stability decision made 28 June 2026,
# not an oversight. Multi-provider wiring is a separate future project.
# Phases call OllamaProvider directly until that work is undertaken.

def generate_via_provider(
    model: str,
    system: str,
    prompt: str,
    phase: int,
    *,
    temperature: float = 0.0,
    images: list[str] | None = None,
    json_format: bool = False,
    response_schema: dict[str, Any] | None = None,
    num_ctx: int | None = None,
    keep_alive: int = 0,
    timeout: int = 120,
) -> dict[str, Any]:
    """Call OllamaProvider directly for inference.

    Builds an InferenceRequest from legacy-style parameters, calls
    OllamaProvider directly (bypassing the ProviderRouter — see note
    above), and returns a dict matching the historical _ollama_generate
    return format.

    Rules:
        max_tokens is the *output length cap* (default 2048), not the
        context window size. Pass num_ctx separately for context window.

    Returns:
        dict with keys: response, model, eval_count, eval_duration,
        and optionally reasoning (if <think> tags detected).
    """
    from hoard.providers.ollama import OllamaProvider
    from hoard.providers.protocol import InferenceRequest

    # Convert legacy system/prompt to chat messages
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # Build provider kwargs for Ollama-specific options
    provider_kwargs: dict[str, Any] = {}
    if num_ctx is not None:
        provider_kwargs["num_ctx"] = num_ctx  # context window size
    if keep_alive:
        provider_kwargs["keep_alive"] = keep_alive

    request = InferenceRequest(
        messages=messages,
        model_name=model,
        temperature=temperature,
        max_tokens=2048,  # output length cap — not the context window
        response_schema=response_schema,
        template_format="json" if json_format else None,
        images=images,
        provider_kwargs=provider_kwargs,
    )

    provider = OllamaProvider(model_name=model)
    response = asyncio.run(provider.generate(request))
    content = response.content

    # Extract reasoning/thinking chain if present (Qwen3.5 thinking mode)
    reasoning = None
    think_match = re.search(
        r"<think>(.*?)</think>", content, re.DOTALL
    )
    if think_match:
        reasoning = think_match.group(1).strip()
        content = re.sub(
            r"<think>.*?</think>\s*", "", content, flags=re.DOTALL
        )

    return {
        "response": content,
        "model": response.model_name,
        "eval_count": response.usage.completion_tokens,
        "eval_duration": 0,
        **({"reasoning": reasoning} if reasoning else {}),
    }


# ── GUI Mode Event System ────────────────────────────────────────────────
# Shared across cli/run.py and phase modules. When enabled, emits structured
# JSON events to stdout for parsing by desktop GUI tools (Trowel).

_gui_mode = False


def set_gui_mode(enabled: bool) -> None:
    """Enable or disable GUI-mode event emission."""
    global _gui_mode
    _gui_mode = enabled


def emit(event_type: str, phase: int | None = None, **data: Any) -> None:
    """Emit a pipeline event.

    In normal mode: prints Rich-formatted console output (imported lazily).
    In gui-mode: prints a JSON line to stdout for Trowel to consume.

    Callable from any phase module for progress events.
    """
    if _gui_mode:
        payload: dict[str, Any] = {"event": event_type}
        if phase is not None:
            payload["phase"] = phase
        payload.update(data)
        print(json.dumps(payload, default=str))
        return

    # Rich-formatted output for normal (terminal) mode
    from rich.console import Console
    console = Console()

    if event_type == "phase_start":
        console.print(f"[blue]→[/] Phase {phase}: {data.get('name', '')}")
    elif event_type == "phase_skip":
        console.print(f"[dim]Phase {phase}: already complete (skipping)[/]")
    elif event_type == "phase_complete":
        console.print(f"[green]✓[/] Phase {phase} complete.")
    elif event_type == "phase_error":
        console.print(f"[red]✗[/] Phase {phase} error: {data.get('error', '')}")
        if "hint" in data:
            console.print(f"  {data['hint']}")
    elif event_type == "pipeline_halt":
        console.print(f"[red]✗[/] {data.get('reason', 'Pipeline halted')}")
    elif event_type == "info":
        msg = data.get("message", "")
        if msg:
            console.print(msg)
