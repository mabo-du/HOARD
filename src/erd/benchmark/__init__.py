"""benchmark — Performance and VRAM profiling for the HOARD pipeline.

Provides thread-safe GPU memory telemetry via pynvml and Ollama API
integration for per-phase profiling.

Modules:
    vram_profiler: VRAMProfiler class with daemon-threaded monitoring.
    ollama_stats:  Ollama /api/ps and /api/generate metrics extraction.

exports: VRAMProfiler, get_ollama_model_stats, get_ollama_timing
used_by: erd.cli, erd.phases
license: MIT
"""

from erd.benchmark.vram_profiler import VRAMProfiler
from erd.benchmark.ollama_stats import get_ollama_model_stats, get_ollama_timing

__all__ = ["VRAMProfiler", "get_ollama_model_stats", "get_ollama_timing"]
