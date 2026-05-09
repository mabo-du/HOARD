"""test_phase5.py — Unit tests for Phase 5: Assembly & Export.

Tests: figure resolution, appendix generation, Harris Matrix SVG,
bibliography extraction, Markdown compilation, archive packaging.

exports: (test functions)
used_by: pytest
rules:   Must not require GPU or real model inference.
         Must not require pandoc to be installed (graceful skip).
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Phase 5 tests
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from erd.config import Config
from erd.phases.phase5 import (
    _compile_markdown,
    _generate_bibliography,
    _generate_context_register,
    _generate_finds_concordance,
    _generate_harris_matrix_svg,
    _generate_sample_register,
    _resolve_figures,
    assemble_report,
    export_report,
    run_phase5,
)

# ── Figure Resolution ────────────────────────────────────────────────────────


class TestResolveFigures:
    def test_figure_found(self, tmp_path: Path) -> None:
        """[FIG:test] should be replaced with an image embed when file exists."""
        (tmp_path / "test.png").write_text("fake-png")
        result = _resolve_figures(
            "See [FIG:test] for details.",
            tmp_path, tmp_path,
        )
        assert "test.png" in result
        assert "![" in result

    def test_figure_not_found(self, tmp_path: Path) -> None:
        """Missing figures should get a placeholder."""
        result = _resolve_figures(
            "See [FIG:missing] for details.",
            tmp_path, tmp_path,
        )
        assert "not found" in result

    def test_no_figures(self, tmp_path: Path) -> None:
        """Text with no figure references should pass through unchanged."""
        text = "Plain text with no figures."
        result = _resolve_figures(text, tmp_path, tmp_path)
        assert result == text

    def test_multiple_figures(self, tmp_path: Path) -> None:
        (tmp_path / "fig1.png").write_text("fake")
        (tmp_path / "fig2.png").write_text("fake")
        text = "See [FIG:fig1] and [FIG:fig2]."
        result = _resolve_figures(text, tmp_path, tmp_path)
        assert result.count("![") == 2
        assert "fig1.png" in result
        assert "fig2.png" in result


# ── Appendix Generation ──────────────────────────────────────────────────────


class TestContextRegister:
    def test_no_data(self, tmp_path: Path) -> None:
        result = _generate_context_register(tmp_path)
        assert "No context data" in result

    def test_with_data(self, tmp_path: Path) -> None:
        ctx = {
            "context_number": "[001]",
            "type": "layer",
            "description": "Dark brown silty clay",
            "interpretation": "Ploughsoil",
            "period": "Post-medieval",
            "finds": [],
            "samples": [],
        }
        (tmp_path / "ctx_001.json").write_text(json.dumps(ctx))

        result = _generate_context_register(tmp_path)
        assert "[001]" in result
        assert "layer" in result
        assert "|" in result  # Table format


class TestFindsConcordance:
    def test_no_data(self, tmp_path: Path) -> None:
        result = _generate_finds_concordance(tmp_path)
        assert "No finds data" in result

    def test_with_finds(self, tmp_path: Path) -> None:
        ctx = {
            "context_number": "[001]",
            "finds": [
                {"type": "pottery", "qty": 5, "period": "Roman", "notes": "Coarseware"},
                {"type": "CBM", "qty": 12, "period": "Roman", "notes": ""},
            ],
        }
        (tmp_path / "ctx_001.json").write_text(json.dumps(ctx))

        result = _generate_finds_concordance(tmp_path)
        assert "pottery" in result
        assert "5" in result or "12" in result


class TestSampleRegister:
    def test_no_data(self, tmp_path: Path) -> None:
        result = _generate_sample_register(tmp_path)
        assert "No sample data" in result

    def test_with_samples(self, tmp_path: Path) -> None:
        ctx = {
            "context_number": "[001]",
            "samples": [
                {"id": "S001", "type": "bulk", "notes": "Charcoal"},
            ],
        }
        (tmp_path / "ctx_001.json").write_text(json.dumps(ctx))

        result = _generate_sample_register(tmp_path)
        assert "S001" in result
        assert "bulk" in result


# ── Harris Matrix ────────────────────────────────────────────────────────────


class TestHarrisMatrix:
    def test_no_relationships(self) -> None:
        ctx = [{"context_number": "[001]"}]
        result = _generate_harris_matrix_svg(ctx)
        assert result is None

    def test_single_edge(self) -> None:
        ctx = [
            {"context_number": "[001]", "cuts": ["[002]"]},
            {"context_number": "[002]", "cut_by": ["[001]"]},
        ]
        result = _generate_harris_matrix_svg(ctx)
        # May be None if graphviz not installed
        if result is not None:
            assert "svg" in result.lower() or "<svg" in result

    def test_multiple_relationships(self) -> None:
        ctx = [
            {"context_number": "[001]", "fills": ["[002]"]},
            {"context_number": "[002]", "filled_by": ["[001]"], "cuts": ["[003]"]},
            {"context_number": "[003]", "cut_by": ["[002]"]},
        ]
        result = _generate_harris_matrix_svg(ctx)
        if result is not None:
            assert "svg" in result.lower() or "<svg" in result


# ── Bibliography ─────────────────────────────────────────────────────────────


class TestBibliography:
    def test_no_citations(self) -> None:
        result = _generate_bibliography("Plain text with no citations.")
        assert "No citations" in result

    def test_single_citation(self) -> None:
        result = _generate_bibliography("As noted by (Smith, 2020), the context was clear.")
        assert "Smith" in result
        assert "2020" in result

    def test_multiple_citations(self) -> None:
        text = "Previous work (Jones, 2019) and (Brown et al., 2021) supports this."
        result = _generate_bibliography(text)
        assert "Jones" in result
        assert "Brown et al." in result

    def test_deduplicates(self) -> None:
        text = "See (Smith, 2020) and also (Smith, 2020)."
        result = _generate_bibliography(text)
        assert result.count("Smith") == 1  # Only one entry


# ── Markdown Compilation ─────────────────────────────────────────────────────


class TestCompileMarkdown:
    def test_basic_assembly(self) -> None:
        body = "## Results\nA Roman ditch was identified."
        appendices = {
            "context_register": "| Context | Type |\n|---------|------|\n| [001] | layer |\n\n",
            "finds_concordance": "*No finds data available.*\n\n",
            "sample_register": "*No sample data available.*\n\n",
        }
        bibliography = "Smith (2020). *Title*.\n"

        result = _compile_markdown(body, appendices, bibliography)
        assert "Excavation Report" in result
        assert "Results" in result
        assert "Context Register" in result
        assert "Finds Concordance" not in result  # Only non-empty appendices included
        assert "Smith (2020)" in result


# ── Assembly ─────────────────────────────────────────────────────────────────


class TestAssembleReport:
    def test_no_refined_data(self, tmp_path: Path) -> None:
        """Assemble should handle missing refined data gracefully."""
        config = Config(
            project_id="test_empty",
            project_name="Test Empty",
            jurisdiction="test",
            workspace_root=tmp_path,
            input_dir=tmp_path / "input",
        )

        final_md, appendices = assemble_report(config)
        assert final_md is not None
        assert len(appendices) == 3

    def test_with_data(self, tmp_path: Path) -> None:
        """Assemble with some digitised data should produce tables."""
        # Create digitised data
        dig_dir = tmp_path / "test_proj" / "01_digitised"
        dig_dir.mkdir(parents=True)
        ctx = {
            "context_number": "[001]",
            "type": "layer",
            "description": "Dark brown silty clay",
            "interpretation": "Ploughsoil",
            "period": "Post-medieval",
            "finds": [{"type": "pottery", "qty": 5, "period": "Roman", "notes": ""}],
            "samples": [],
        }
        (dig_dir / "ctx_001.json").write_text(json.dumps(ctx))

        config = Config(
            project_id="test_proj",
            project_name="Test",
            jurisdiction="test",
            workspace_root=tmp_path,
            input_dir=tmp_path / "input",
        )

        final_md, appendices = assemble_report(config, digitised_dir=dig_dir)
        assert "[001]" in appendices.get("context_register", "")


# ── Export ───────────────────────────────────────────────────────────────────


class TestExport:
    def test_export_markdown_only(self, tmp_path: Path) -> None:
        """Export should always produce at least a Markdown file."""
        config = Config(
            project_id="test_export",
            project_name="Test Export",
            jurisdiction="test",
            workspace_root=tmp_path,
            input_dir=tmp_path / "input",
        )
        result = export_report("# Test Report\nContent.", config, formats=[])
        assert "markdown" in result
        assert result["markdown"] is not None

    def test_archive_zip(self, tmp_path: Path) -> None:
        """Archive ZIP should be created."""
        config = Config(
            project_id="test_zip",
            project_name="Test ZIP",
            jurisdiction="test",
            workspace_root=tmp_path,
            input_dir=tmp_path / "input",
        )
        result = export_report("# Test Report\nContent.", config, formats=["zip"])
        assert "zip" in result


# ── Full Phase 5 Run ─────────────────────────────────────────────────────────


class TestRunPhase5:
    def test_phase5_completes(self, tmp_path: Path) -> None:
        """Phase 5 should complete and return export paths."""
        # Create minimal workspace structure
        proj_dir = tmp_path / "test_full"
        (proj_dir / "00_manifest").mkdir(parents=True)
        (proj_dir / "01_digitised").mkdir()
        (proj_dir / "02_spatial").mkdir()
        (proj_dir / "03_draft").mkdir()
        (proj_dir / "04_refined").mkdir()
        (proj_dir / "05_final").mkdir()
        (proj_dir / "assets").mkdir()
        (proj_dir / "logs").mkdir()

        config = Config(
            project_id="test_full",
            project_name="Test Full",
            jurisdiction="historic_england_cl3",
            workspace_root=tmp_path,
            input_dir=tmp_path / "input",
        )

        result = run_phase5(config, formats=["markdown"])
        assert "report_markdown" in result
        assert result["report_markdown"] != ""
