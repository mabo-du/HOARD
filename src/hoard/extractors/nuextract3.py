"""nuextract3.py — NuExtract3 structured extraction via Ollama.

Runs the NuExtract3 Q4_K_M GGUF model through Ollama's API (which handles
GPU inference). The model is a 4B-parameter vision-language model fine-tuned
via reinforcement learning for structured document extraction.

This module provides a drop-in replacement for ``_call_glm_ocr()`` in
``hoard.phases.phase1`` with the same interface: image_bytes + system_prompt
→ ContextSheet dict.

NuExtract3 achieves ~0.651 on structured extraction benchmarks vs ~0.435
for GLM-4.6V-Flash (the closest model to GLM-OCR), and 56% better schema
adherence than the base Qwen3.5-4B.

Usage:
    extractor = NuExtract3Extractor()
    result = extractor.extract(image_bytes, system_prompt)
    # result is a ContextSheet dict

Dependencies:
    - Ollama running at http://localhost:11434
    - Model registered as ``nuextract3`` (via Modelfile from GGUF)
    - ``requests``

exports: NuExtract3Extractor
         call_nuextract3()  (standalone function, same sig as _call_glm_ocr)
used_by: hoard.phases.phase1  (when extractor="nuextract3")
"""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

from hoard.extractors.template import context_sheet_template, template_to_json
from hoard.phases.phase1 import ContextSheet

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = "http://localhost:11434"
NUEXTRACT3_MODEL = "nuextract3"

# The Ollama model name for NuExtract3 from HuggingFace registry
# Falls back to local 'nuextract3' if the HF one isn't pulled
HF_MODEL = "hf.co/numind/NuExtract3-GGUF:Q4_K_M"

TIMEOUT = 180  # seconds — NuExtract3 can be slow on first load
TEMPERATURE = 0.0  # Greedy decoding for deterministic extraction

# ── NuExtract3 System Prompt ────────────────────────────────────────────────

NUEXTRACT_SYSTEM = (
    "You are an archaeological document digitisation system. "
    "Extract the specified fields from the input and output valid JSON "
    "matching the provided template exactly.\n\n"
    "Rules:\n"
    "1. Output ONLY valid JSON — no preamble, no explanation, no markdown.\n"
    "2. Use standard archaeological terminology.\n"
    "3. Context numbers must use square brackets, e.g. [101].\n"
    "4. If handwriting is illegible or ambiguous, provide your best estimate.\n"
    "5. If a field is not visible, use null or [] as appropriate.\n"
    "6. DO NOT invent data.\n"
    "7. For 'type', use standard archaeological context types.\n"
    "8. For sketch_present, return \"yes\" or \"no\" (string)."
)

_EXTRACTION_INSTRUCTION = (
    "\n\nExtract the following fields from the document and output "
    "valid JSON exactly matching this template:\n{template}"
)


# ── Main Extractor ──────────────────────────────────────────────────────────


class NuExtract3Extractor:
    """Structured document extraction using NuExtract3 via Ollama.

    Handles model availability checks, prompt construction, response
    parsing, and graceful fallbacks.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or self._resolve_model()
        self._checked_availability = False
        self._available = False

    @staticmethod
    def _resolve_model() -> str:
        """Return the first available NuExtract3 model name.

        Checks the HuggingFace-registry model first, then the local one.
        """
        # Check both model names
        for name in (HF_MODEL, NUEXTRACT3_MODEL):
            try:
                resp = requests.get(
                    f"{OLLAMA_BASE_URL}/api/show",
                    json={"name": name},
                    timeout=10,
                )
                if resp.status_code == 200 and resp.json().get("modelfile"):
                    logger.info(f"Using NuExtract3 model: {name}")
                    return name
            except (requests.RequestException, ValueError):
                continue

        logger.warning("NuExtract3 model not found in Ollama — will try nuextract3 as fallback")
        return NUEXTRACT3_MODEL

    def is_available(self) -> bool:
        """Check if the NuExtract3 model is registered in Ollama."""
        if self._checked_availability:
            return self._available

        try:
            resp = requests.get(
                f"{OLLAMA_BASE_URL}/api/show",
                json={"name": self.model_name},
                timeout=10,
            )
            self._available = resp.status_code == 200
        except requests.RequestException:
            self._available = False

        self._checked_availability = True
        return self._available

    def extract(
        self,
        image_bytes: bytes | None = None,
        ocr_text: str | None = None,
        context_number_hint: str | None = None,
    ) -> dict[str, Any]:
        """Run NuExtract3 extraction and return a validated ContextSheet dict.

        Args:
            image_bytes: Optional PNG image bytes (for vision-capable setups).
            ocr_text: Optional OCR text (for text-only extraction).
            context_number_hint: Optional context number hint.

        Returns:
            Dict matching ContextSheet schema, or raises on failure.

        At least one of image_bytes or ocr_text must be provided.
        """
        if not self.is_available():
            raise RuntimeError(
                f"NuExtract3 model '{self.model_name}' not found in Ollama. "
                f"Run: ollama pull {HF_MODEL}"
            )

        # Build the NuExtract3 typed template
        template = context_sheet_template()
        template_str = template_to_json(template)

        # Build the user message
        user_message = NUEXTRACT_SYSTEM
        user_message += _EXTRACTION_INSTRUCTION.format(template=template_str)

        if context_number_hint:
            user_message += f"\n\nThis is context sheet number {context_number_hint}."

        if ocr_text:
            user_message += f"\n\nOCR text from document:\n{ocr_text}"

        # Prepare the Ollama request
        url = f"{OLLAMA_BASE_URL}/api/generate"
        payload: dict[str, Any] = {
            "model": self.model_name,
            "prompt": user_message,
            "stream": False,
            "options": {
                "temperature": TEMPERATURE,
                "num_ctx": 16384,
            },
            "keep_alive": -1,  # Lock in VRAM during batch
        }

        # Add image if provided (vision mode)
        if image_bytes:
            b64_image = base64.b64encode(image_bytes).decode("utf-8")
            payload["images"] = [b64_image]

        # Send request
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        result = resp.json()
        response_text = result.get("response", "").strip()

        # NuExtract3 sometimes wraps JSON in ```json ... ``` or <think>...</think>
        response_text = self._clean_response(response_text)

        # Parse and validate with Pydantic
        try:
            parsed = ContextSheet.model_validate_json(response_text)
            parsed.model = "nuextract3"
            return parsed.model_dump()
        except Exception as e:
            logger.warning(f"NuExtract3 validation failed: {e}")
            logger.debug(f"Raw response: {response_text[:500]}")
            raise

    @staticmethod
    def _clean_response(text: str) -> str:
        """Remove markdown fences and thinking blocks from model output."""
        # Remove <think>...</think> blocks
        import re as _re

        text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL)
        text = _re.sub(r"<Thought>.*?</Thought>", "", text, flags=_re.DOTALL)

        # Remove ```json ... ``` fences
        text = _re.sub(r"```(?:json)?\s*", "", text)
        text = _re.sub(r"\s*```", "", text)

        # Remove leading/trailing whitespace and non-JSON prefixes
        text = text.strip()

        # If text starts with anything other than '{' or '[', try to find JSON
        first_brace = text.find("{")
        if first_brace > 0:
            text = text[first_brace:]

        last_brace = text.rfind("}")
        if last_brace > 0:
            text = text[: last_brace + 1]

        return text

    def extract_from_ocr(
        self,
        ocr_text: dict[str, Any] | str,
        context_number_hint: str | None = None,
    ) -> dict[str, Any]:
        """Extract from existing OCR output (text-only, no vision).

        Takes the string representation of GLM-OCR output and re-extracts
        structured data using NuExtract3's superior schema adherence.

        Args:
            ocr_text: GLM-OCR output dict or raw text string.
            context_number_hint: Optional context number hint.

        Returns:
            Validated ContextSheet dict.
        """
        if isinstance(ocr_text, dict):
            text = json.dumps(ocr_text, indent=2)
        else:
            text = str(ocr_text)

        return self.extract(
            image_bytes=None,
            ocr_text=text,
            context_number_hint=context_number_hint,
        )


# ── Standalone Function (drop-in for _call_glm_ocr) ─────────────────────────


def call_nuextract3(
    image_bytes: bytes,
    system_prompt: str,
    context_number_hint: str | None = None,
) -> dict[str, Any]:
    """Standalone NuExtract3 extraction — same signature as _call_glm_ocr.

    Args:
        image_bytes: Preprocessed PNG image bytes (may be ignored in text-only
                     mode if OCR text is embedded in the system_prompt).
        system_prompt: The extraction instructions.
        context_number_hint: Optional context number.

    Returns:
        ContextSheet dict, or raises on failure.
    """
    extractor = NuExtract3Extractor()
    return extractor.extract(
        image_bytes=image_bytes,
        ocr_text=None,
        context_number_hint=context_number_hint,
    )
