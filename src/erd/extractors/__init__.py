"""extractors — Pluggable document extraction backends for Phase 1.

Currently supported:
    - glm-ocr (default): GLM-OCR via Ollama
    - nuextract3: NuExtract3 Q4_K_M via Ollama (structured extraction specialist)

Usage:
    from erd.extractors.nuextract3 import NuExtract3Extractor, call_nuextract3

exports: NuExtract3Extractor, call_nuextract3, context_sheet_template
used_by: erd.phases.phase1
"""

from erd.extractors.nuextract3 import NuExtract3Extractor, call_nuextract3
from erd.extractors.template import context_sheet_template, template_to_json

__all__ = [
    "NuExtract3Extractor",
    "call_nuextract3",
    "context_sheet_template",
    "template_to_json",
]
