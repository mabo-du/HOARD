"""helpers.py — Shared utilities for phase modules.

Centralises duplicate functions previously copied across phase3.py and phase5.py
(_load_json_safe, _find_json_files) and phase1.py and phase2.py
(_evict_ollama_model). Also provides generate_via_provider() which routes
inference requests through the provider abstraction (audit logging, cost
tracking, provider selection) instead of raw requests.post() calls.

exports: load_json_safe, find_json_files, evict_ollama_model,
         generate_via_provider, OLLAMA_BASE_URL
used_by: hoard.phases.phase1, phase2, phase3, phase4, phase5
rules:   Must never import torch or any GPU-bound library.
"""

from __future__ import annotations

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
    except Exception:
        pass
    gc.collect()


# ── Provider-Based Inference ──────────────────────────────────────────────

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
    """Route an inference request through the provider abstraction.

    Builds an InferenceRequest from legacy-style parameters, calls the
    ProviderRouter (which handles provider selection, fallback, and audit
    logging), and returns a dict matching the historical _ollama_generate
    return format.

    Returns:
        dict with keys: response, model, eval_count, eval_duration,
        and optionally reasoning (if <think> tags detected).
    """
    from hoard.providers import get_router
    from hoard.providers.protocol import InferenceRequest

    # Convert legacy system/prompt to chat messages
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # Build provider kwargs for Ollama-specific options
    provider_kwargs: dict[str, Any] = {}
    if num_ctx is not None:
        provider_kwargs["num_ctx"] = num_ctx
    if keep_alive:
        provider_kwargs["keep_alive"] = keep_alive

    request = InferenceRequest(
        messages=messages,
        model_name=model,
        temperature=temperature,
        max_tokens=num_ctx,
        response_schema=response_schema,
        template_format="json" if json_format else None,
        images=images,
        provider_kwargs=provider_kwargs,
    )

    router = get_router()
    response = router.route_sync(request, phase)

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
