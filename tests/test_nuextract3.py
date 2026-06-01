"""test_nuextract3.py — Unit tests for NuExtract3 extractor module.

Tests the template converter, prompt construction, and response
cleaning logic. Does NOT test actual model inference (requires Ollama
with the nuextract3 model pulled).
"""

from __future__ import annotations

import json

import pytest

from erd.extractors import NuExtract3Extractor, context_sheet_template, template_to_json
from erd.extractors.nuextract3 import NUEXTRACT_SYSTEM


class TestNuExtract3Template:
    """NuExtract3 template generation and serialization."""

    def test_template_has_required_fields(self) -> None:
        """Template must contain all ContextSheet fields."""
        template = context_sheet_template()
        required = {
            "context_number", "type", "description", "interpretation",
            "cut_by", "cuts", "fills", "filled_by",
            "same_as", "period", "finds", "samples",
            "sketch_present", "review_flags",
        }
        assert required.issubset(template.keys()), f"Missing: {required - template.keys()}"

    def test_template_type_uses_enum(self) -> None:
        """The 'type' field should be an enum list in NuExtract3 format."""
        template = context_sheet_template()
        assert isinstance(template["type"], list)
        assert "layer" in template["type"]
        assert "cut" in template["type"]

    def test_template_serializes_to_json(self) -> None:
        """template_to_json should produce parseable JSON."""
        template = context_sheet_template()
        json_str = template_to_json(template)
        parsed = json.loads(json_str)
        assert parsed == template

    def test_template_finds_is_array_of_objects(self) -> None:
        """The 'finds' field should be an array of typed objects."""
        template = context_sheet_template()
        assert isinstance(template["finds"], list)
        assert len(template["finds"]) == 1
        find_schema = template["finds"][0]
        assert find_schema["qty"] == "integer"
        assert find_schema["type"] == "string"
        assert find_schema["period"] == "string"

    def test_template_sketch_present_is_yes_no_enum(self) -> None:
        """sketch_present should be a yes/no enum (NuExtract3 doesn't do bool)."""
        template = context_sheet_template()
        assert template["sketch_present"] == ["yes", "no"]

    def test_template_review_flags_is_object_array(self) -> None:
        """review_flags should have field + issue sub-fields."""
        template = context_sheet_template()
        assert isinstance(template["review_flags"], list)
        assert template["review_flags"][0]["field"] == "string"
        assert template["review_flags"][0]["issue"] == "string"


class TestNuExtract3ResponseCleaning:
    """Response cleaning strips thinking blocks and markdown fences."""

    def test_clean_plain_json(self) -> None:
        """Plain JSON should pass through unchanged."""
        text = '{"context_number": "[101]"}'
        cleaned = NuExtract3Extractor._clean_response(text)
        assert cleaned == text

    def test_clean_json_fence(self) -> None:
        """```json ... ``` fences should be stripped."""
        text = '```json\n{"context_number": "[101]"}\n```'
        cleaned = NuExtract3Extractor._clean_response(text)
        assert cleaned == '{"context_number": "[101]"}'

    def test_clean_thinking_block(self) -> None:
        """<think>...</think> blocks should be removed."""
        text = '<think>This is a context sheet from trench A.</think>{"context_number": "[101]"}'
        cleaned = NuExtract3Extractor._clean_response(text)
        assert cleaned == '{"context_number": "[101]"}'

    def test_clean_with_preamble(self) -> None:
        """Text before the first JSON brace should be stripped."""
        text = 'Here is the extracted data:\n{"context_number": "[101]"}'
        cleaned = NuExtract3Extractor._clean_response(text)
        assert cleaned == '{"context_number": "[101]"}'

    def test_clean_complex_output(self) -> None:
        """Combined thinking + fences + preamble."""
        text = """
        <think>
        The document shows context 101, a dark greyish brown silty loam.
        </think>
        ```json
        {"context_number": "[101]", "type": "layer", "description": "silty loam"}
        ```
        """
        cleaned = NuExtract3Extractor._clean_response(text)
        parsed = json.loads(cleaned)
        assert parsed["context_number"] == "[101]"
        assert parsed["type"] == "layer"


class TestNuExtract3Prompt:
    """System prompt contains essential instructions."""

    def test_system_prompt_has_extraction_instruction(self) -> None:
        """The system prompt should mention extracting fields from documents."""
        assert "Extract" in NUEXTRACT_SYSTEM
        assert "archaeological" in NUEXTRACT_SYSTEM.lower()

    def test_system_prompt_has_json_rule(self) -> None:
        """The prompt should instruct only valid JSON output."""
        assert "JSON" in NUEXTRACT_SYSTEM

    def test_system_prompt_no_invent_data(self) -> None:
        """The prompt must forbid hallucinating data."""
        assert "invent data" in NUEXTRACT_SYSTEM.lower()
