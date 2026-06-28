"""test_review_dashboard.py — Unit tests for the review dashboard.

Tests: ReviewItem creation, flag loading from manifests, review session
       actions (accept/edit/defer), correction saving.

exports: (test functions)
used_by: pytest
rules:   Must not require GPU or real pipeline output.
         All tests use synthetic JSON fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hoard.config import Config
from hoard.review import (
    FlagSource,
    ReviewDecision,
    ReviewItem,
    ReviewSession,
    load_flags_from_manifest,
    load_flags_from_workspace,
)
from hoard.workspace import Workspace


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def manifest_with_flags() -> dict:
    return {
        "project_id": "test_site_2026",
        "created": "2026-05-11T12:00:00Z",
        "files": [
            {
                "id": "ctx_001",
                "path": "assets/context_sheet_001.png",
                "type": "context_sheet",
                "quality": {"blur_score": 31.1, "skew_deg": 1.2, "exposure_mean": 178, "flag": "BLUR_LOW"},
            },
            {
                "id": "ctx_002",
                "path": "assets/context_sheet_002.png",
                "type": "context_sheet",
                "quality": {"blur_score": 142.3, "skew_deg": 18.5, "exposure_mean": 180, "flag": "SKEW_HIGH"},
            },
            {
                "id": "photo_001",
                "path": "assets/site_photo_001.png",
                "type": "site_photo",
                "quality": {"blur_score": 95.0, "skew_deg": 0.5, "exposure_mean": 35, "flag": "EXPOSURE_LOW"},
            },
            {
                "id": "ctx_003",
                "path": "assets/context_sheet_003.png",
                "type": "context_sheet",
                "quality": {"blur_score": 150.0, "skew_deg": 0.3, "exposure_mean": 180, "flag": None},
            },
        ],
        "mandatory_check": "PASS",
        "quality_warnings": 3,
    }


@pytest.fixture
def manifest_with_validation_issues() -> dict:
    return {
        "project_id": "test_site_2026",
        "created": "2026-05-11T12:00:00Z",
        "files": [],
        "mandatory_check": "FAIL",
        "missing_mandatory": ["finds_catalogue", "context_sheets"],
        "finds_validation_issues": [
            {"field": "period", "message": "Column 'period' not found", "value": "missing column"},
        ],
        "quality_warnings": 0,
    }


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Config:
    """Create a temporary workspace with a minimal project structure."""
    cfg = Config(
        project_id="test_site_2026",
        project_name="Test Site 2026",
        jurisdiction="historic_england_cl3",
        workspace_root=tmp_path,
        input_dir=tmp_path / "input",
    )
    cfg.project_dir.mkdir(parents=True, exist_ok=True)
    (cfg.manifest_dir).mkdir(parents=True, exist_ok=True)
    (cfg.digitised_dir).mkdir(parents=True, exist_ok=True)
    return cfg


# ── Tests: ReviewItem ────────────────────────────────────────────────────────


class TestReviewItem:
    def test_create_item(self) -> None:
        item = ReviewItem(
            item_id="p0_ctx_001_BLUR_LOW",
            phase=0,
            source=FlagSource.PHASE0_MANIFEST,
            source_file="ctx_001.png",
            field="_quality",
            issue="Blur score 31.1",
            confidence=None,
            current_value="BLUR_LOW",
        )
        assert item.item_id == "p0_ctx_001_BLUR_LOW"
        assert item.phase == 0
        assert item.decision == ReviewDecision.PENDING
        assert item.corrected_value is None

    def test_to_dict(self) -> None:
        item = ReviewItem(
            item_id="p0_test",
            phase=0,
            source=FlagSource.PHASE0_MANIFEST,
            source_file="test.png",
            field="_quality",
            issue="Test",
            confidence=0.5,
            current_value="FLAG",
        )
        d = item.to_dict()
        assert d["item_id"] == "p0_test"
        assert d["phase"] == 0
        assert d["decision"] == "pending"

    def test_accept_correct_defer(self) -> None:
        item = ReviewItem(
            item_id="p0_test",
            phase=0,
            source=FlagSource.PHASE0_MANIFEST,
            source_file="test.png",
            field="test",
            issue="Test issue",
            confidence=None,
            current_value="old_value",
        )
        # Accept
        item.decision = ReviewDecision.ACCEPTED
        assert item.decision == ReviewDecision.ACCEPTED

        # Correct
        item.decision = ReviewDecision.CORRECTED
        item.corrected_value = "new_value"
        assert item.corrected_value == "new_value"

        # Defer
        item.decision = ReviewDecision.DEFERRED
        item.notes = "Will check later"
        assert item.notes == "Will check later"


# ── Tests: Flag Loading ──────────────────────────────────────────────────────


class TestLoadFlagsFromManifest:
    def test_load_quality_flags(self, manifest_with_flags: dict) -> None:
        items = load_flags_from_manifest(manifest_with_flags)  # type: ignore[arg-type]
        assert len(items) == 3  # Three files with flags
        assert all(i.phase == 0 for i in items)

        # Check specific flags
        ids = {i.item_id for i in items}
        assert "p0_ctx_001_BLUR_LOW" in ids
        assert "p0_ctx_002_SKEW_HIGH" in ids
        assert "p0_photo_001_EXPOSURE_LOW" in ids

    def test_no_quality_flags(self) -> None:
        clean = {
            "files": [
                {"id": "ctx_001", "quality": {"flag": None, "blur_score": 150}},
                {"id": "ctx_002", "quality": {"flag": None, "blur_score": 200}},
            ],
        }
        items = load_flags_from_manifest(clean)  # type: ignore[arg-type]
        assert len(items) == 0

    def test_validation_issues(self, manifest_with_validation_issues: dict) -> None:
        items = load_flags_from_manifest(manifest_with_validation_issues)  # type: ignore[arg-type]
        # Should have mandatory check failure + 1 finds issue
        assert len(items) == 2
        ids = {i.item_id for i in items}
        assert "p0_mandatory_check" in ids
        assert "p0_finds_0" in ids

    def test_empty_manifest(self) -> None:
        items = load_flags_from_manifest({})  # type: ignore[arg-type]
        assert len(items) == 0

    def test_missing_file(self, tmp_path: Path) -> None:
        items = load_flags_from_manifest(tmp_path / "nonexistent.json")
        assert len(items) == 0


class TestLoadFlagsFromWorkspace:
    def test_empty_workspace(self, temp_workspace: Config) -> None:
        ws = Workspace(temp_workspace.project_dir)
        items = load_flags_from_workspace(ws, temp_workspace)
        assert len(items) == 0

    def test_with_manifest(self, temp_workspace: Config, manifest_with_flags: dict) -> None:
        # Write manifest to workspace
        manifest_path = temp_workspace.manifest_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_with_flags))
        ws = Workspace(temp_workspace.project_dir)
        items = load_flags_from_workspace(ws, temp_workspace)
        assert len(items) == 3  # Three quality flags


# ── Tests: ReviewSession ─────────────────────────────────────────────────────


class TestReviewSession:
    def test_empty_session(self, temp_workspace: Config) -> None:
        session = ReviewSession(temp_workspace)
        session.load()
        assert session.total == 0
        assert session.remaining == 0
        assert session.current is None

    def test_session_with_flags(self, temp_workspace: Config, manifest_with_flags: dict) -> None:
        # Write manifest
        (temp_workspace.manifest_dir / "manifest.json").write_text(json.dumps(manifest_with_flags))
        session = ReviewSession(temp_workspace)
        session.load()
        assert session.total == 3

    def test_accept_advance(self, temp_workspace: Config, manifest_with_flags: dict) -> None:
        (temp_workspace.manifest_dir / "manifest.json").write_text(json.dumps(manifest_with_flags))
        session = ReviewSession(temp_workspace)
        session.load()

        assert session.current is not None
        first_id = session.current.item_id

        # Accept and advance
        session.accept_current()
        assert session.current.decision == ReviewDecision.ACCEPTED

        session.advance()
        assert session.current is not None
        assert session.current.item_id != first_id

    def test_correct_and_save(self, temp_workspace: Config) -> None:
        # Create a digitised JSON with a reviewable field flag
        dig_json = {
            "source_file": "ctx_001",
            "model": "chandra-ocr-2",
            "confidence_overall": 0.87,
            "context_number": "[374]",
            "type": "layer",
            "description": "Mid brown silty clay",
            "review_flags": [
                {"field": "description", "issue": "LOW_CONFIDENCE", "confidence": 0.61},
            ],
        }
        (temp_workspace.digitised_dir / "ctx_001.json").write_text(json.dumps(dig_json))

        session = ReviewSession(temp_workspace)
        session.load()

        if session.current:
            session.correct_current("Dark brown silty clay with flint")
            written = session.save_corrections()
            assert written == 1
            # Verify the file was updated
            updated = json.loads((temp_workspace.digitised_dir / "ctx_001.json").read_text())
            assert updated["description"] == "Dark brown silty clay with flint"

    def test_defer_and_count_pending(self, temp_workspace: Config, manifest_with_flags: dict) -> None:
        (temp_workspace.manifest_dir / "manifest.json").write_text(json.dumps(manifest_with_flags))
        session = ReviewSession(temp_workspace)
        session.load()

        assert session.remaining == 3
        session.defer_current("Need to check original form")
        assert session.current is not None
        assert session.current.decision == ReviewDecision.DEFERRED
        assert session.remaining == 2  # One deferred


# ── Tests: _update_compliance_finding ──────────────────────────────────────────────


class TestUpdateComplianceFinding:
    """Unit tests for _update_compliance_finding."""

    def _data(self) -> dict:
        return {
            "findings": [
                {
                    "section_id": "methodology",
                    "type": "missing_section",
                    "message": "Section 'methodology' not found in Phase 3 draft",
                    "severity": "error",
                },
                {
                    "section_id": "executive_summary",
                    "type": "prohibited_term",
                    "message": "Prohibited term 'dig' found",
                    "severity": "warning",
                },
            ]
        }

    def test_updates_matching_finding(self) -> None:
        from hoard.review.dashboard import _update_compliance_finding

        data = self._data()
        _update_compliance_finding(data, "methodology:missing_section", "Corrected note")
        finding = next(f for f in data["findings"] if f["section_id"] == "methodology")
        assert finding["message"] == "Corrected note"

    def test_does_not_touch_other_findings(self) -> None:
        from hoard.review.dashboard import _update_compliance_finding

        data = self._data()
        original_msg = data["findings"][1]["message"]
        _update_compliance_finding(data, "methodology:missing_section", "Corrected note")
        assert data["findings"][1]["message"] == original_msg

    def test_updates_all_matches_for_same_type(self) -> None:
        """Multiple prohibited_term findings for the same section should all update."""
        from hoard.review.dashboard import _update_compliance_finding

        data = {
            "findings": [
                {"section_id": "methodology", "type": "prohibited_term",
                 "message": "Term 'dig'", "severity": "warning"},
                {"section_id": "methodology", "type": "prohibited_term",
                 "message": "Term 'trench'", "severity": "warning"},
            ]
        }
        _update_compliance_finding(data, "methodology:prohibited_term", "Reviewed — acceptable")
        assert all(
            f["message"] == "Reviewed — acceptable" for f in data["findings"]
        )

    def test_no_match_does_not_raise(self) -> None:
        from hoard.review.dashboard import _update_compliance_finding

        data = self._data()
        # Should not raise, only log a warning
        _update_compliance_finding(data, "nonexistent:type", "value")
        # findings unchanged
        assert len(data["findings"]) == 2

    def test_missing_colon_is_noop(self) -> None:
        from hoard.review.dashboard import _update_compliance_finding

        data = self._data()
        original = json.dumps(data)
        _update_compliance_finding(data, "no_colon_here", "value")
        assert json.dumps(data) == original


# ── Tests: Phase 4 compliance correction round-trip ───────────────────────────


class TestComplianceCorrectionRoundtrip:
    """Integration tests: Phase 4 compliance finding → scan → correct → save.

    These tests exercise the full path from a compliance_*.json file on disk
    through _scan_compliance_json → ReviewSession → save_corrections() → file.
    They would have silently written nothing with the old _update_nested_field
    path (regression guard).
    """

    @pytest.fixture
    def workspace_with_compliance(self, tmp_path: Path) -> Config:
        cfg = Config(
            project_id="test_site_2026",
            project_name="Test Site 2026",
            jurisdiction="historic_england_cl3",
            workspace_root=tmp_path,
            input_dir=tmp_path / "input",
        )
        cfg.project_dir.mkdir(parents=True, exist_ok=True)
        cfg.manifest_dir.mkdir(parents=True, exist_ok=True)
        cfg.digitised_dir.mkdir(parents=True, exist_ok=True)
        cfg.refined_dir.mkdir(parents=True, exist_ok=True)
        return cfg

    def _write_compliance_json(self, cfg: Config, filename: str, findings: list) -> Path:
        path = cfg.refined_dir / filename
        path.write_text(json.dumps({"findings": findings}, indent=2))
        return path

    def test_missing_section_correction_round_trips(self, workspace_with_compliance: Config) -> None:
        """Correcting a missing_section finding updates the JSON on disk."""
        cfg = workspace_with_compliance
        compliance_path = self._write_compliance_json(
            cfg,
            "compliance_20260628_120000.json",
            [
                {
                    "section_id": "methodology",
                    "type": "missing_section",
                    "message": "Section 'methodology' not found in Phase 3 draft",
                    "severity": "error",
                },
            ],
        )

        session = ReviewSession(cfg)
        session.load()

        # Exactly one Phase 4 finding should be loaded
        assert session.total == 1
        item = session.current
        assert item is not None
        assert item.phase == 4
        assert item.field == "methodology:missing_section"
        assert item.source_file == "compliance_20260628_120000.json"

        # Correct it
        session.correct_current("Methodology section supplied via ARK import")
        written = session.save_corrections()

        # save_corrections() must report it was written
        assert written == 1

        # The file on disk must reflect the correction
        updated = json.loads(compliance_path.read_text())
        methodology = next(
            f for f in updated["findings"]
            if f["section_id"] == "methodology" and f["type"] == "missing_section"
        )
        assert methodology["message"] == "Methodology section supplied via ARK import"

    def test_prohibited_term_correction_round_trips(self, workspace_with_compliance: Config) -> None:
        """Correcting a prohibited_term finding updates the JSON on disk."""
        cfg = workspace_with_compliance
        compliance_path = self._write_compliance_json(
            cfg,
            "compliance_20260628_130000.json",
            [
                {
                    "section_id": "executive_summary",
                    "type": "prohibited_term",
                    "message": "Prohibited term 'dig' found: ...we dug a trench...",
                    "severity": "warning",
                },
                {
                    "section_id": "methodology",
                    "type": "missing_section",
                    "message": "Section 'methodology' not found",
                    "severity": "error",
                },
            ],
        )

        session = ReviewSession(cfg)
        session.load()
        assert session.total == 2

        # Find and correct only the prohibited_term item
        prohibited = next(
            i for i in session.items if i.field == "executive_summary:prohibited_term"
        )
        prohibited.decision = ReviewDecision.CORRECTED
        prohibited.corrected_value = "Reviewed: term acceptable in context"

        written = session.save_corrections()
        assert written == 1

        updated = json.loads(compliance_path.read_text())
        exec_finding = next(
            f for f in updated["findings"]
            if f["section_id"] == "executive_summary" and f["type"] == "prohibited_term"
        )
        methodology_finding = next(
            f for f in updated["findings"]
            if f["section_id"] == "methodology"
        )
        # Corrected finding updated
        assert exec_finding["message"] == "Reviewed: term acceptable in context"
        # Non-corrected finding untouched
        assert methodology_finding["message"] == "Section 'methodology' not found"

    def test_old_nested_field_path_would_have_silently_failed(self) -> None:
        """Regression guard: _update_nested_field writes nothing for compliance JSON.

        The compliance JSON is {"findings": [...]}, not a nested dict.
        _update_nested_field(data, "methodology:missing_section", value) would
        try data.get("methodology", {}) → {} → write to a dead-end temp dict.
        Confirms _update_compliance_finding is the correct path.
        """
        from hoard.review.dashboard import _update_nested_field

        data = {
            "findings": [
                {
                    "section_id": "methodology",
                    "type": "missing_section",
                    "message": "original message",
                    "severity": "error",
                }
            ]
        }
        original_message = data["findings"][0]["message"]
        # This is what the old code did — it should have no effect on the finding
        _update_nested_field(data, "methodology:missing_section", "corrected")
        assert data["findings"][0]["message"] == original_message, (
            "_update_nested_field must not reach into the findings list — "
            "if this assertion fails the regression is back"
        )




# ── Tests: CLI integration ───────────────────────────────────────────────────


def test_cli_help_invocation() -> None:
    """Verify the review command appears in CLI help."""
    from typer.testing import CliRunner
    from hoard.cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["review", "--help"])
    assert result.exit_code == 0
    assert "Open the review dashboard" in result.output
    # Rich ANSI formatting may split --project across escape codes
    assert "-project" in result.output
