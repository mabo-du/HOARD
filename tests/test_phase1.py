"""test_phase1.py — Unit tests for Phase 1: Multi-Modal Digitisation.

Tests: checkbox post-processor, Pydantic models, image pre-processing,
helper functions. No GPU or Ollama required.

exports: (test functions)
used_by: pytest
rules:   Must not require GPU or real model inference. Uses synthetic data.
agent:   deepseek-v4-pro | 2026-05-25 | t007 | Phase 1 unit tests
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from erd.phases.phase1 import (
    ContextSheet,
    Find,
    _has_any_checkbox,
    _postprocess_checkboxes,
    _preprocess_image,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Find model
# ═══════════════════════════════════════════════════════════════════════════════

class TestFindModel:
    def test_valid_find(self):
        f = Find(type="pottery", qty=12, period="medieval", notes="Green-glazed")
        assert f.type == "pottery"
        assert f.qty == 12
        assert f.period == "medieval"

    def test_defaults(self):
        f = Find(type="bone", qty=0, period="undated")
        assert f.notes == ""

    def test_serialises(self):
        f = Find(type="CBM", qty=5, period="post-medieval")
        d = f.model_dump()
        assert d["type"] == "CBM"
        assert d["qty"] == 5


# ═══════════════════════════════════════════════════════════════════════════════
# ContextSheet model
# ═══════════════════════════════════════════════════════════════════════════════

class TestContextSheet:
    def test_minimal_valid(self):
        cs = ContextSheet(
            source_file="ctx_101.png",
            model="glm-ocr",
            context_number="[101]",
            type="layer",
            description="Dark silty clay",
            interpretation="Ploughsoil",
        )
        assert cs.context_number == "[101]"
        assert cs.finds == []
        assert cs.samples == []
        assert cs.sketch_present is False
        assert cs.review_flags == []

    def test_full_sheet(self):
        cs = ContextSheet(
            source_file="ctx_102.png",
            model="glm-ocr",
            context_number="[102]",
            type="cut",
            cut_by=["[101]"],
            cuts=["[103]"],
            fills=["[104]"],
            description="Linear cut feature",
            interpretation="Roman ditch",
            period="Roman",
            finds=[Find(type="pottery", qty=3, period="Roman")],
            samples=[{"id": "S001", "type": "bulk", "notes": "Charcoal"}],
            sketch_present=True,
            review_flags=[{"field": "period", "issue": "Ambiguous dating"}],
        )
        assert cs.cuts == ["[103]"]
        assert len(cs.finds) == 1
        assert len(cs.samples) == 1

    def test_serialises_to_json(self):
        cs = ContextSheet(
            source_file="test.png",
            model="glm-ocr",
            context_number="[201]",
            type="layer",
            description="Silty clay",
            interpretation="Natural",
            period="undated",
        )
        d = cs.model_dump()
        assert d["context_number"] == "[201]"
        assert d["type"] == "layer"

    def test_json_roundtrip(self):
        cs = ContextSheet(
            source_file="test.png",
            model="glm-ocr",
            context_number="[301]",
            type="deposit",
            description="Rubble deposit",
            interpretation="Demolition layer",
            finds=[Find(type="CBM", qty=20, period="modern")],
        )
        j = json.dumps(cs.model_dump())
        parsed = ContextSheet.model_validate_json(j)
        assert parsed.context_number == "[301]"


# ═══════════════════════════════════════════════════════════════════════════════
# _has_any_checkbox
# ═══════════════════════════════════════════════════════════════════════════════

class TestHasAnyCheckbox:
    def test_detects_default_checkmark(self):
        assert _has_any_checkbox("Layer (✓) Cut ( )")

    def test_detects_alternative_checkmark(self):
        assert _has_any_checkbox("Layer (✔) Cut ( )")

    def test_detects_bracket_x(self):
        assert _has_any_checkbox("Layer [x] Cut [ ]")

    def test_detects_parenthetical_x(self):
        assert _has_any_checkbox("Layer (x) Cut ( )")

    def test_detects_unicode_ballot(self):
        assert _has_any_checkbox("Layer (☑) Cut ( )")

    def test_no_checkbox_clean_string(self):
        assert not _has_any_checkbox("layer")

    def test_no_checkbox_clean_description(self):
        assert not _has_any_checkbox("Dark brown silty clay")

    def test_no_checkbox_empty(self):
        assert not _has_any_checkbox("")

    def test_no_checkbox_numbers(self):
        assert not _has_any_checkbox("Context [101]")


# ═══════════════════════════════════════════════════════════════════════════════
# _postprocess_checkboxes
# ═══════════════════════════════════════════════════════════════════════════════

class TestPostprocessCheckboxes:
    """Comprehensive tests for checkbox normalisation."""

    # ── Categorical checkbox groups ──

    def test_layer_checked(self):
        result = _postprocess_checkboxes({"type": "Layer (✓) Cut ( ) Deposit ( ) Fill ( )"})
        assert result["type"] == "layer"

    def test_cut_checked(self):
        result = _postprocess_checkboxes({"type": "Layer ( ) Cut (✓) Deposit ( ) Fill ( )"})
        assert result["type"] == "cut"

    def test_deposit_checked(self):
        result = _postprocess_checkboxes({"type": "Layer ( ) Cut ( ) Deposit (✓) Fill ( )"})
        assert result["type"] == "deposit"

    def test_fill_checked(self):
        result = _postprocess_checkboxes({"type": "Layer ( ) Cut ( ) Deposit ( ) Fill (✓)"})
        assert result["type"] == "fill"

    def test_alternate_checkmark(self):
        result = _postprocess_checkboxes({"type": "Layer ( ) Cut ( ) Deposit ( ) Structure (✔)"})
        assert result["type"] == "structure"

    def test_bracket_variant(self):
        result = _postprocess_checkboxes({"type": "Layer [x] Cut [ ] Deposit [ ]"})
        assert result["type"] == "layer"

    def test_parenthetical_variant(self):
        result = _postprocess_checkboxes({"type": "Layer (x) Cut ( )"})
        assert result["type"] == "layer"

    def test_unicode_ballot(self):
        result = _postprocess_checkboxes({"type": "Layer (☑) Cut ( )"})
        assert result["type"] == "layer"

    def test_multiple_fields(self):
        data = {
            "type": "Layer (✓) Cut ( ) Deposit ( )",
            "period": "Roman (✓) Medieval ( ) Post-Med ( )",
        }
        result = _postprocess_checkboxes(data)
        assert result["type"] == "layer"
        assert result["period"] == "roman"

    # ── Boolean Yes/No ──

    def test_yes_checked_sketch(self):
        result = _postprocess_checkboxes({"sketch_present": "Yes (✓) No ( )"})
        assert result["sketch_present"] is True

    def test_no_checked_sketch(self):
        result = _postprocess_checkboxes({"sketch_present": "Yes ( ) No (✓)"})
        assert result["sketch_present"] is False

    def test_lowercase_yes(self):
        result = _postprocess_checkboxes({"sketch_present": "yes (✓) no ( )"})
        assert result["sketch_present"] is True

    # ── Boolean via categorical field (type as yes/no) ──

    def test_type_as_boolean_yes(self):
        result = _postprocess_checkboxes({"type": "Yes (✓) No ( )"})
        assert result["type"] is True

    def test_type_as_boolean_no(self):
        result = _postprocess_checkboxes({"type": "Yes ( ) No (✓)"})
        assert result["type"] is False

    # ── Pass-through (no checkboxes) ──

    def test_clean_value_unchanged(self):
        result = _postprocess_checkboxes({"type": "layer", "period": "medieval"})
        assert result["type"] == "layer"
        assert result["period"] == "medieval"

    def test_context_number_unchanged(self):
        result = _postprocess_checkboxes({"context_number": "[101]"})
        assert result["context_number"] == "[101]"

    def test_source_file_unchanged(self):
        result = _postprocess_checkboxes({"source_file": "test.jpg", "model": "glm-ocr"})
        assert result["source_file"] == "test.jpg"

    # ── Edge cases ──

    def test_empty_string(self):
        result = _postprocess_checkboxes({"type": ""})
        assert result["type"] == ""

    def test_none_value(self):
        result = _postprocess_checkboxes({"type": None})
        assert result["type"] is None

    def test_returns_dict(self):
        result = _postprocess_checkboxes({})
        assert isinstance(result, dict)

    def test_mutates_in_place(self):
        data = {"type": "Layer (✓) Cut ( )"}
        result = _postprocess_checkboxes(data)
        assert result is data  # same dict

    def test_certainty_field(self):
        data = {"certainty": "Probable (✓) Possible ( ) Definite ( )"}
        result = _postprocess_checkboxes(data)
        assert result["certainty"] == "probable"


# ═══════════════════════════════════════════════════════════════════════════════
# Image pre-processing (synthetic)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreprocessImage:
    @staticmethod
    def _make_png(path: Path, w: int = 50, h: int = 50) -> None:
        """Create a proper PNG file using PIL."""
        from PIL import Image
        img = Image.new("RGB", (w, h), color=(100, 100, 100))
        # Add some variation so it's not a flat colour
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, 30, 30], fill=(200, 50, 50))
        img.save(path, format="PNG")

    def test_returns_bytes_from_png(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp = Path(f.name)
        self._make_png(tmp)
        try:
            result = _preprocess_image(tmp)
            assert isinstance(result, bytes)
            assert len(result) > 0
        finally:
            tmp.unlink(missing_ok=True)

    def test_raises_on_invalid_path(self):
        with pytest.raises(Exception):
            _preprocess_image(Path("/nonexistent/image.png"))

    def test_handles_quality_flags(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp = Path(f.name)
        self._make_png(tmp)
        try:
            result = _preprocess_image(tmp, quality_flags={"flag": "EXPOSURE_LOW"})
            assert isinstance(result, bytes)
            result2 = _preprocess_image(tmp)
            assert isinstance(result2, bytes)
        finally:
            tmp.unlink(missing_ok=True)
