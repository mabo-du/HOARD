"""template.py — Pydantic model → NuExtract3 template converter.

NuExtract3 uses a typed JSON template where leaf values describe the
expected output type instead of the value itself:

    {"field_name": "string", "qty": "integer"}

Supported types: verbatim-string, string, integer, number, date-time,
["enum1", "enum2"], ["string"], [{"field": "type"}], etc.

This module provides the ContextSheet template and a generic converter.

exports: context_sheet_template() -> dict
         template_to_json(template) -> str
used_by: hoard.extractors.nuextract3
"""

from __future__ import annotations

import json
from typing import Any

_CONTEXT_SHEET_TEMPLATE: dict[str, Any] = {
    "context_number": "verbatim-string",
    "type": [
        "layer", "cut", "deposit", "fill", "structure",
        "pit", "ditch", "posthole", "wall", "floor",
        "surface", "grave", "hearth", "burial",
    ],
    "cut_by": ["verbatim-string"],
    "cuts": ["verbatim-string"],
    "same_as": "verbatim-string",
    "fills": ["verbatim-string"],
    "filled_by": ["verbatim-string"],
    "description": "string",
    "interpretation": "string",
    "period": [
        "palaeolithic", "mesolithic", "neolithic",
        "bronze_age", "iron_age", "roman",
        "early_medieval", "medieval",
        "post_medieval", "modern",
        "undated", "unknown",
    ],
    "finds": [
        {
            "type": "string",
            "qty": "integer",
            "period": "string",
            "notes": "string",
        },
    ],
    "samples": [
        {
            "id": "verbatim-string",
            "type": "string",
            "notes": "string",
        },
    ],
    "sketch_present": ["yes", "no"],
    "review_flags": [
        {
            "field": "string",
            "issue": "string",
        },
    ],
}


def context_sheet_template() -> dict[str, Any]:
    """Return the NuExtract3 typed template for archaeological context sheets.

    The returned dict can be converted to JSON and passed as the
    structured extraction template in the NuExtract3 prompt.
    """
    return dict(_CONTEXT_SHEET_TEMPLATE)  # Return a copy to prevent mutation


def template_to_json(template: dict[str, Any]) -> str:
    """Serialize a NuExtract3 template to an indented JSON string.

    The result is embedded in the extraction prompt so the model outputs
    JSON matching this structure with the correct types.
    """
    return json.dumps(template, indent=2, ensure_ascii=False)


__all__ = [
    "context_sheet_template",
    "template_to_json",
]
