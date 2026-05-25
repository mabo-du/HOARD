"""test_phase3.py — Unit tests for Phase 3: Synthesis & Narrative Drafting.

Tests: section extraction, review triggers, JSON/file helpers,
context assembly. No GPU or Ollama required.

exports: (test functions)
used_by: pytest
rules:   Must not require GPU or real model inference.
agent:   deepseek-v4-pro | 2026-05-25 | t017 | Phase 3 unit tests
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from erd.phases.phase3 import (
    _check_review_triggers,
    _extract_sections,
    _find_json_files,
    _load_json_safe,
    _render_context_summary,
    _render_finds_summary,
    _render_harris_relationships,
    _render_sample_results,
)


# ═══════════════════════════════════════════════════════════════════════════════
# _load_json_safe
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoadJsonSafe:
    def test_valid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"key": "value"}, f)
            tmp = Path(f.name)
        try:
            result = _load_json_safe(tmp)
            assert result == {"key": "value"}
        finally:
            tmp.unlink(missing_ok=True)

    def test_missing_file(self):
        result = _load_json_safe(Path("/nonexistent/file.json"))
        assert result == {}

    def test_corrupt_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{not valid json")
            tmp = Path(f.name)
        try:
            result = _load_json_safe(tmp)
            assert result == {}
        finally:
            tmp.unlink(missing_ok=True)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp = Path(f.name)
        try:
            result = _load_json_safe(tmp)
            assert result == {}
        finally:
            tmp.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# _find_json_files
# ═══════════════════════════════════════════════════════════════════════════════

class TestFindJsonFiles:
    def test_returns_sorted(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "b.json").write_text("{}")
            (tmp / "a.json").write_text("{}")
            (tmp / "c.json").write_text("{}")
            result = _find_json_files(tmp)
            assert len(result) == 3
            assert result[0].name == "a.json"
            assert result[1].name == "b.json"
            assert result[2].name == "c.json"

    def test_missing_dir(self):
        result = _find_json_files(Path("/nonexistent"))
        assert result == []

    def test_non_json_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "a.json").write_text("{}")
            (tmp / "b.txt").write_text("text")
            result = _find_json_files(tmp)
            assert len(result) == 1
            assert result[0].name == "a.json"

    def test_custom_pattern(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "a.json").write_text("{}")
            (tmp / "b.md").write_text("# text")
            result = _find_json_files(tmp, "*.md")
            assert len(result) == 1
            assert result[0].name == "b.md"


# ═══════════════════════════════════════════════════════════════════════════════
# _extract_sections
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractSections:
    def test_single_section(self):
        text = "##section:executive_summary\n## Executive Summary\nReport content here.\nMore text."
        result = _extract_sections(text)
        assert "executive_summary" in result
        assert "Executive Summary" in result["executive_summary"]

    def test_multiple_sections(self):
        text = (
            "##section:introduction\n## Introduction\nSite description.\n\n"
            "##section:methodology\n## Methodology\nMethods used.\n\n"
            "##section:results\n## Results\nFindings here."
        )
        result = _extract_sections(text)
        assert len(result) == 3
        assert "introduction" in result
        assert "methodology" in result
        assert "results" in result

    def test_section_with_special_chars(self):
        text = "##section:results_prehistoric\n## Results: Prehistoric\nContent here."
        result = _extract_sections(text)
        assert "results_prehistoric" in result

    def test_preserves_markdown_formatting(self):
        text = "##section:discussion\n## Discussion\n**Bold** and *italic* text.\n\n- List item"
        result = _extract_sections(text)
        assert "**Bold**" in result["discussion"]

    def test_empty_text(self):
        assert _extract_sections("") == {}

    def test_no_sections(self):
        text = "## Just a heading\nContent without section labels."
        result = _extract_sections(text)
        assert result == {}

    def test_section_with_leading_text(self):
        text = "Preamble text.\n##section:executive_summary\n## Summary\nContent."
        result = _extract_sections(text)
        assert "Preamble" not in str(result)
        assert "executive_summary" in result

    def test_section_label_included_in_content(self):
        """The section label line itself should be included in the content."""
        text = "##section:intro\n## Introduction\nBody."
        result = _extract_sections(text)
        assert "section:intro" in result["intro"]


# ═══════════════════════════════════════════════════════════════════════════════
# _check_review_triggers
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckReviewTriggers:
    def test_uncertainty_triggers(self):
        triggers = _check_review_triggers(
            "The evidence is insufficient data for firm conclusions.",
            {"contexts": []},
        )
        assert any(t["issue"] == "UNCERTAINTY" for t in triggers)

    def test_conflicting_evidence(self):
        triggers = _check_review_triggers(
            "There is conflicting evidence from the pottery and C14 dates.",
            {"contexts": []},
        )
        assert any(t["issue"] == "UNCERTAINTY" for t in triggers)

    def test_cannot_determine(self):
        triggers = _check_review_triggers(
            "We cannot determine the exact date range.",
            {"contexts": []},
        )
        assert any(t["issue"] == "UNCERTAINTY" for t in triggers)

    def test_no_triggers_on_clean_text(self):
        triggers = _check_review_triggers(
            "The pottery assemblage dates to the 2nd century AD.",
            {"contexts": []},
        )
        assert len(triggers) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# _render_context_summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestRenderContextSummary:
    def test_renders_valid_contexts(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "ctx_101.json").write_text(json.dumps({
                "context_number": "[101]",
                "type": "layer",
                "period": "medieval",
                "interpretation": "Ploughsoil",
            }))
            result = _render_context_summary(tmp)
            assert "[101]" in result
            assert "layer" in result
            assert "Ploughsoil" in result

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            result = _render_context_summary(Path(d))
            assert "No context" in result

    def test_skips_non_context_jsons(self):
        """Non-context JSON files use stem as context_number."""
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "data.json").write_text('{"key": "not a context"}')
            result = _render_context_summary(tmp)
            # Should still include the file (uses stem as context_number)
            assert "data" in result


# ═══════════════════════════════════════════════════════════════════════════════
# _render_finds_summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestRenderFindsSummary:
    def test_renders_finds(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "ctx_101.json").write_text(json.dumps({
                "context_number": "[101]",
                "finds": [{"type": "pottery", "qty": 12, "period": "medieval"}],
            }))
            result = _render_finds_summary(tmp)
            assert "pottery" in result
            assert "12" in result

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            result = _render_finds_summary(Path(d))
            assert "No finds" in result

    def test_context_without_finds(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "ctx_101.json").write_text(json.dumps({
                "context_number": "[101]",
                "finds": [],
            }))
            result = _render_finds_summary(tmp)
            assert "No finds" in result


# ═══════════════════════════════════════════════════════════════════════════════
# _render_sample_results
# ═══════════════════════════════════════════════════════════════════════════════

class TestRenderSampleResults:
    def test_renders_samples(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "ctx_101.json").write_text(json.dumps({
                "context_number": "[101]",
                "samples": [{"id": "S001", "type": "bulk", "notes": "Charcoal"}],
            }))
            result = _render_sample_results(tmp)
            assert "S001" in result
            assert "Charcoal" in result

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            result = _render_sample_results(Path(d))
            assert "No sample" in result


# ═══════════════════════════════════════════════════════════════════════════════
# _render_harris_relationships
# ═══════════════════════════════════════════════════════════════════════════════

class TestRenderHarrisRelationships:
    def test_renders_relationships(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "ctx_101.json").write_text(json.dumps({
                "context_number": "[101]",
                "cut_by": ["[102]"],
                "cuts": ["[100]"],
            }))
            result = _render_harris_relationships(tmp)
            assert "[101]" in result
            assert "cut_by" in result.lower() or "cuts" in result.lower()

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            result = _render_harris_relationships(Path(d))
            # Should not crash with empty dir
            assert isinstance(result, str)
