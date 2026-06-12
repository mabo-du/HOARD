"""ollama_stats.py — Ollama API integration for model memory and timing stats.

Queries Ollama's /api/ps endpoint for loaded model VRAM footprints
and /api/generate for detailed inference timing metrics.

exports: get_ollama_model_stats, get_ollama_timing
used_by: hoard.benchmark, hoard.phases (optional profiling)
license: MIT
"""

from __future__ import annotations

from typing import Any

import requests

from hoard.helpers import OLLAMA_BASE_URL as OLLAMA_BASE


def get_ollama_model_stats() -> list[dict[str, Any]]:
    """Query /api/ps to get VRAM usage of currently loaded models.

    Returns list of dicts with model_name, size_vram_mb, and processor_state.
    Empty list if Ollama is not running or no models loaded.
    """
    try:
        resp = requests.get(f"{OLLAMA_BASE}/api/ps", timeout=5)
        resp.raise_for_status()
        data = resp.json()

        stats: list[dict[str, Any]] = []
        for model in data.get("models", []):
            details = model.get("details", {})
            size_vram = model.get("size_vram", 0)
            stats.append({
                "model_name": model.get("name", "unknown"),
                "size_vram_mb": round(size_vram / (1024 * 1024), 1) if size_vram else 0,
                "processor_state": details.get("processor", "unknown"),
                "gpu_layers": details.get("gpu_layers", 0),
            })
        return stats
    except (requests.ConnectionError, requests.Timeout):
        return []
    except Exception:
        return []


def get_ollama_timing(response_json: dict[str, Any]) -> dict[str, Any]:
    """Extract inference timing metrics from an Ollama /api/generate response.

    Returns dict with:
        - total_duration_s: wall clock time
        - load_duration_s: model load from disk to VRAM
        - prompt_eval_s: input token processing time
        - eval_s: output generation time
        - prompt_tokens: input token count
        - eval_tokens: output token count
        - tokens_per_second: output generation speed
    """
    total_ns = response_json.get("total_duration", 0)
    load_ns = response_json.get("load_duration", 0)
    prompt_ns = response_json.get("prompt_eval_duration", 0)
    eval_ns = response_json.get("eval_duration", 0)
    prompt_count = response_json.get("prompt_eval_count", 0)
    eval_count = response_json.get("eval_count", 0)

    tps = 0.0
    if eval_ns > 0 and eval_count > 0:
        tps = eval_count / (eval_ns / 1e9)

    return {
        "total_duration_s": round(total_ns / 1e9, 2),
        "load_duration_s": round(load_ns / 1e9, 2),
        "prompt_eval_s": round(prompt_ns / 1e9, 2),
        "eval_s": round(eval_ns / 1e9, 2),
        "prompt_tokens": prompt_count,
        "eval_tokens": eval_count,
        "tokens_per_second": round(tps, 1),
    }
