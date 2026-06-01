"""vram_profiler.py — Threaded GPU VRAM monitoring via pynvml.

Provides a daemon-threaded profiler that polls NVIDIA GPU memory,
temperature, and power usage during pipeline execution without
blocking the main inference loop.

export: VRAMProfiler
used_by: hoard.benchmark, hoard.phases (optional --benchmark flag)
rules:   Must handle pynvml not installed gracefully.
         Must be thread-safe for use in multi-phase pipelines.
license: MIT
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

try:
    import pynvml
    _HAS_PYNVML = True
except ImportError:
    _HAS_PYNVML = False


@dataclass
class VramSnapshot:
    """Single telemetry sample captured by the profiler."""
    timestamp_ms: float
    vram_used_mb: float
    vram_total_mb: float
    vram_free_mb: float
    gpu_temp_c: int
    power_w: float


@dataclass
class VramReport:
    """Aggregated telemetry report after monitoring stops."""
    snapshot_count: int = 0
    duration_s: float = 0.0
    peak_vram_mb: float = 0.0
    avg_vram_mb: float = 0.0
    peak_temp_c: int = 0
    peak_power_w: float = 0.0
    snapshots: list[VramSnapshot] = field(default_factory=list)


class VRAMProfiler:
    """Daemon-threaded GPU telemetry profiler.

    Runs a background thread polling pynvml at a configurable rate.
    Call start() before inference, stop() after, then read the report.

    Gracefully handles pynvml import failure (returns zeroed report).
    """

    def __init__(self, device_index: int = 0, poll_rate_s: float = 0.1):
        """Create a profiler for the given GPU device.

        Args:
            device_index: GPU device index (0 for first GPU).
            poll_rate_s: How often to sample (seconds). Default 100ms.
        """
        self._device_index = device_index
        self._poll_rate = poll_rate_s
        self._monitoring = False
        self._thread: threading.Thread | None = None
        self._snapshots: list[VramSnapshot] = []
        self._start_time: float = 0.0
        self._handle: Any = None

    def start(self) -> None:
        """Begin daemon-threaded GPU monitoring."""
        if not _HAS_PYNVML:
            return

        try:
            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(self._device_index)
        except pynvml.NVMLError:
            return  # GPU not available — profiler silently disabled

        self._monitoring = True
        self._snapshots = []
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self) -> VramReport:
        """Stop monitoring and return aggregated telemetry."""
        if self._thread and self._monitoring:
            self._monitoring = False
            self._thread.join(timeout=5.0)

        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass

        if not self._snapshots:
            return VramReport()

        duration = time.time() - self._start_time
        peak_mb = max(s.vram_used_mb for s in self._snapshots)
        avg_mb = sum(s.vram_used_mb for s in self._snapshots) / len(self._snapshots)
        peak_temp = max(s.gpu_temp_c for s in self._snapshots)
        peak_power = max(s.power_w for s in self._snapshots)

        return VramReport(
            snapshot_count=len(self._snapshots),
            duration_s=round(duration, 2),
            peak_vram_mb=round(peak_mb, 1),
            avg_vram_mb=round(avg_mb, 1),
            peak_temp_c=peak_temp,
            peak_power_w=round(peak_power, 2),
            snapshots=self._snapshots,
        )

    def _monitor_loop(self) -> None:
        """Internal: continuously poll GPU telemetry."""
        last_log = time.time()
        while self._monitoring and self._handle is not None:
            try:
                mem = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
                temp = pynvml.nvmlDeviceGetTemperature(
                    self._handle, pynvml.NVML_TEMPERATURE_GPU
                )
                power_mw = pynvml.nvmlDeviceGetPowerUsage(self._handle)

                snapshot = VramSnapshot(
                    timestamp_ms=round((time.time() - self._start_time) * 1000, 1),
                    vram_used_mb=round(mem.used / (1024 * 1024), 1),
                    vram_total_mb=round(mem.total / (1024 * 1024), 1),
                    vram_free_mb=round(mem.free / (1024 * 1024), 1),
                    gpu_temp_c=temp,
                    power_w=power_mw / 1000.0,
                )
                self._snapshots.append(snapshot)
                time.sleep(self._poll_rate)
            except pynvml.NVMLError:
                time.sleep(1.0)  # Back off on error
