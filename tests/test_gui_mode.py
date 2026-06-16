"""test_gui_mode.py — Tests for the GUI-mode event system.

Tests: gui-mode flag behaviour, event schema compliance, JSON output format,
       progress/review_required event payloads, state management (set/clear).
Runtimes: All tests are CPU-only and fast (< 0.5s).
"""

from __future__ import annotations

import json
import sys
from io import StringIO
from typing import Any


from hoard.helpers import emit, set_gui_mode


def capture_emit(event_type: str, **data: Any) -> str:
    """Capture emit output by running in gui-mode and reading stdout."""
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        set_gui_mode(True)
        emit(event_type, **data)
        set_gui_mode(False)
        return sys.stdout.getvalue().strip()
    finally:
        sys.stdout = old_stdout


class TestGuiModeState:
    """Verify that gui-mode toggles correctly."""

    def test_default_off(self) -> None:
        from hoard.helpers import _gui_mode
        assert _gui_mode is False

    def test_toggle_on(self) -> None:
        set_gui_mode(True)
        from hoard.helpers import _gui_mode
        assert _gui_mode is True
        set_gui_mode(False)

    def test_toggle_off(self) -> None:
        set_gui_mode(True)
        set_gui_mode(False)
        from hoard.helpers import _gui_mode
        assert _gui_mode is False


class TestEventSchema:
    """Verify that all event types produce valid JSON with correct fields."""

    def test_phase_start(self) -> None:
        line = capture_emit("phase_start", phase=0, name="Ingestion & Triage")
        payload = json.loads(line)
        assert payload["event"] == "phase_start"
        assert payload["phase"] == 0
        assert payload["name"] == "Ingestion & Triage"

    def test_phase_complete(self) -> None:
        line = capture_emit("phase_complete", phase=1, status="success",
                            processed=15, failed=2)
        payload = json.loads(line)
        assert payload["event"] == "phase_complete"
        assert payload["phase"] == 1
        assert payload["status"] == "success"
        assert payload["processed"] == 15

    def test_phase_error(self) -> None:
        line = capture_emit("phase_error", phase=2, error="Ollama not running",
                            hint="Ensure Ollama is running")
        payload = json.loads(line)
        assert payload["event"] == "phase_error"
        assert payload["phase"] == 2
        assert payload["error"] == "Ollama not running"
        assert "hint" in payload

    def test_phase_skip(self) -> None:
        line = capture_emit("phase_skip", phase=3, name="Synthesis & Drafting")
        payload = json.loads(line)
        assert payload["event"] == "phase_skip"
        assert payload["phase"] == 3

    def test_progress(self) -> None:
        line = capture_emit("progress", phase=1, current=5, total=20,
                            item="ctx_012.jpg")
        payload = json.loads(line)
        assert payload["event"] == "progress"
        assert payload["phase"] == 1
        assert payload["current"] == 5
        assert payload["total"] == 20
        assert payload["item"] == "ctx_012.jpg"

    def test_review_required(self) -> None:
        line = capture_emit("review_required", phase=0, flagged_count=3,
                            path="/tmp/test_project")
        payload = json.loads(line)
        assert payload["event"] == "review_required"
        assert payload["phase"] == 0
        assert payload["flagged_count"] == 3
        assert payload["path"] == "/tmp/test_project"

    def test_pipeline_halt(self) -> None:
        line = capture_emit("pipeline_halt", reason="Missing context sheets")
        payload = json.loads(line)
        assert payload["event"] == "pipeline_halt"
        assert payload["reason"] == "Missing context sheets"

    def test_info(self) -> None:
        line = capture_emit("info", message="Phase 4 complete.")
        payload = json.loads(line)
        assert payload["event"] == "info"
        assert payload["message"] == "Phase 4 complete."

    def test_event_without_phase(self) -> None:
        """Events like pipeline_halt may not carry a phase number."""
        line = capture_emit("pipeline_halt", reason="Fatal error")
        assert "phase" not in json.loads(line)

    def test_progress_positive_current(self) -> None:
        """Progress current must always be >= 1."""
        line = capture_emit("progress", phase=1, current=1, total=10,
                            item="first.jpg")
        payload = json.loads(line)
        assert payload["current"] >= 1

    def test_review_required_nonzero_flagged(self) -> None:
        """flagged_count should be > 0 when review is required."""
        line = capture_emit("review_required", phase=0, flagged_count=1,
                            path="/tmp")
        payload = json.loads(line)
        assert payload["flagged_count"] > 0


class TestNullMode:
    """Verify that normal (non-gui) mode still produces output."""

    def test_phase_start_output(self) -> None:
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            set_gui_mode(False)
            emit("phase_start", phase=0, name="Test Phase")
            output = sys.stdout.getvalue()
            assert "Test Phase" in output or "Phase 0" in output
        finally:
            sys.stdout = old_stdout
