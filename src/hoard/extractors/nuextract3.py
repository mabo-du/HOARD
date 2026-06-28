"""nuextract3.py — NuExtract3 structured extraction via llama.cpp.

Runs NuExtract3 Q4_K_M GGUF directly through llama-cpp-python with GPU
acceleration (Vulkan backend). Uses the custom NuExtract3ChatHandler
custom chat handler (Strategy 5) which renders the GGUF's Jinja2 template
with ``template=<schema>`` and ``mode="structured"`` — the correct way
to activate NuExtract3's structured extraction mode.

Usage:
    extractor = NuExtract3Extractor()
    result = extractor.extract(image_path="ctx_001.png")
    # → ContextSheet dict with non-null content fields

exports: NuExtract3Extractor
         call_nuextract3()
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from hoard.extractors.template import context_sheet_template, template_to_json

logger = logging.getLogger(__name__)

# Lazy imports
_ContextSheet = None


def _get_context_sheet():
    global _ContextSheet
    if _ContextSheet is None:
        from hoard.phases.phase1 import ContextSheet as CS
        _ContextSheet = CS
    return _ContextSheet


NUEXTRACT_SYSTEM = (
    "Extract structured data from the archaeological context sheet image. "
    "Return only valid JSON matching the provided schema. "
    "Do not invent data or add fields not visible in the document. "
    "If a field is illegible or absent, set its value to null."
)

# ── Model paths ─────────────────────────────────────────────────────────────

_HF_SNAPSHOT = (
    "~/.cache/huggingface/hub/models--numind--NuExtract3-GGUF/"
    "snapshots/631a32f126925ea54d031dc1cb23c9208889c529"
)
MODEL_PATH = os.path.expanduser(os.path.join(_HF_SNAPSHOT, "NuExtract3-Q4_K_M.gguf"))
MMPROJ_PATH = os.path.expanduser(os.path.join(_HF_SNAPSHOT, "mmproj-NuExtract3-BF16.gguf"))

TEMPERATURE = 0.0
N_CTX = 16384


# ── Extractor ───────────────────────────────────────────────────────────────


class NuExtract3Extractor:
    """Structured extraction with NuExtract3 via llama.cpp + custom chat handler.

    Uses NuExtract3ChatHandler which renders the GGUF Jinja2 template with
    template= and mode="structured" kwargs, enabling proper structured
    extraction output rather than default Markdown-OCR mode.

    Caches the model in VRAM across calls. Use ``unload()`` to release.
    """

    def __init__(self) -> None:
        self._llm: Any = None
        self._handler: Any = None

    # ── Model lifecycle ──────────────────────────────────────────────────

    def _load_model(self) -> None:
        """Load NuExtract3 GGUF with mmproj + custom chat handler on GPU."""
        from llama_cpp import Llama

        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"NuExtract3 GGUF not found at {MODEL_PATH}.\n"
                "Run: huggingface-cli download numind/NuExtract3-GGUF "
                "NuExtract3-Q4_K_M.gguf mmproj-NuExtract3-BF16.gguf "
                "--local-dir ~/.cache/huggingface/hub/"
            )

        # Build the extraction schema (NuExtract3 typed template)
        from hoard.extractors.nuextract3_handler import NuExtract3ChatHandler

        schema = template_to_json(context_sheet_template())
        mmproj = MMPROJ_PATH if os.path.exists(MMPROJ_PATH) else None
        if not mmproj:
            raise FileNotFoundError(f"mmproj not found at {MMPROJ_PATH}")

        self._handler = NuExtract3ChatHandler(
            clip_model_path=mmproj,
            extraction_schema=schema,
            verbose=False,
        )

        logger.info(
            f"Loading NuExtract3 ({os.path.getsize(MODEL_PATH) / 1024**3:.1f} GB) on GPU "
            f"with custom NuExtract3ChatHandler..."
        )
        self._llm = Llama(
            model_path=MODEL_PATH,
            mmproj=mmproj,
            chat_handler=self._handler,
            n_gpu_layers=-1,
            n_ctx=N_CTX,
            verbose=False,
        )
        logger.info("NuExtract3 loaded with structured extraction handler")

    @property
    def llm(self) -> Any:
        if self._llm is None:
            self._load_model()
        return self._llm

    def is_available(self) -> bool:
        return os.path.exists(MODEL_PATH)

    def unload(self) -> None:
        if self._llm is not None:
            self._llm = None
            self._handler = None
            import gc
            gc.collect()

    # ── Extraction ───────────────────────────────────────────────────────

    def extract(
        self,
        image_path: str | Path | None = None,
        image_bytes: bytes | None = None,
        ocr_text: str | None = None,
        context_number_hint: str | None = None,
    ) -> dict[str, Any]:
        """Extract structured data from a context sheet image.

        The NuExtract3ChatHandler handles Jinja2 template rendering with
        ``template=<schema>`` and ``mode="structured"`` automatically.
        The model output is validated against ContextSheet Pydantic schema.

        Args:
            image_path: Path to context sheet PNG.
            image_bytes: PNG bytes (alternative to image_path).
            ocr_text: Raw OCR text (text-only mode — not yet supported
                      with the custom handler since it requires images
                      for the mtmd pipeline).
            context_number_hint: Optional context number hint.

        Returns:
            ContextSheet dict.
        """
        if not self.is_available():
            raise RuntimeError(
                f"NuExtract3 model not found at {MODEL_PATH}.\n"
                "Pull it with: huggingface-cli download numind/NuExtract3-GGUF "
                "NuExtract3-Q4_K_M.gguf mmproj-NuExtract3-BF16.gguf ..."
            )

        # Build content for the user message
        content: list[dict[str, Any]] = []

        if image_path:
            path = Path(image_path).resolve()
            if not path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")
            content.append({
                "type": "image_url",
                "image_url": {"url": path.as_uri()},
            })
        elif image_bytes:
            import base64
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })
        else:
            raise ValueError("image_path or image_bytes is required for the mtmd pipeline")

        # The handler's extraction_schema is already set during __init__.
        # The context_number_hint and ocr_text go into the user text.
        text_parts = []
        if context_number_hint:
            text_parts.append(f"Context sheet number: {context_number_hint}.")
        if ocr_text:
            text_parts.append(f"OCR text from document:\n{ocr_text}")
        if text_parts:
            content.append({"type": "text", "text": " ".join(text_parts)})

        messages = [{"role": "user", "content": content}]

        response = self.llm.create_chat_completion(
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=4096,
        )

        raw = response["choices"][0]["message"]["content"] or ""
        response_text = self._clean_response(raw)

        try:
            ContextSheet = _get_context_sheet()
            parsed = ContextSheet.model_validate_json(response_text)
            parsed.model = "nuextract3"
            return parsed.model_dump()
        except Exception as e:
            logger.warning(f"NuExtract3 validation failed: {e}")
            logger.debug(f"Raw response: {response_text[:500]}")
            raise

    @staticmethod
    def _clean_response(text: str) -> str:
        import re as _re
        text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL)
        text = _re.sub(r"```(?:json)?\s*", "", text)
        text = _re.sub(r"\s*```", "", text)
        text = text.strip()
        first = text.find("{")
        if first > 0:
            text = text[first:]
        last = text.rfind("}")
        if last > 0:
            text = text[: last + 1]
        return text


# ── Standalone (drop-in for _call_glm_ocr) ──────────────────────────────────


def call_nuextract3(
    image_bytes: bytes,
    system_prompt: str = "",
    context_number_hint: str | None = None,
) -> dict[str, Any]:
    """Drop-in replacement for ``_call_glm_ocr``."""
    extractor = NuExtract3Extractor()
    return extractor.extract(
        image_bytes=image_bytes,
        context_number_hint=context_number_hint,
    )
