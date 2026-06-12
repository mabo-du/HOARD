"""helpers.py — Shared utilities for phase modules.

Centralises duplicate functions previously copied across phase3.py and phase5.py
(_load_json_safe, _find_json_files) and phase1.py and phase2.py
(_evict_ollama_model).

exports: _load_json_safe, _find_json_files, _evict_ollama_model
used_by: hoard.phases.phase1, phase2, phase3, phase5
rules:   Must never import torch or any GPU-bound library.
"""

from __future__ import annotations

import gc
import json
import logging
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
