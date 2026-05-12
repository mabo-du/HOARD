"""Tests for the ARK system direct data input module.

Tests cover CSV parsing, JSON parsing, field mapping, round-trip import,
error handling, and CLI integration.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from erd.ark import ArkImportResult, guess_mapping_from_header, import_ark_export, transform_row
from erd.ark.loader import _discover_ark_files, _parse_csv, _parse_json
from erd.ark.mapping import (
    ARK_CONTEXT_FIELDS,
    ARK_FINDS_FIELDS,
    ARK_PHOTOS_FIELDS,
    _build_lookup,
)
from erd.ark.semantic_mapper import ArkSemanticMapper, map_headers_semantic
from erd.config import Config


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def ark_context_csv(tmp_path: Path) -> Path:
    """Create a realistic ARK context sheet CSV export."""
    p = tmp_path / "context.csv"
    rows = [
        ["context_id", "trench", "description", "interpretation", "period", "type", "length_m", "depth_m"],
        ["1001", "T1", "Dark brown silty clay", "Colluvial layer", "Medieval", "layer", "2.5", "0.3"],
        ["1002", "T1", "Compact yellow clay", "Natural subsoil", "Natural", "layer", "", ""],
        ["1003", "T1", "Cut for posthole", "Posthole cut", "Medieval", "cut", "0.4", "0.35"],
        ["1004", "T1", "Fill of posthole 1003", "Posthole fill", "Medieval", "fill", "", ""],
    ]
    _write_csv(p, rows)
    return p


@pytest.fixture
def ark_finds_csv(tmp_path: Path) -> Path:
    """Create a realistic ARK finds catalogue CSV export."""
    p = tmp_path / "finds.csv"
    rows = [
        ["context_id", "object_type", "material", "quantity", "weight_g", "period", "description"],
        ["1001", "Pottery", "Pottery", "12", "45.2", "Medieval", "Body sherds, moderate abrasion"],
        ["1001", "Bone", "Animal bone", "3", "12.8", "Medieval", "Calcined fragments"],
        ["1004", "Pottery", "Pottery", "1", "3.5", "Medieval", "Rim sherd, fine fabric"],
    ]
    _write_csv(p, rows)
    return p


@pytest.fixture
def ark_samples_csv(tmp_path: Path) -> Path:
    """Create an ARK sample register CSV export."""
    p = tmp_path / "samples.csv"
    rows = [
        ["context_id", "sample_no", "sample_type", "volume_ml", "processed", "period"],
        ["1003", "S001", "Bulk soil", "5000", "Y", "Medieval"],
        ["1001", "S002", "Bulk soil", "4000", "Y", "Medieval"],
    ]
    _write_csv(p, rows)
    return p


@pytest.fixture
def ark_photos_csv(tmp_path: Path) -> Path:
    """Create an ARK photo log CSV export."""
    p = tmp_path / "photos.csv"
    rows = [
        ["photo_id", "filename", "context_id", "direction", "description", "taken_by"],
        ["P001", "IMG_101.jpg", "1001", "N", "Oblique view of section", "ABC"],
        ["P002", "IMG_102.jpg", "1002", "S", "Overall trench shot", "ABC"],
    ]
    _write_csv(p, rows)
    return p


@pytest.fixture
def ark_drawings_csv(tmp_path: Path) -> Path:
    """Create an ARK drawing register CSV export."""
    p = tmp_path / "drawings.csv"
    rows = [
        ["drawing_no", "context_id", "drawing_type", "scale", "description", "drawn_by"],
        ["D001", "1001", "Section", "1:10", "North-facing section T1", "XYZ"],
        ["D002", "1003", "Plan", "1:5", "Posthole 1003 plan", "XYZ"],
    ]
    _write_csv(p, rows)
    return p


@pytest.fixture
def ark_json_export(tmp_path: Path) -> Path:
    """Create an ARK JSON export file."""
    p = tmp_path / "context.json"
    data = [
        {"context_id": "2001", "trench": "T2", "description": "Topsoil", "interpretation": "Ploughsoil", "period": "Post-Medieval"},
        {"context_id": "2002", "trench": "T2", "description": "Grey silty clay", "interpretation": "Alluvial deposit", "period": "Medieval"},
    ]
    p.write_text(json.dumps(data))
    return p


@pytest.fixture
def ark_input_dir(
    tmp_path: Path,
    ark_context_csv: Path,
    ark_finds_csv: Path,
    ark_samples_csv: Path,
    ark_photos_csv: Path,
    ark_drawings_csv: Path,
    ark_json_export: Path,
) -> Path:
    """Directory containing all ARK export fixtures."""
    return tmp_path


@pytest.fixture
def ark_minimal_dir(tmp_path: Path) -> Path:
    """Directory with minimal ARK exports (just context + finds)."""
    ctx = _write_csv(tmp_path / "context.csv", [
        ["context_id", "trench", "description"],
        ["3001", "T1", "Test context"],
    ])
    finds = _write_csv(tmp_path / "finds.csv", [
        ["context_id", "object_type", "material", "quantity"],
        ["3001", "Pottery", "Pottery", "5"],
    ])
    return tmp_path


@pytest.fixture
def ark_non_ark_dir(tmp_path: Path) -> Path:
    """Directory with no ARK export files."""
    p = tmp_path / "photos" / "DSC_001.jpg"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not-a-real-image")
    return p.parent.parent  # return parent so config.input_dir points here


def _write_csv(path: Path, rows: list[list[str]]) -> Path:
    """Helper to write a CSV file."""
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    return path


def _make_config(input_dir: Path, project_id: str = "test_ark") -> Config:
    """Helper: create a Config pointing at a temp workspace."""
    return Config(
        project_id=project_id,
        project_name="Test ARK Import",
        jurisdiction="historic_england_cl3",
        workspace_root=input_dir / "_hoard_workspace",
        input_dir=input_dir,
    )


# ── CSV parsing ─────────────────────────────────────────────────────────────


class TestParseCSV:
    def test_parses_standard_csv(self, ark_context_csv: Path) -> None:
        rows = _parse_csv(ark_context_csv)
        assert len(rows) == 4
        assert rows[0]["context_id"] == "1001"
        assert rows[0]["description"] == "Dark brown silty clay"

    def test_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.csv"
        p.write_text("")
        rows = _parse_csv(p)
        assert rows == []

    def test_header_only(self, tmp_path: Path) -> None:
        p = tmp_path / "header.csv"
        p.write_text("a,b,c\n")
        assert _parse_csv(p) == []

    def test_bom_handling(self, tmp_path: Path) -> None:
        """CSV with UTF-8 BOM should parse cleanly."""
        p = tmp_path / "bom.csv"
        # Write raw BOM bytes + CSV content
        p.write_bytes(b"\xef\xbb\xbfa,b,c\n1,2,3\n")
        rows = _parse_csv(p)
        assert len(rows) == 1
        assert rows[0]["a"] == "1"


# ── JSON parsing ────────────────────────────────────────────────────────────


class TestParseJSON:
    def test_parses_array(self, ark_json_export: Path) -> None:
        rows = _parse_json(ark_json_export)
        assert len(rows) == 2
        assert rows[0]["context_id"] == "2001"

    def test_parses_data_wrapper(self, tmp_path: Path) -> None:
        p = tmp_path / "wrapped.json"
        p.write_text(json.dumps({"data": [{"a": "1"}, {"a": "2"}]}))
        rows = _parse_json(p)
        assert len(rows) == 2

    def test_parses_results_wrapper(self, tmp_path: Path) -> None:
        p = tmp_path / "results.json"
        p.write_text(json.dumps({"results": [{"x": "y"}]}))
        rows = _parse_json(p)
        assert len(rows) == 1

    def test_empty_array(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.json"
        p.write_text("[]")
        assert _parse_json(p) == []

    def test_unrecognised_structure(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"metadata": {"version": "1"}}))
        with pytest.raises(ValueError, match="Unrecognised JSON structure"):
            _parse_json(p)

    def test_invalid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "invalid.json"
        p.write_text("{not-json}")
        with pytest.raises(json.JSONDecodeError):
            _parse_json(p)


# ── File discovery ──────────────────────────────────────────────────────────


class TestDiscoverArkFiles:
    def test_finds_context_finds(self, ark_input_dir: Path) -> None:
        files = _discover_ark_files(ark_input_dir)
        found_types = {t for _, t in files}
        assert "context" in found_types
        assert "finds" in found_types

    def test_supports_multiple_extensions(self, ark_input_dir: Path) -> None:
        files = _discover_ark_files(ark_input_dir)
        sources = {f.suffix.lower(): t for f, t in files}
        assert ".csv" in sources
        assert ".json" in sources

    def test_empty_directory(self, tmp_path: Path) -> None:
        assert _discover_ark_files(tmp_path) == []

    def test_non_ark_files_ignored(self, ark_non_ark_dir: Path) -> None:
        assert _discover_ark_files(ark_non_ark_dir) == []

    def test_finds_all_five_types(self, ark_input_dir: Path) -> None:
        files = _discover_ark_files(ark_input_dir)
        types = {t for _, t in files}
        assert types == {"context", "finds", "samples", "photos", "drawings"}

    def test_dotfiles_ignored(self, tmp_path: Path) -> None:
        (tmp_path / ".context.csv").write_text("a,b\n1,2\n")
        assert _discover_ark_files(tmp_path) == []


# ── Field mapping ───────────────────────────────────────────────────────────


class TestGuessMapping:
    def test_maps_standard_context_headers(self) -> None:
        header = ["context_id", "trench_code", "description", "period", "type"]
        mapping = guess_mapping_from_header(header, ARK_CONTEXT_FIELDS)
        assert mapping["context_number"] == "context_id"
        assert mapping["trench"] == "trench_code"
        assert mapping["description"] == "description"
        assert mapping["period"] == "period"
        assert mapping["context_type"] == "type"

    def test_maps_standard_finds_headers(self) -> None:
        header = ["context_id", "object_type", "material", "quantity", "weight_g"]
        mapping = guess_mapping_from_header(header, ARK_FINDS_FIELDS)
        assert mapping["context_number"] == "context_id"
        assert mapping["object_type"] == "object_type"
        assert mapping["quantity"] == "quantity"

    def test_case_insensitive(self) -> None:
        header = ["Context_ID", "Trench", "Description"]
        mapping = guess_mapping_from_header(header, ARK_CONTEXT_FIELDS)
        assert "context_number" in mapping
        assert "trench" in mapping

    def test_unrecognised_columns_ignored(self) -> None:
        header = ["context_id", "spreadsheet_secret_staff_only", "description"]
        mapping = guess_mapping_from_header(header, ARK_CONTEXT_FIELDS)
        assert "context_number" in mapping
        assert "description" in mapping
        assert "spreadsheet_secret_staff_only" not in mapping

    def test_first_match_wins(self) -> None:
        # Both "context_id" and "context_number" can map to hoard "context_number"
        header = ["context_number", "context_id"]
        mapping = guess_mapping_from_header(header, ARK_CONTEXT_FIELDS)
        # "context_number" appears first -> should win for mapping to "context_number"
        assert mapping["context_number"] == "context_number"


class TestTransformRow:
    def test_basic_transformation(self) -> None:
        field_map = {"context_number": "context_id", "trench": "trench", "description": "description"}
        row = {"context_id": "1001", "trench": "T1", "description": "Dark silt"}
        result = transform_row(row, field_map, "context")
        assert result["context_number"] == "1001"
        assert result["trench"] == "T1"
        assert result["description"] == "Dark silt"
        assert result["_source"] == "context"

    def test_whitespace_stripped(self) -> None:
        field_map = {"context_number": "context_id", "description": "desc"}
        row = {"context_id": "  1001  ", "desc": "  silt  "}
        result = transform_row(row, field_map, "context")
        assert result["context_number"] == "1001"
        assert result["description"] == "silt"

    def test_empty_values_preserved(self) -> None:
        field_map = {"context_number": "context_id", "depth_m": "depth"}
        row = {"context_id": "1001", "depth": ""}
        result = transform_row(row, field_map, "context")
        assert result["depth_m"] == ""


# ── Build lookup ────────────────────────────────────────────────────────────


class TestBuildLookup:
    def test_builds_dict(self) -> None:
        mappings = [("ContextID", "ctx", None), ("Trench", "trench", None)]
        lookup = _build_lookup(mappings)
        assert lookup["contextid"] == "ctx"
        assert lookup["trench"] == "trench"

    def test_last_wins_on_collision(self) -> None:
        mappings = [("col", "field_a", None), ("col", "field_b", None)]
        lookup = _build_lookup(mappings)
        assert lookup["col"] == "field_b"


# ── Full import integration ─────────────────────────────────────────────────


class TestImportArkExport:
    def test_imports_context_and_finds(self, ark_minimal_dir: Path) -> None:
        cfg = _make_config(ark_minimal_dir)
        result = import_ark_export(cfg)
        assert result.total_records == 2
        assert result.records_by_type.get("context") == 1
        assert result.records_by_type.get("finds") == 1
        assert result.files_found == 2
        assert result.files_parsed == 2
        assert result.manifest_path is not None
        assert result.manifest_path.exists()

    def test_imports_all_five_types(self, ark_input_dir: Path) -> None:
        cfg = _make_config(ark_input_dir)
        result = import_ark_export(cfg)
        assert result.total_records == 15  # 6 context (4 CSV + 2 JSON) + 3 finds + 2 samples + 2 photos + 2 drawings
        assert len(result.records_by_type) == 5

    def test_generates_manifest(self, ark_minimal_dir: Path) -> None:
        cfg = _make_config(ark_minimal_dir)
        result = import_ark_export(cfg)
        manifest = json.loads(result.manifest_path.read_text())
        assert manifest["import_method"] == "ark"
        assert manifest["phase0_bypassed"] is True
        assert manifest["phase1_bypassed"] is True
        assert manifest["mandatory_check"] == "PASS"
        assert manifest["halt"] is False
        assert len(manifest["files"]) == 2

    def test_writes_digitised_json(self, ark_minimal_dir: Path) -> None:
        cfg = _make_config(ark_minimal_dir)
        result = import_ark_export(cfg)
        digitised_dir = cfg.digitised_dir
        json_files = sorted(digitised_dir.glob("*.json"))
        assert len(json_files) == result.total_records
        record = json.loads(json_files[0].read_text())
        assert "_source" in record
        assert "_ark_fields_mapped" in record

    def test_updates_pipeline_state(self, ark_minimal_dir: Path) -> None:
        cfg = _make_config(ark_minimal_dir)
        result = import_ark_export(cfg)
        state_path = cfg.project_dir / "pipeline_state.json"
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert state["phases"]["0"]["status"] == "complete"
        assert state["phases"]["1"]["status"] == "complete"
        assert "Bypassed via ARK import" in state["phases"]["0"]["summary"]

    def test_empty_input_dir(self, tmp_path: Path) -> None:
        cfg = _make_config(tmp_path)
        result = import_ark_export(cfg)
        assert result.total_records == 0
        assert len(result.errors) > 0
        assert "No ARK export files found" in result.errors[0]

    def test_non_ark_dir(self, ark_non_ark_dir: Path) -> None:
        cfg = _make_config(ark_non_ark_dir)
        result = import_ark_export(cfg)
        assert result.total_records == 0
        assert len(result.errors) > 0

    def test_handles_malformed_csv_gracefully(self, tmp_path: Path) -> None:
        p = tmp_path / "context.csv"
        p.write_text("a,b,c\n1,2,3\n4,5")  # malformed row
        cfg = _make_config(tmp_path)
        result = import_ark_export(cfg)
        # Should still attempt, error gracefully
        assert isinstance(result, ArkImportResult)


# ── Forward-compatibility: Phase 5 data contract ───────────────────────────


class TestPhase5Compatibility:
    """Digitised output should match Phase 5's expected input format."""

    def test_digitised_records_have_source_key(self, ark_minimal_dir: Path) -> None:
        cfg = _make_config(ark_minimal_dir)
        import_ark_export(cfg)
        for json_file in sorted(cfg.digitised_dir.glob("*.json")):
            record = json.loads(json_file.read_text())
            assert "_source" in record, f"{json_file.name} missing _source"

    def test_digitised_records_have_context_number(self, ark_minimal_dir: Path) -> None:
        cfg = _make_config(ark_minimal_dir)
        import_ark_export(cfg)
        for json_file in sorted(cfg.digitised_dir.glob("context_*.json")):
            record = json.loads(json_file.read_text())
            assert "context_number" in record, f"{json_file.name} missing context_number"

    def test_finds_records_have_quantity(self, ark_minimal_dir: Path) -> None:
        cfg = _make_config(ark_minimal_dir)
        import_ark_export(cfg)
        for json_file in sorted(cfg.digitised_dir.glob("finds_*.json")):
            record = json.loads(json_file.read_text())
            assert "quantity" in record, f"{json_file.name} missing quantity"

    def test_manifest_has_ark_record_count(self, ark_minimal_dir: Path) -> None:
        cfg = _make_config(ark_minimal_dir)
        import_ark_export(cfg)
        manifest = json.loads(cfg.manifest_dir.joinpath("manifest.json").read_text())
        for entry in manifest["files"]:
            assert "ark_record_count" in entry
            assert entry["ark_record_count"] > 0


# ── Warning / edge-case tests ──────────────────────────────────────────────


class TestWarningsAndErrors:
    def test_warns_on_unrecognised_columns(self, tmp_path: Path) -> None:
        ctx = tmp_path / "context.csv"
        ctx.write_bytes("context_id,description,secret_staff_field\n1001,silt,hidden\n".encode("utf-8-sig"))
        cfg = _make_config(tmp_path)
        result = import_ark_export(cfg)
        assert any("unrecognised" in w.lower() for w in result.warnings)

    def test_mixed_known_unknown_files(self, tmp_path: Path) -> None:
        (tmp_path / "context.csv").write_bytes("context_id\n1001\n".encode())
        (tmp_path / "notebook.csv").write_bytes("a,b\n1,2\n".encode())
        cfg = _make_config(tmp_path)
        result = import_ark_export(cfg)
        assert result.files_found == 1  # only context.csv matched
        assert result.total_records == 1


# ── Semantic mapper tests ──────────────────────────────────────────────────

SEMANTIC_SKIP_REASON = "sentence-transformers not installed"


class TestSemanticMapper:
    """Tests for the semantic embedding-based header mapper.

    These tests verify that the semantic mapper can recognise ARK column
    names that don't appear in the static mapping table but are semantically
    similar to known HOARD fields.
    """

    def test_mapper_instantiation(self) -> None:
        mapper = ArkSemanticMapper()
        assert mapper is not None
        assert mapper._available is None  # lazy load

    def test_maps_unseen_variant(self) -> None:
        """Recognise 'ctx_id' and 'trench_name' as HOARD fields."""
        result = map_headers_semantic(["ctx_id", "trench_name", "deposit_description"], "context")
        # All three should be mapped to SOME HOARD field
        assert len(result) >= 2
        # ctx_id should match a context-related field
        assert any("context" in k or "number" in k for k in result)

    def test_maps_context_variant(self) -> None:
        """Handle 'ctx_description' as a text/notes field."""
        result = map_headers_semantic(["ctx_description", "recorded_by_initials"], "context")
        assert len(result) == 2
        # ctx_description -> some text field, recorded_by_initials -> recorder
        assert "recorded_by" in result

    def test_maps_finds_variant(self) -> None:
        """Handle 'sf_number' as find_number, 'object_material' as material."""
        result = map_headers_semantic(["sf_number", "object_material", "item_count"], "finds")
        assert "find_number" in result
        assert "material" in result
        assert "quantity" in result

    def test_maps_photo_variant(self) -> None:
        """Handle 'image_filename', 'view_direction', 'photo_notes'."""
        result = map_headers_semantic(["image_filename", "view_direction", "photo_notes"], "photos")
        assert "filename" in result
        assert "direction" in result
        # photo_notes should map to a text/notes field
        assert len(result) == 3

    def test_exact_matches_still_work(self) -> None:
        """Semantic mapper can match exact known fields too."""
        result = map_headers_semantic(["context_id", "trench", "description"], "context")
        assert result.get("context_number") == "context_id"
        assert result.get("trench") == "trench"
        assert result.get("description") == "description"

    def test_empty_header_list(self) -> None:
        """Empty header list should return empty dict, not crash."""
        result = map_headers_semantic([], "context")
        assert result == {}

    def test_semantic_fills_unrecognised_in_full_pipeline(self) -> None:
        """Integration: guess_mapping_from_header uses semantic mapper to fill
        columns not in the static mapping table."""
        # 'ctx_id' and 'deposit_description' are NOT in the static mapping table
        header = ["ctx_id", "trench_code", "deposit_description"]
        result = guess_mapping_from_header(header, ARK_CONTEXT_FIELDS)
        assert "context_number" in result  # from semantic fallback
        assert "trench" in result          # from exact match
        # Semantic mapper should fill at least one more field beyond exact matches
        assert len(result) >= 3            # ctx_id + trench_code + deposit_description
