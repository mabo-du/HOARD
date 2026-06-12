"""test_phase4.py — Unit tests for Phase 4: Compliance Refinement.

Tests: prohibited term detection, section parsing, word counting,
template loading. No GPU or Ollama required.

exports: (test functions)
used_by: pytest
rules:   Must not require GPU or real model inference.
agent:   deepseek-v4-pro | 2026-05-25 | t020 | Phase 4 unit tests
"""

from __future__ import annotations

import tempfile
from pathlib import Path


from hoard.phases.phase4 import (
    _build_compliance_prompt,
    _check_prohibited_terms,
    _count_words,
    _find_latest_draft,
    _load_template,
    _parse_sections_from_draft,
)

# ═══════════════════════════════════════════════════════════════════════════════
# _load_template
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoadTemplate:
    def test_loads_historic_england(self):
        """The real template should load from the templates/ directory."""
        template = _load_template("historic_england_cl3")
        assert template is not None
        assert "jurisdiction" in template
        assert "Historic England" in template["jurisdiction"]
        assert "mandatory_sections" in template

    def test_returns_none_for_missing(self):
        result = _load_template("nonexistent_template_xyz")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# _find_latest_draft
# ═══════════════════════════════════════════════════════════════════════════════

class TestFindLatestDraft:
    def test_finds_latest_file(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "draft_20260524_203058.md").write_text("older")
            (tmp / "draft_20260524_203126.md").write_text("newer content")
            result = _find_latest_draft(tmp)
            assert result is not None
            assert "newer content" in result

    def test_handles_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            result = _find_latest_draft(Path(d))
            assert result is None

    def test_handles_nonexistent_dir(self):
        result = _find_latest_draft(Path("/nonexistent/dir"))
        assert result is None

    def test_returns_none_for_non_md_files(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "data.txt").write_text("text")
            result = _find_latest_draft(tmp)
            assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# _parse_sections_from_draft
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseSectionsFromDraft:
    def test_single_section(self):
        text = "##section:introduction\n## Introduction\nSite details.\nMore text."
        result = _parse_sections_from_draft(text)
        assert "introduction" in result
        assert "Introduction" in result["introduction"]

    def test_multiple_sections(self):
        text = (
            "##section:intro\n## Introduction\nDetails.\n\n"
            "##section:method\n## Methodology\nMethods.\n\n"
            "##section:results\n## Results\nFindings."
        )
        result = _parse_sections_from_draft(text)
        assert len(result) == 3
        assert "intro" in result
        assert "method" in result
        assert "results" in result

    def test_closing_section(self):
        """The last section without a following label should still be captured."""
        text = "##section:discussion\n## Discussion\nFinal thoughts."
        result = _parse_sections_from_draft(text)
        assert "discussion" in result
        assert "Final thoughts" in result["discussion"]

    def test_empty_text(self):
        assert _parse_sections_from_draft("") == {}

    def test_no_section_labels(self):
        text = "## Just a heading\nContent without sections."
        result = _parse_sections_from_draft(text)
        assert result == {}

    def test_preamble_not_included(self):
        text = "Some preamble.\n##section:main\n## Main\nContent."
        result = _parse_sections_from_draft(text)
        assert "main" in result
        assert "preamble" not in str(result).lower()


# ═══════════════════════════════════════════════════════════════════════════════
# _count_words
# ═══════════════════════════════════════════════════════════════════════════════

class TestCountWords:
    def test_simple_sentence(self):
        assert _count_words("Hello world") == 2

    def test_longer_text(self):
        text = "The quick brown fox jumps over the lazy dog"
        assert _count_words(text) == 9

    def test_empty_string(self):
        assert _count_words("") == 0  # split("") returns []

    def test_whitespace_only(self):
        assert _count_words("   ") == 0  # split() handles this

    def test_multiple_spaces(self):
        assert _count_words("a   b   c") == 3

    def test_newlines(self):
        assert _count_words("line one\nline two\nline three") == 6

    def test_single_word(self):
        assert _count_words("word") == 1

    def test_punctuation_attached(self):
        assert _count_words("Hello, world!") == 2


# ═══════════════════════════════════════════════════════════════════════════════
# _check_prohibited_terms
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckProhibitedTerms:
    def test_detects_significant(self):
        flags = _check_prohibited_terms(
            "This is a significant discovery.",
            ["significant"],
        )
        assert len(flags) == 1
        assert flags[0]["term"] == "significant"

    def test_case_insensitive(self):
        flags = _check_prohibited_terms(
            "A Significant find was unearthed.",
            ["significant"],
        )
        assert len(flags) == 1

    def test_multiple_occurrences(self):
        flags = _check_prohibited_terms(
            "This is a significant and very significant find.",
            ["significant"],
        )
        assert len(flags) >= 2

    def test_multiple_terms(self):
        flags = _check_prohibited_terms(
            "A unique and important find. Extremely significant.",
            ["significant", "unique", "important finds", "extremely", "very significant"],
        )
        assert len(flags) > 1

    def test_no_match(self):
        flags = _check_prohibited_terms(
            "The pottery assemblage dates to the 2nd century.",
            ["significant", "unique"],
        )
        assert len(flags) == 0

    def test_empty_terms_list(self):
        flags = _check_prohibited_terms("text with significant", None)
        assert len(flags) == 0

    def test_empty_terms_list_empty_list(self):
        flags = _check_prohibited_terms("text", [])
        assert len(flags) == 0

    def test_multi_word_term(self):
        flags = _check_prohibited_terms(
            "These are very significant findings.",
            ["very significant"],
        )
        assert len(flags) == 1
        assert flags[0]["term"] == "very significant"

    def test_multi_word_term_partial(self):
        """'very significant findings' contains 'very significant'."""
        flags = _check_prohibited_terms(
            "very significant findings here",
            ["very significant"],
        )
        assert len(flags) == 1

    def test_includes_context(self):
        flags = _check_prohibited_terms(
            "The assemblage represents an important finds assemblage.",
            ["important finds"],
        )
        assert len(flags) == 1
        assert "context" in flags[0]
        assert "important finds" in flags[0]["context"]

    def test_historic_england_prohibited_terms(self):
        """Real-world test with Historic England CL3 prohibited terms."""
        he_terms = ["significant", "unique", "important finds", "extremely", "very significant"]
        text = (
            "A significant medieval boundary ditch was identified. "
            "This is a unique find in the local area. "
            "The assemblage represents an important finds group."
        )
        flags = _check_prohibited_terms(text, he_terms)
        assert len(flags) >= 3  # significant, unique, important finds


# ═══════════════════════════════════════════════════════════════════════════════
# _build_compliance_prompt
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildCompliancePrompt:
    def test_includes_section_content(self):
        prompt = _build_compliance_prompt(
            section_id="introduction",
            section_label="Introduction",
            section_content="## Introduction\nSite description.",
            required_fields=["project_name", "ngr"],
            prohibited_terms=["significant"],
        )
        assert "introduction" in prompt.lower()
        assert "Site description" in prompt

    def test_includes_section_label(self):
        prompt = _build_compliance_prompt(
            section_id="methodology",
            section_label="Methodology",
            section_content="## Methodology\nMethods.",
            required_fields=None,
            prohibited_terms=None,
        )
        assert "Methodology" in prompt

    def test_includes_required_fields(self):
        prompt = _build_compliance_prompt(
            section_id="intro",
            section_label="Introduction",
            section_content="Content.",
            required_fields=["project_name", "ngr", "planning_authority"],
            prohibited_terms=None,
        )
        assert "project_name" in prompt
        assert "ngr" in prompt

    def test_includes_prohibited_terms(self):
        prompt = _build_compliance_prompt(
            section_id="results",
            section_label="Results",
            section_content="A significant find.",
            required_fields=None,
            prohibited_terms=["significant", "unique"],
        )
        assert "significant" in prompt or "prohibited" in prompt.lower()

    def test_outputs_section_id_header(self):
        prompt = _build_compliance_prompt(
            section_id="discussion",
            section_label="Discussion",
            section_content="Some discussion.",
            required_fields=[],
            prohibited_terms=[],
        )
        assert "section:discussion" in prompt
