"""test_template_engine.py — Unit tests for the jurisdiction template engine.

Tests: template loading, merging (extends), mandatory section checking,
required field detection, prohibited term scanning, heading style,
figure caption format, word count checks.

exports: (test functions)
used_by: pytest
rules:   Must not require GPU or real model inference.
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Template engine tests
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from erd.templates.engine import ComplianceFinding, TemplateEngine

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def engine(tmp_path: Path) -> TemplateEngine:
    return TemplateEngine(template_dir=tmp_path)


@pytest.fixture
def he_template(tmp_path: Path) -> dict:
    """Create a minimal Historic England-style template for testing."""
    template = {
        "jurisdiction": "Test — Historic England Evaluation",
        "version": "2024",
        "mandatory_sections": [
            {"id": "executive_summary", "label": "Executive Summary", "max_words": 300,
             "required_fields": ["project_name", "ngr", "dates", "key_findings"]},
            {"id": "introduction", "label": "Introduction",
             "required_fields": ["project_name", "site_location"]},
            {"id": "results", "label": "Results",
             "sub_sections": ["prehistoric", "roman"], "required_per_sub": ["context_list"]},
            {"id": "discussion", "label": "Discussion"},
            {"id": "bibliography", "label": "Bibliography"},
        ],
        "prohibited_terms": ["significant", "unique"],
        "heading_style": "sentence_case",
        "figure_caption_format": "Fig. {n}: {description}.",
    }
    (tmp_path / "test_he.yaml").write_text(yaml.dump(template))
    return template


# ── Loading ──────────────────────────────────────────────────────────────────


class TestTemplateLoading:
    def test_load_existing(self, engine: TemplateEngine, he_template: dict) -> None:
        template = engine.load_template("test_he")
        assert template is not None
        assert template["jurisdiction"] == "Test — Historic England Evaluation"

    def test_load_missing(self, engine: TemplateEngine) -> None:
        template = engine.load_template("nonexistent")
        assert template is None

    def test_list_templates(self, engine: TemplateEngine, he_template: dict) -> None:
        templates = engine.list_templates()
        assert len(templates) == 1
        assert templates[0]["code"] == "test_he"

    def test_load_invalid_yaml(self, engine: TemplateEngine, tmp_path: Path) -> None:
        (tmp_path / "bad.yaml").write_text("{{{invalid yaml: [")
        template = engine.load_template("bad")
        assert template is None


# ── Template Merging ─────────────────────────────────────────────────────────


class TestTemplateMerging:
    def test_extends_merge(self, engine: TemplateEngine, tmp_path: Path) -> None:
        parent = {
            "jurisdiction": "Parent",
            "version": "2023",
            "mandatory_sections": [
                {"id": "executive_summary", "label": "Exec Summary", "required_fields": ["a"]},
                {"id": "intro", "label": "Intro", "required_fields": ["b"]},
            ],
            "prohibited_terms": ["bad", "worse"],
            "heading_style": "sentence_case",
        }
        child = {
            "jurisdiction": "Child",
            "version": "2024",
            "extends": "parent",
            "mandatory_sections": [
                {"id": "executive_summary", "label": "Exec Summary", "required_fields": ["a", "c"]},
                {"id": "new_section", "label": "New", "required_fields": ["d"]},
            ],
            "prohibited_terms": ["bad"],
        }
        (tmp_path / "parent.yaml").write_text(yaml.dump(parent))
        (tmp_path / "child.yaml").write_text(yaml.dump(child))

        merged = engine.get_extended_template("child")
        assert merged is not None
        assert merged["jurisdiction"] == "Child"           # Child wins
        assert merged["version"] == "2024"                 # Child wins

        # Sections: child overrides parent by id, adds new ones
        section_ids = [s["id"] for s in merged["mandatory_sections"]]
        assert "executive_summary" in section_ids
        assert "intro" in section_ids                     # From parent
        assert "new_section" in section_ids                # From child

        # executive_summary's required_fields should merge (child wins for that section id)
        exec_section = next(s for s in merged["mandatory_sections"] if s["id"] == "executive_summary")
        assert "c" in exec_section["required_fields"]

        # Prohibited terms: child overrides parent
        assert "bad" in merged["prohibited_terms"]
        assert "worse" not in merged["prohibited_terms"]   # Parent's removed by child override

        # Merged field from parent
        assert merged["heading_style"] == "sentence_case"


# ── Mandatory Section Checking ────────────────────────────────────────────────


class TestMandatorySections:
    def test_all_present(self, engine: TemplateEngine, he_template: dict) -> None:
        draft = """```section:executive_summary
## Executive Summary
Project Name: Stoneyfield Farm.
NGR: TL 1234 5678.
Fieldwork dates: May 2026.
Key findings: A Roman ditch.
```section:introduction
## Introduction
Project Name: Stoneyfield Farm.
Site Location: Cambridge.
```section:results
## Results
Results content.
```section:discussion
## Discussion
Discussion content.
```section:bibliography
## Bibliography
References.
"""
        report = engine.check_all(draft, "test_he")
        assert report.passed
        assert len(report.errors) == 0

    def test_missing_section(self, engine: TemplateEngine, he_template: dict) -> None:
        draft = """```section:executive_summary
## Executive Summary
```section:introduction
## Introduction
```
"""  # Missing results, discussion, bibliography
        report = engine.check_all(draft, "test_he")
        assert not report.passed
        assert any(f.finding_type == "missing_section" for f in report.errors)

    def test_section_via_heading_fallback(self, engine: TemplateEngine, he_template: dict) -> None:
        """Phase 3 sections identified by ## headings should still be found."""
        draft = """## Executive Summary
Project Name: Stoneyfield Farm.
NGR: TL 1234 5678.
Fieldwork dates: May 2026.
Key findings: A Roman ditch.
## Introduction
Project Name: Stoneyfield Farm.
Site Location: Cambridge.
## Results
Results content.
## Discussion
Discussion content.
## Bibliography
References.
"""
        report = engine.check_all(draft, "test_he")
        assert report.passed


# ── Required Fields ──────────────────────────────────────────────────────────


class TestRequiredFields:
    def test_required_field_present(self, engine: TemplateEngine, he_template: dict) -> None:
        draft = """```section:executive_summary
## Executive Summary
Project Name: Stoneyfield Farm.
NGR: TL 1234 5678.
Fieldwork dates: May 2026.
Key findings: A Roman ditch.
```
"""
        report = engine.check_all(draft, "test_he")
        exec_errors = [f for f in report.errors if f.section_id == "executive_summary"]
        assert len(exec_errors) == 0

    def test_required_field_missing(self, engine: TemplateEngine, he_template: dict) -> None:
        draft = """```section:executive_summary
## Executive Summary
Some text but missing several required fields.
```
"""
        report = engine.check_all(draft, "test_he")
        exec_errors = [f for f in report.errors if f.section_id == "executive_summary"]
        assert len(exec_errors) > 0
        assert any("project_name" in str(f.field) for f in exec_errors)


# ── Prohibited Terms ─────────────────────────────────────────────────────────


class TestProhibitedTerms:
    def test_detects_prohibited(self, engine: TemplateEngine, he_template: dict) -> None:
        draft = "This was a significant find. The assemblage was unique."
        report = engine.check_all(draft, "test_he")
        prohibited = [f for f in report.findings if f.finding_type == "prohibited_term"]
        assert len(prohibited) == 2

    def test_clean_draft(self, engine: TemplateEngine, he_template: dict) -> None:
        draft = "This was a notable find. The assemblage was uncommon."
        report = engine.check_all(draft, "test_he")
        prohibited = [f for f in report.findings if f.finding_type == "prohibited_term"]
        assert len(prohibited) == 0


# ── Heading Style ────────────────────────────────────────────────────────────


class TestHeadingStyle:
    def test_sentence_case_ok(self, engine: TemplateEngine, he_template: dict) -> None:
        draft = "## Executive Summary\n## Introduction\n## Results\n"
        report = engine.check_all(draft, "test_he")
        style_issues = [f for f in report.findings if f.finding_type == "heading_style"]
        assert len(style_issues) == 0

    def test_all_caps_detected(self, engine: TemplateEngine, he_template: dict) -> None:
        draft = "## EXECUTIVE SUMMARY\n"
        report = engine.check_all(draft, "test_he")
        style_issues = [f for f in report.findings if f.finding_type == "heading_style"]
        assert len(style_issues) == 1

    def test_sentence_case_violation(self, engine: TemplateEngine, he_template: dict) -> None:
        draft = "## EXECUTIVE SUMMARY\n## INTRODUCTION\n"
        report = engine.check_all(draft, "test_he")
        style_issues = [f for f in report.findings if f.finding_type == "heading_style"]
        assert len(style_issues) > 0


# ── Executive Summary Word Count ─────────────────────────────────────────────


class TestWordCount:
    def test_within_limit(self, engine: TemplateEngine, he_template: dict) -> None:
        words = "word " * 50  # 50 words, well within 300 limit
        draft = f"```section:executive_summary\n## Executive Summary\n{words}\n```\n"
        report = engine.check_all(draft, "test_he")
        wc_issues = [f for f in report.findings if f.finding_type == "word_count"]
        assert len(wc_issues) == 0

    def test_exceeds_limit(self, engine: TemplateEngine, he_template: dict) -> None:
        words = "word " * 400  # 400 words, over 300 limit
        draft = f"```section:executive_summary\n## Executive Summary\n{words}\n```\n"
        report = engine.check_all(draft, "test_he")
        wc_issues = [f for f in report.findings if f.finding_type == "word_count"]
        assert len(wc_issues) == 1


# ── ComplianceFinding ────────────────────────────────────────────────────────


class TestComplianceFinding:
    def test_to_dict(self) -> None:
        f = ComplianceFinding("exec", "missing_field", "error", "Field not found", field="project_name")
        d = f.to_dict()
        assert d["section_id"] == "exec"
        assert d["type"] == "missing_field"
        assert d["severity"] == "error"
        assert d["field"] == "project_name"
