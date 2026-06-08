"""hardware.py — Hardware detection and offline model tier system.

Auto-detects GPU/VRAM availability, probes Ollama for installed models,
and maps results to a predefined execution tier. The tier system is
designed so every user gets a working configuration regardless of hardware.

exports: HardwareProfile, ModelTier, detect_hardware, suggest_tier
used_by: hoard.providers.router, hoard.cli.init
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ModelTier(str, Enum):
    """Execution tier dictating which models are used for each phase."""

    ULTRA_LIGHT = "ultra_light"  # No GPU — cloud-only or fallback to minimal CPU
    BUDGET = "budget"  # ~6 GB VRAM — current HOARD baseline
    STANDARD = "standard"  # 8-12 GB VRAM — larger vision models
    PERFORMANCE = "performance"  # 16-24 GB VRAM — high-end local models


# Tier definitions: phase -> (model_name, vram_gb, provider_type)
# Used by the router to construct default provider chains.

TIER_DEFINITIONS: dict[ModelTier, dict[int, dict[str, Any]]] = {
    ModelTier.ULTRA_LIGHT: {
        1: {"model": "gemini-2.5-flash-lite", "provider": "google", "vram_gb": 0},
        2: {"model": "gemini-2.5-flash", "provider": "google", "vram_gb": 0},
        3: {"model": "claude-sonnet-4-20250514", "provider": "anthropic", "vram_gb": 0},
        4: {"model": "gemini-2.5-flash-lite", "provider": "google", "vram_gb": 0},
    },
    ModelTier.BUDGET: {
        1: {"model": "glm-ocr:latest", "provider": "ollama", "vram_gb": 2.2},
        2: {"model": "qwen3-vl:4b", "provider": "ollama", "vram_gb": 2.8},
        3: {"model": "qwen3.5-4b", "provider": "ollama", "vram_gb": 2.8},
        4: {"model": "gemma4:latest", "provider": "ollama", "vram_gb": 2.1},
    },
    ModelTier.STANDARD: {
        1: {"model": "glm-ocr:latest", "provider": "ollama", "vram_gb": 2.2},
        2: {"model": "qwen3-vl:8b", "provider": "ollama", "vram_gb": 5.5},
        3: {"model": "qwen3.5-4b", "provider": "ollama", "vram_gb": 2.8},
        4: {"model": "gemma4:latest", "provider": "ollama", "vram_gb": 2.1},
    },
    ModelTier.PERFORMANCE: {
        1: {"model": "nuextract3", "provider": "ollama", "vram_gb": 4.5},
        2: {"model": "paligemma2:latest", "provider": "ollama", "vram_gb": 8.0},
        3: {"model": "qwen3:8b", "provider": "ollama", "vram_gb": 5.5},
        4: {"model": "gemma4:9b", "provider": "ollama", "vram_gb": 5.5},
    },
}


@dataclass
class HardwareProfile:
    """Detected hardware capabilities for the current machine."""

    gpu_present: bool = False
    gpu_name: str = ""
    vram_total_mb: int = 0
    vram_free_mb: int = 0
    ollama_available: bool = False
    ollama_models: list[str] = field(default_factory=list)
    network_available: bool = False
    cpu_cores: int = 0
    ram_gb: float = 0.0

    @property
    def vram_free_gb(self) -> float:
        return round(self.vram_free_mb / 1024, 1) if self.vram_free_mb > 0 else 0.0


def detect_hardware() -> HardwareProfile:
    """Probe the system for GPU, VRAM, Ollama, and network availability.

    Returns a HardwareProfile populated with detected values. All detection
    is best-effort — failures return sensible defaults (no GPU, no Ollama).
    """
    profile = HardwareProfile()
    _detect_gpu(profile)
    _detect_ollama(profile)
    _detect_network(profile)
    _detect_cpu_ram(profile)
    return profile


def suggest_tier(profile: HardwareProfile) -> tuple[ModelTier, str]:
    """Suggest the best model tier based on detected hardware.

    Returns:
        Tuple of (tier, explanation_string).
    """
    if not profile.gpu_present or profile.vram_free_gb < 4:
        if profile.network_available:
            return (
                ModelTier.ULTRA_LIGHT,
                "No GPU detected; cloud providers configured (requires API keys)",
            )
        else:
            return (
                ModelTier.BUDGET,
                "No GPU and no network — fallback to minimal local models",
            )

    if profile.vram_free_gb >= 14:
        return (ModelTier.PERFORMANCE, f"High VRAM ({profile.vram_free_gb} GB free) — performance tier")
    elif profile.vram_free_gb >= 6:
        return (ModelTier.STANDARD, f"Adequate VRAM ({profile.vram_free_gb} GB free) — standard tier")
    else:
        return (ModelTier.BUDGET, f"Limited VRAM ({profile.vram_free_gb} GB free) — budget tier")


def format_tier_summary(profile: HardwareProfile, tier: ModelTier) -> str:
    """Format a human-readable hardware summary for display during hoard init."""
    lines = [
        "Detected Hardware:",
        f"  GPU: {profile.gpu_name or 'None detected'} "
        f"({'~' + str(profile.vram_total_mb // 1024) + ' GB' if profile.vram_total_mb else ''})",
        f"  CPU: {profile.cpu_cores} cores",
        f"  RAM: {profile.ram_gb:.0f} GB",
        f"  Ollama: {'Available' if profile.ollama_available else 'Not found'}",
        f"  Network: {'Online' if profile.network_available else 'Offline'}",
        "",
        f"Recommended Tier: {tier.value}",
    ]
    return "\n".join(lines)


# ── Internal detection helpers ───────────────────────────────────────────────


def _detect_gpu(profile: HardwareProfile) -> None:
    """Detect NVIDIA GPU and VRAM via nvidia-smi."""
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return

    import subprocess
    try:
        result = subprocess.run(
            [nvidia_smi, "--query-gpu=name,memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return

        line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            profile.gpu_name = parts[0]
            profile.vram_total_mb = int(parts[1])
            profile.vram_free_mb = int(parts[2])
            profile.gpu_present = True
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass


def _detect_ollama(profile: HardwareProfile) -> None:
    """Detect Ollama availability and installed models."""
    import subprocess
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            profile.ollama_available = True
            # Parse model names from output (skip header line)
            for line in result.stdout.strip().split("\n")[1:]:
                if line.strip():
                    name = line.split()[0]
                    profile.ollama_models.append(name)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _detect_network(profile: HardwareProfile) -> None:
    """Check basic internet connectivity."""
    import subprocess
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "3", "8.8.8.8"],
            capture_output=True, text=True, timeout=5,
        )
        profile.network_available = result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        pass


def _detect_cpu_ram(profile: HardwareProfile) -> None:
    """Detect CPU core count and total RAM."""
    import os
    profile.cpu_cores = os.cpu_count() or 0

    try:
        import subprocess
        result = subprocess.run(
            ["grep", "MemTotal", "/proc/meminfo"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            kb = int(result.stdout.split()[1])
            profile.ram_gb = round(kb / (1024 * 1024), 1)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        # Fallback: use os.sysconf if available
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            profile.ram_gb = round(pages * page_size / (1024 ** 3), 1)
        except (ValueError, AttributeError):
            profile.ram_gb = 0.0
