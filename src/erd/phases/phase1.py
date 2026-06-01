"""phase1.py — Multi-Modal Digitisation.

Converts scanned archaeological documents into structured JSON using
specialised Vision-Language Models. Three routing paths:

  Route 1a — Context sheets (handwritten forms): GLM-OCR via Ollama
              with Pydantic structured output enforcement (default).
  Route 1b — Context sheets (handwritten forms): NuExtract3 Q4_K_M via
              Ollama (opt-in with --extractor nuextract3). Better schema
              adherence (+56%) but requires model pull first.
  Route 2 — Finds catalogues (typed tables): Docling with Granite-Docling-258M.
  Route 3 — Existing typed notes: Docling CPU parser (zero VRAM).

Degraded documents are pre-processed with OpenCV (CLAHE, deskew,
adaptive threshold) before VLM inference.

VRAM management uses Ollama's keep_alive parameter for deterministic
model loading/unloading rather than llama.cpp router mode (which has
race conditions on constrained 8GB hardware).

exports: run_phase1(config) -> dict  — executes digitisation
used_by: erd.cli.run  → orchestrator
"""

from __future__ import annotations

import base64
import gc
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import re
import requests
from docling.document_converter import DocumentConverter
from pydantic import BaseModel, Field

from erd.config import Config

logger = logging.getLogger(__name__)

# Lazy import for NuExtract3 (keeps CLI startup fast — only imported when needed)
_NUEXTRACT3_AVAILABLE = False
try:
    from erd.extractors.nuextract3 import NuExtract3Extractor
    _NUEXTRACT3_AVAILABLE = True
except ImportError:
    pass

# ── Constants ──────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = "http://localhost:11434"
GLM_OCR_MODEL = "glm-ocr:latest"
QWEN_VL_FALLBACK = "qwen3-vl:8b"  # Fallback for degraded documents

# GLM-OCR requires 16K+ context for image processing
GLM_CTX_SIZE = 16384
GLM_TIMEOUT = 120
GLM_TEMPERATURE = 0.0  # Greedy decoding for deterministic extraction

# Image pre-processing
MAX_IMAGE_DIMENSION = 2048  # Longest edge in pixels

# ── Pydantic Schemas (Structured Output) ──────────────────────────────────────


class Find(BaseModel):
    type: str = Field(description="Type of find (e.g. pottery, animal_bone, CBM, glass)")
    qty: int = Field(description="Quantity of finds")
    period: str = Field(description="Chronological period")
    notes: str = Field(default="", description="Additional notes")


class ContextSheet(BaseModel):
    source_file: str = Field(description="Original source filename")
    model: str = Field(default="glm-ocr", description="Model used for extraction")
    schema_version: str = Field(default="1.0.0", description="Schema contract version")
    context_number: str = Field(description="Context number, e.g. [101]")
    type: str = Field(description="Context type: layer, cut, deposit, structure, etc.")
    cut_by: list[str] = Field(default_factory=list, description="Contexts that cut this one")
    cuts: list[str] = Field(default_factory=list, description="Contexts this one cuts")
    same_as: str | None = Field(default=None, description="Equivalent context number")
    fills: list[str] = Field(default_factory=list, description="Contexts that fill this one")
    filled_by: list[str] = Field(default_factory=list, description="Contexts this one fills")
    description: str = Field(description="Sedimentological description")
    interpretation: str = Field(description="Archaeological interpretation")
    period: str = Field(default="Unknown", description="Chronological period assignment")
    finds: list[Find] = Field(default_factory=list)
    samples: list[dict[str, str]] = Field(default_factory=list)
    sketch_present: bool = Field(default=False)
    review_flags: list[dict[str, str]] = Field(
        default_factory=list,
        description="Low-confidence or ambiguous fields requiring human review",
    )


# ── Image Pre-processing (CPU, zero VRAM) ────────────────────────────────────


def _preprocess_image(image_path: Path, quality_flags: dict | None = None) -> bytes:
    """Apply OpenCV pre-processing to degraded document images.

    Runs entirely on CPU. Returns PNG bytes ready for Base64 encoding.
    """
    import cv2

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")

    flags = quality_flags or {}

    # 1. Deskew (SKEW_HIGH)
    if flags.get("flag") == "SKEW_HIGH":
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=200)
        if lines is not None:
            angles = []
            for rho, theta in lines[:, 0]:
                angle = abs(theta * 180 / np.pi - 90)
                if angle < 45:
                    angles.append(angle)
            if angles:
                median_angle = np.median(angles) - 0
                if abs(median_angle) > 0.5:
                    h, w = img.shape[:2]
                    center = (w // 2, h // 2)
                    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                    img = cv2.warpAffine(
                        img, M, (w, h),
                        flags=cv2.INTER_CUBIC,
                        borderMode=cv2.BORDER_REPLICATE,
                    )

    # 2. Contrast enhancement (EXPOSURE_LOW)
    if flags.get("flag") in ("EXPOSURE_LOW", None):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        img = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    # 3. Resize if too large
    h, w = img.shape[:2]
    if max(h, w) > MAX_IMAGE_DIMENSION:
        scale = MAX_IMAGE_DIMENSION / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # Encode to PNG bytes
    _, encoded = cv2.imencode(".png", img)
    return encoded.tobytes()


# ── Ollama / VLM API ─────────────────────────────────────────────────────────


def _call_glm_ocr(
    image_bytes: bytes,
    system_prompt: str,
    context_number_hint: str | None = None,
) -> dict[str, Any]:
    """Call GLM-OCR via Ollama with structured output and image input.

    Returns parsed ContextSheet dict, or raises on validation failure.
    """
    # Base64 encode the image
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    prompt = system_prompt
    if context_number_hint:
        prompt += f"\n\nThis is context sheet number {context_number_hint}."

    # Build request with image
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": GLM_OCR_MODEL,
        "prompt": prompt,
        "images": [b64_image],
        "format": ContextSheet.model_json_schema(),
        "options": {
            "temperature": GLM_TEMPERATURE,
            "num_ctx": GLM_CTX_SIZE,
        },
        "stream": False,
        "keep_alive": -1,  # Lock in VRAM during batch processing
    }

    resp = requests.post(url, json=payload, timeout=GLM_TIMEOUT)
    resp.raise_for_status()
    result = resp.json()
    response_text = result.get("response", "")

    # Parse and validate with Pydantic
    try:
        parsed = ContextSheet.model_validate_json(response_text)
        return parsed.model_dump()
    except Exception as e:
        logger.warning(f"GLM-OCR validation failed: {e}")
        raise


def _call_vlm_fallback(image_bytes: bytes, system_prompt: str) -> dict[str, Any]:
    """Fallback: call Qwen3-VL-8B via Ollama when GLM-OCR fails.

    Less strict schema adherence but better resilience on degraded docs.
    """
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": QWEN_VL_FALLBACK,
        "prompt": system_prompt,
        "images": [b64_image],
        "format": ContextSheet.model_json_schema(),
        "options": {
            "temperature": 0.1,
            "num_ctx": 32768,
        },
        "stream": False,
        "keep_alive": -1,
    }

    resp = requests.post(url, json=payload, timeout=180)
    resp.raise_for_status()
    response_text = resp.json().get("response", "")

    try:
        parsed = ContextSheet.model_validate_json(response_text)
        parsed.model = QWEN_VL_FALLBACK
        if not parsed.review_flags:
            parsed.review_flags = []
        parsed.review_flags.append({
            "field": "_model",
            "issue": f"Extracted via fallback model ({QWEN_VL_FALLBACK})",
        })
        return parsed.model_dump()
    except Exception as e:
        logger.error(f"Fallback model also failed: {e}")
        raise


def _evict_ollama_model(model_name: str) -> None:
    """Force-unload an Ollama model from VRAM using keep_alive=0."""
    try:
        requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": model_name, "prompt": "", "keep_alive": 0},
            timeout=5,
        )
    except Exception:
        pass
    gc.collect()


# ── Checkbox Post-Processing ─────────────────────────────────────────────────


_CHECKBOX_PATTERN = re.compile(
    r"(\w[\w\s./-]*?)\s*[\(\[][✓✔☑xX]\s*[\)\]]"
)

_YES_PATTERN = re.compile(r"^\s*Yes\s*[\(\[][✓✔☑xX][\)\]]", re.IGNORECASE)


def _postprocess_checkboxes(data: dict[str, Any]) -> dict[str, Any]:
    """Normalise GLM-OCR checkbox output into clean categorical values.

    GLM-OCR often outputs checkbox groups verbatim rather than extracting
    the checked value:

        "Layer (✓) Cut ( ) Deposit ( ) Fill ( )"    →  "layer"
        "Yes (✓) No ( )"                              →  True
        "Yes ( ) No (✓)"                              →  False
        "Layer ( ) Cut (✓) Deposit ( ) Fill ( )"      →  "cut"

    Handles Unicode check variants (✓ ✔ ☑) and parenthetical markers.
    Operates in-place on the dict and returns it for convenience.
    """
    # ── Categorical checkbox groups (type, period, etc.) ──
    for field in ("type", "period", "certainty"):
        value = data.get(field)
        if not isinstance(value, str):
            continue
        if not _has_any_checkbox(value):
            continue

        # Check for Yes/No boolean pattern
        if re.match(r"^\s*(Yes|No)", value, re.IGNORECASE):
            data[field] = bool(_YES_PATTERN.match(value))
            continue

        # Extract the first checked option from a checkbox group
        match = _CHECKBOX_PATTERN.search(value)
        if match:
            data[field] = match.group(1).strip().lower()

    # ── Boolean yes/no fields ──
    for field in ("sketch_present",):
        value = data.get(field)
        if not isinstance(value, str):
            continue
        if not _has_any_checkbox(value):
            continue
        data[field] = bool(_YES_PATTERN.match(value))

    return data


def _has_any_checkbox(value: str) -> bool:
    """Return True if the string contains any checkbox marker."""
    return bool(re.search(r"[✓✔☑]|\[x\]|\[X\]|\(x\)|\(X\)", value))


# ── System Prompt ────────────────────────────────────────────────────────────


CONTEXT_SHEET_PROMPT = """You are an archaeological document digitisation system. Extract the following fields from this context sheet image.

Rules:
1. Output valid JSON matching the provided schema.
2. Use standard archaeological terminology for soil descriptions (colour, compaction, inclusions).
3. Context numbers should use square brackets, e.g. [101].
4. If handwriting is illegible or ambiguous, provide your best estimate in the field
   AND add an entry to review_flags: {"field": "field_name", "issue": "description of ambiguity"}.
5. For checkboxes: determine if checked (true) or unchecked (false).
6. For the 'type' field: use standard context types (layer, cut, deposit, fill, structure).
7. If no finds are present, set finds to an empty list [].
8. If no samples are present, set samples to an empty list [].
9. Do NOT invent data. If a field is not visible, leave it as a reasonable default.
"""


# ── Document Processing ──────────────────────────────────────────────────────


def _process_context_sheet(
    image_path: Path,
    quality_flags: dict | None = None,
    context_hint: str | None = None,
    extractor: str = "glm-ocr",
) -> dict[str, Any] | None:
    """Process a single context sheet image and return structured data.

    Args:
        image_path: Path to the context sheet image.
        quality_flags: Quality assessment from Phase 0 (for pre-processing).
        context_hint: Optional context number hint from filename.
        extractor: Which extraction model to use.
            "glm-ocr" (default) — GLM-OCR with Qwen3-VL fallback.
            "nuextract3" — NuExtract3 structured extraction specialist.
    """
    # Pre-process (same for all extractors)
    image_bytes = _preprocess_image(image_path, quality_flags)

    # ── NuExtract3 Path ──
    if extractor == "nuextract3":
        if not _NUEXTRACT3_AVAILABLE:
            logger.error("NuExtract3 support not installed (missing erd.extractors)")
            return None
        try:
            nuextract = NuExtract3Extractor()
            if not nuextract.is_available():
                logger.warning(
                    "NuExtract3 model not available in Ollama. "
                    "Run: ollama pull hf.co/numind/NuExtract3-GGUF:Q4_K_M"
                )
                return None
            result = nuextract.extract(
                image_bytes=image_bytes,
                ocr_text=None,
                context_number_hint=context_hint,
            )
            return _postprocess_checkboxes(result)
        except Exception as e:
            logger.error(f"NuExtract3 extraction failed: {e}")
            return None

    # ── GLM-OCR Path (default) ──
    for attempt in range(2):  # Max 2 attempts
        try:
            result = _call_glm_ocr(
                image_bytes=image_bytes,
                system_prompt=CONTEXT_SHEET_PROMPT,
                context_number_hint=context_hint,
            )
            return _postprocess_checkboxes(result)
        except Exception as e:
            if attempt == 0:
                logger.warning(f"GLM-OCR attempt 1 failed, retrying: {e}")
                continue
            logger.warning(f"GLM-OCR failed after 2 attempts, trying fallback: {e}")
            # Evict GLM-OCR, load fallback
            _evict_ollama_model(GLM_OCR_MODEL)
            try:
                result = _call_vlm_fallback(
                    image_bytes=image_bytes,
                    system_prompt=CONTEXT_SHEET_PROMPT,
                )
                return _postprocess_checkboxes(result)
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")
                return None

    return None


def _process_catalogue_with_docling(file_path: Path) -> dict[str, Any] | None:
    """Process a typed finds catalogue or typed document using Docling.

    Docling handles PDF, DOCX, TXT, and image files with layout-aware parsing.
    """
    try:
        converter = DocumentConverter()
        result = converter.convert(str(file_path))

        # Extract tables as Markdown/JSON
        tables = []
        if result.document.tables:
            for table in result.document.tables:
                tables.append(table.export_to_dict())

        return {
            "source_file": file_path.name,
            "model": "docling",
            "text": result.document.export_to_markdown(),
            "tables": tables,
        }
    except Exception as e:
        logger.error(f"Docling failed on {file_path}: {e}")
        return None


def _process_typed_document(file_path: Path) -> dict[str, Any] | None:
    """Process existing typed notes (TXT, DOCX, MD) — zero VRAM, CPU only."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return {
            "source_file": file_path.name,
            "model": "text_parser",
            "text": text,
        }
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        return None


# ── Main Entry Point ─────────────────────────────────────────────────────────


def run_phase1(config: Config) -> dict[str, Any]:
    """Execute Phase 1: Multi-Modal Digitisation.

    Reads the Phase 0 manifest and routes each file to the appropriate
    extraction model. Outputs structured JSON files.

    Args:
        config: Pipeline configuration.

    Returns:
        Dict with:
            - 'status': 'complete' | 'partial' | 'failed'
            - 'processed': number of documents processed
            - 'failed': number of documents that failed extraction
            - 'output_dir': path to digitised output directory
    """
    start_time = time.time()
    output_dir = config.digitised_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    assets_dir = config.assets_dir

    # Load manifest
    manifest_path = config.manifest_dir / "manifest.json"
    if not manifest_path.exists():
        return {
            "status": "failed",
            "processed": 0,
            "failed": 0,
            "error": "No Phase 0 manifest found. Run Phase 0 first.",
        }

    manifest = json.loads(manifest_path.read_text())
    files = manifest.get("files", [])
    quality_warnings = manifest.get("quality_warnings", 0)

    processed_count = 0
    failed_count = 0
    results: list[dict[str, Any]] = []

    logger.info(f"Phase 1 starting: {len(files)} files in manifest")

    # Group context sheets for batch processing with GLM-OCR
    context_sheets = [f for f in files if f.get("type") == "context_sheet"]
    catalogues = [f for f in files if f.get("type") == "finds_catalogue"]
    typed_docs = [f for f in files if f.get("type") in ("existing_text",)]

    # ── Route 1: Context Sheets (GLM-OCR) ──
    if context_sheets:
        logger.info(f"Processing {len(context_sheets)} context sheet(s) via GLM-OCR")
        for entry in context_sheets:
            src = config.input_dir / entry["path"]
            if not src.exists():
                logger.warning(f"File not found: {src}")
                failed_count += 1
                continue

            quality = entry.get("quality", {})
            ctx_hint = src.stem.replace("ctx_", "").replace("context_", "")

            try:
                result = _process_context_sheet(
                    src, quality, ctx_hint,
                    extractor=config.extractor,
                )
                if result:
                    result["source_file"] = src.name
                    out_path = output_dir / f"{src.stem}.json"
                    out_path.write_text(json.dumps(result, indent=2))
                    processed_count += 1
                    results.append(result)
                    logger.info(f"  ✓ {src.name}")
                else:
                    logger.warning(f"  ✗ {src.name} — extraction failed")
                    failed_count += 1
            except Exception as e:
                logger.error(f"  ✗ {src.name} — {e}")
                failed_count += 1

        # Evict GLM-OCR from VRAM after batch
        _evict_ollama_model(GLM_OCR_MODEL)

    # ── Route 2: Finds Catalogues (Docling) ──
    if catalogues:
        logger.info(f"Processing {len(catalogues)} catalogue(s) via Docling")
        for entry in catalogues:
            src = config.input_dir / entry["path"]
            if not src.exists():
                logger.warning(f"File not found: {src}")
                failed_count += 1
                continue

            ext = src.suffix.lower()
            if ext in (".csv", ".xlsx"):
                # Tabular data — parse directly with pandas
                try:
                    import pandas as pd
                    if ext == ".csv":
                        df = pd.read_csv(src)
                    else:
                        df = pd.read_excel(src)
                    result = {
                        "source_file": src.name,
                        "model": "pandas",
                        "rows": len(df),
                        "columns": list(df.columns),
                        "data": df.fillna("").to_dict(orient="records"),
                    }
                except Exception as e:
                    logger.error(f"  ✗ {src.name} — pandas failed: {e}")
                    result = _process_catalogue_with_docling(src)
            else:
                # PDF/Image — use Docling with vision model
                result = _process_catalogue_with_docling(src)

            if result:
                out_path = output_dir / f"{src.stem}.json"
                out_path.write_text(json.dumps(result, indent=2, default=str))
                processed_count += 1
                logger.info(f"  ✓ {src.name}")
            else:
                failed_count += 1

    # ── Route 3: Existing Typed Notes (CPU) ──
    for entry in typed_docs:
        src = config.input_dir / entry["path"]
        if not src.exists():
            continue
        result = _process_typed_document(src)
        if result:
            out_path = output_dir / f"{src.stem}.json"
            out_path.write_text(json.dumps(result, indent=2))
            processed_count += 1
        else:
            failed_count += 1

    duration_ms = int((time.time() - start_time) * 1000)

    # Write summary to logs
    summary = {
        "status": "complete" if failed_count == 0 else "partial",
        "processed": processed_count,
        "failed": failed_count,
        "total_files": len(files),
        "quality_warnings": quality_warnings,
        "output_dir": str(output_dir),
        "duration_ms": duration_ms,
    }
    log_path = config.logs_dir / "phase1_summary.json"
    log_path.write_text(json.dumps(summary, indent=2))

    # Validate outputs against schema contract (v1)
    validated, errors = _validate_context_schema(output_dir)
    if errors:
        msg = f"Schema validation: {validated}/{validated + len(errors)} passed"
        logger.warning(msg)
        for err in errors[:5]:
            logger.warning(f"  Schema error: {err}")

        if config.strict:
            summary["status"] = "failed"
            summary["schema_validation"] = {
                "valid": validated,
                "errors": errors,
            }
            logger.error(f"Strict mode: {len(errors)} schema validation error(s) — halting")
            return summary

    logger.info(f"Phase 1 complete: {processed_count} processed, {failed_count} failed in {duration_ms/1000:.1f}s")

    return summary


_SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent.parent / "schemas" / "context-sheet-v1.json"


def _validate_context_schema(digitised_dir: Path) -> tuple[int, list[str]]:
    """Validate Phase 1 output JSON files against the shared schema contract.

    Returns (valid_count, error_messages).

    This is advisory (warns but doesn't halt) so extraction proceeds even
    if the schema has minor additions or the output has benign extras.
    """
    errors: list[str] = []
    valid_count = 0

    schema_path = _SCHEMA_PATH
    if not schema_path.exists():
        logger.info(f"Schema contract not found at {schema_path} — skipping validation")
        return 0, []

    try:
        import jsonschema
        schema = json.loads(schema_path.read_text())
    except ImportError:
        logger.info("jsonschema not installed — skipping schema contract validation")
        return 0, []
    except Exception as e:
        logger.warning(f"Could not load schema: {e}")
        return 0, []

    for f in sorted(digitised_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            jsonschema.validate(instance=data, schema=schema)
            valid_count += 1
        except jsonschema.ValidationError as e:
            errors.append(f"{f.name}: {e.message[:100]}")
        except Exception:
            pass

    return valid_count, errors
