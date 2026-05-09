"""test_phase0.py — Unit tests for Phase 0: Ingestion & Triage.

Tests: manifest generation, quality flags, image normalisation,
classification heuristics, CSV validation, mandatory file checks.

exports: (test functions)
used_by: pytest
rules:   Must not require GPU or real model inference.
         Must use synthetic image data, not real photographs.
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Initial scaffold
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from erd.config import Config
from erd.phases.phase0 import (
    FileEntry,
    QualityFlags,
    _assess_quality,
    _classify_image,
    _file_hash,
    _validate_csv_finds,
    _validate_xlsx_finds,
    run_phase0,
)

# ── Helpers ────────────────────────────────────────────────────────────────


def _make_synthetic_png(path: Path, width: int = 100, height: int = 100) -> None:
    """Create a minimal valid PNG file."""
    import struct
    import zlib

    # Minimal PNG: header + IHDR + IDAT + IEND
    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    raw_data = b""
    for y in range(height):
        raw_data += b"\x00"  # filter byte
        for x in range(width):
            raw_data += bytes([x % 256, y % 256, (x + y) % 256])
    idat = _chunk(b"IDAT", zlib.compress(raw_data))
    iend = _chunk(b"IEND", b"")

    path.write_bytes(signature + ihdr + idat + iend)


def _make_synthetic_csv(path: Path, rows: list[list[str]]) -> None:
    import csv
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def _make_synthetic_xlsx(path: Path, headers: list[str], rows: list[list]) -> None:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    wb.save(path)


# ── Quality Flags ──────────────────────────────────────────────────────────


class TestQualityFlags:
    def test_to_dict_empty(self) -> None:
        q = QualityFlags()
        assert q.to_dict() == {}

    def test_to_dict_with_values(self) -> None:
        q = QualityFlags()
        q.blur_score = 50.0
        q.flag = "BLUR_LOW"
        d = q.to_dict()
        assert d["blur_score"] == 50.0
        assert d["flag"] == "BLUR_LOW"

    def test_to_dict_rounds_values(self) -> None:
        q = QualityFlags()
        q.blur_score = 50.567
        d = q.to_dict()
        assert d["blur_score"] == 50.6


# ── File Hash ──────────────────────────────────────────────────────────────


class TestFileHash:
    def test_hash_is_sha256(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"hello world")
            p = Path(f.name)
        try:
            h = _file_hash(p)
            assert h == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
            assert len(h) == 64
        finally:
            p.unlink()


# ── Image Classification ───────────────────────────────────────────────────


class TestClassifyImage:
    def test_context_sheet(self) -> None:
        assert _classify_image(Path("ctx_001.png")) == "context_sheet"
        assert _classify_image(Path("context_sheet_001.jpg")) == "context_sheet"

    def test_finds_catalogue(self) -> None:
        assert _classify_image(Path("finds_catalogue.csv")) == "finds_catalogue"
        assert _classify_image(Path("small_finds.xlsx")) == "finds_catalogue"

    def test_plan(self) -> None:
        assert _classify_image(Path("trench_plan.png")) == "plan"
        assert _classify_image(Path("site_plan_2026.svg")) == "plan"

    def test_site_photo(self) -> None:
        assert _classify_image(Path("DSC0042.jpg")) == "site_photo"
        assert _classify_image(Path("photo_001.png")) == "site_photo"

    def test_unknown(self) -> None:
        assert _classify_image(Path("random_file.png")) == "unknown"


# ── CSV Validation ─────────────────────────────────────────────────────────


class TestValidateCsvFinds:
    def test_valid_finds_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "finds.csv"
        _make_synthetic_csv(csv_path, [
            ["context", "object_type", "quantity", "period", "notes"],
            ["101", "pottery", "5", "Roman", ""],
            ["102", "CBM", "12", "Medieval", ""],
        ])
        valid, issues = _validate_csv_finds(csv_path)
        assert valid
        assert len(issues) == 0

    def test_missing_context_column(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "finds.csv"
        _make_synthetic_csv(csv_path, [
            ["object_type", "quantity", "period"],
            ["pottery", "5", "Roman"],
        ])
        valid, issues = _validate_csv_finds(csv_path)
        assert not valid

    def test_empty_csv(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("")
        valid, issues = _validate_csv_finds(csv_path)
        assert not valid

    def test_no_quantity_column(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "finds.csv"
        _make_synthetic_csv(csv_path, [
            ["context", "object_type", "period", "notes"],
            ["101", "pottery", "Roman", ""],
        ])
        valid, issues = _validate_csv_finds(csv_path)
        assert not valid
        assert any("quantity" in i.lower() for i in issues)


# ── XLSX Validation ────────────────────────────────────────────────────────


class TestValidateXlsxFinds:
    def test_valid_xlsx(self, tmp_path: Path) -> None:
        xlsx_path = tmp_path / "finds.xlsx"
        _make_synthetic_xlsx(xlsx_path, ["Context", "Object Type", "Qty"], [
            ["101", "pottery", 5],
            ["102", "CBM", 12],
        ])
        valid, issues = _validate_xlsx_finds(xlsx_path)
        assert valid

    def test_missing_context(self, tmp_path: Path) -> None:
        xlsx_path = tmp_path / "finds.xlsx"
        _make_synthetic_xlsx(xlsx_path, ["Object Type", "Qty", "Period"], [
            ["pottery", 5, "Roman"],
        ])
        valid, issues = _validate_xlsx_finds(xlsx_path)
        assert not valid


# ── Full Phase 0 Run ───────────────────────────────────────────────────────


class TestRunPhase0:
    def test_empty_input_directory(self, tmp_path: Path) -> None:
        """Phase 0 on an empty directory should produce an empty manifest."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        workspace = tmp_path / "erd_workspace"
        workspace.mkdir()

        config = Config(
            project_id="test_empty",
            project_name="Test Empty",
            jurisdiction="historic_england_cl3",
            workspace_root=workspace,
            input_dir=input_dir,
        )

        manifest = run_phase0(config)
        assert manifest["project_id"] == "test_empty"
        assert manifest["files"] == []
        assert manifest["mandatory_check"] == "FAIL"

    def test_single_context_sheet(self, tmp_path: Path) -> None:
        """Phase 0 should detect a single context sheet."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        _make_synthetic_png(input_dir / "ctx_001.png")
        workspace = tmp_path / "erd_workspace"

        config = Config(
            project_id="test_single",
            project_name="Test Single",
            jurisdiction="historic_england_cl3",
            workspace_root=workspace,
            input_dir=input_dir,
        )

        manifest = run_phase0(config)
        assert len(manifest["files"]) == 1
        assert manifest["files"][0]["type"] == "context_sheet"
        assert manifest["mandatory_check"] == "PASS"

    def test_correct_manifest_structure(self, tmp_path: Path) -> None:
        """The manifest JSON should match the design doc schema."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        _make_synthetic_png(input_dir / "ctx_001.png")
        _make_synthetic_csv(input_dir / "finds.csv", [
            ["context", "object_type", "quantity", "period"],
            ["101", "pottery", "5", "Roman"],
        ])
        workspace = tmp_path / "erd_workspace"

        config = Config(
            project_id="test_schema",
            project_name="Test Schema",
            jurisdiction="historic_england_cl3",
            workspace_root=workspace,
            input_dir=input_dir,
        )

        manifest = run_phase0(config)

        # Check schema fields from design doc
        assert "project_id" in manifest
        assert "created" in manifest
        assert "files" in manifest
        assert "mandatory_check" in manifest
        assert "quality_warnings" in manifest

        for entry in manifest["files"]:
            assert "id" in entry
            assert "path" in entry
            assert "type" in entry
            assert "quality" in entry

        manifest_path = workspace / "test_schema" / "00_manifest" / "manifest.json"
        assert manifest_path.exists()
        parsed = json.loads(manifest_path.read_text())
        assert parsed["project_id"] == "test_schema"

    def test_missing_library_csv(self, tmp_path: Path) -> None:
        """Phase 0 should handle CSV validation gracefully without openpyxl."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        # A CSV that looks like a finds catalogue but has no useful columns
        _make_synthetic_csv(input_dir / "finds.csv", [
            ["col1", "col2", "col3"],
            ["a", "b", "c"],
        ])
        workspace = tmp_path / "erd_workspace"

        config = Config(
            project_id="test_bad_csv",
            project_name="Test Bad CSV",
            jurisdiction="historic_england_cl3",
            workspace_root=workspace,
            input_dir=input_dir,
        )

        manifest = run_phase0(config)
        assert manifest["mandatory_check"] == "PASS"  # CSV is still a finds_catalogue
        assert len(manifest.get("finds_validation_issues", [])) > 0
