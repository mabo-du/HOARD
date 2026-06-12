"""workspace.py — Working directory management for the pipeline.

Creates, validates, and cleans the hoard_workspace/{project_id}/ directory
tree. Handles pipeline_state.json read/write for resumability.

exports: Workspace, PipelineState
used_by: hoard.cli.*, hoard.phases.*
rules:   Every phase must check PipelineState before starting.
         PipelineState is the sole source of truth for what has run.
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Initial scaffold
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class PipelineState:
    """Read/write pipeline_state.json for resumability."""

    PHASES = [0, 1, 2, 3, 4, 5]

    def __init__(self, state_file: Path) -> None:
        self.state_file = state_file
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self.state_file.exists():
            raw = self.state_file.read_text()
            if raw.strip():
                return json.loads(raw)
        return {"project_id": None, "phases": {}}

    def save(self) -> None:
        """Write current state to disk atomically."""
        tmp = self.state_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        tmp.rename(self.state_file)

    def is_phase_complete(self, phase: int) -> bool:
        return str(phase) in self._data.get("phases", {}) and self._data["phases"][str(phase)].get(
            "status"
        ) in ("complete", "skipped")

    def complete_phase(self, phase: int, summary: str = "") -> None:
        self._data.setdefault("phases", {})[str(phase)] = {
            "status": "complete",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
        }
        self.save()

    def fail_phase(self, phase: int, error: str) -> None:
        self._data.setdefault("phases", {})[str(phase)] = {
            "status": "failed",
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "error": error,
        }
        self.save()


class Workspace:
    """Manages the hoard_workspace directory tree for a project."""

    SUBDIRS = [
        "00_manifest",
        "01_digitised",
        "02_spatial",
        "03_draft",
        "04_refined",
        "05_final",
        "assets",
        "logs",
    ]

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.state = PipelineState(project_dir / "pipeline_state.json")

    def ensure_dirs(self) -> None:
        """Create all subdirectories if they don't exist."""
        for sub in self.SUBDIRS:
            (self.project_dir / sub).mkdir(parents=True, exist_ok=True)

    def validate(self) -> list[str]:
        """Return a list of missing subdirectories."""
        missing = []
        for sub in self.SUBDIRS:
            if not (self.project_dir / sub).is_dir():
                missing.append(sub)
        return missing
