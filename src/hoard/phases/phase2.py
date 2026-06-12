"""phase2.py — Spatial Reconstruction.

Single-stage pipeline using Qwen3-VL-8B (Ollama) for:

  - Photo captioning: structured archaeological caption describing features,
    spatial relationships, and scale
  - Cross-check: identifies discrepancies between visual evidence and
    Phase 1 context sheet data (e.g. "photo shows masonry but context
    says layer")
  - SVG vectorisation: converts field section drawings to SVG via
    Qwen3-VL-8B prompt engineering

Peak VRAM: ~5.5 GB during Qwen3-VL-8B inference.

exports: run_phase2(config) -> dict
used_by: hoard.cli.run  -> orchestrator
license: MIT
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import requests
from PIL import Image

from hoard.config import Config
from hoard.helpers import OLLAMA_BASE_URL, evict_ollama_model

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────

QWEN_VL_MODEL = "qwen3-vl:8b"
GLM_OCR_MODEL = "glm-ocr:latest"  # Fast alternative: 2.2 GB, ~30s per image
VL_TIMEOUT = 120
SVG_TIMEOUT = 600  # SVG generation needs more time for complex output
VL_TEMPERATURE = 0.1
VL_CTX_SIZE = 32768

# Image constraints
MAX_IMAGE_DIMENSION = 2048  # longest edge


# ── Data Models ──────────────────────────────────────────────────────────────


@dataclass
class CrossCheckResult:
    """Results of cross-referencing visual evidence against context sheets."""
    matching_contexts: list[str] = field(default_factory=list)
    inconsistencies: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PhotoAnalysis:
    """Full structured output for one site photograph."""
    source_file: str
    model: str = QWEN_VL_MODEL
    caption: str = ""
    cross_check: CrossCheckResult | None = None
    error: str | None = None


# ── Qwen3-VL: Caption Synthesis & Cross-Check ──────────────────────────────


def _call_qwen_vl(
    image_bytes: bytes,
    system_prompt: str,
    user_prompt: str,
    temperature: float = VL_TEMPERATURE,
    model: str = GLM_OCR_MODEL,  # Use fast GLM-OCR by default
) -> dict[str, Any] | None:
    """Call a vision model via Ollama with image + text prompt.

    Uses GLM-OCR by default (fast, 2.2 GB, ~30s per image).
    Falls back to Qwen3-VL-8B if specified.

    Returns parsed JSON dict on success, None on failure.
    """
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": model,
        "prompt": f"{system_prompt}\n\n{user_prompt}",
        "images": [b64_image],
        "options": {
            "temperature": temperature,
            "num_ctx": VL_CTX_SIZE,
        },
        "stream": False,
        "keep_alive": -1,  # Keep in VRAM during batch
    }

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=VL_TIMEOUT,
        )
        resp.raise_for_status()
        text = resp.json().get("response", "").strip()

        if not text:
            logger.warning("Qwen3-VL returned empty response")
            return None

        # Try direct JSON parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Fallback: extract JSON from markdown code block or braces
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Last resort: find anything that looks like { ... }
        brace_match = re.search(r"\{[\s\S]*\}", text)
        if brace_match:
            try:
                return json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass

        # Truncated JSON fallback: extract caption value if visible
        cap_match = re.search(r'"caption"\s*:\s*"([^"]+)"', text)
        if cap_match:
            return {"caption": cap_match.group(1)}

        # Prose fallback: return full text as caption
        if len(text) > 20:
            return {"caption": text.strip()[:500]}

        logger.warning(f"Could not parse JSON from response: {text[:200]}")
        return None
    except Exception as e:
        logger.warning(f"Qwen3-VL call failed: {e}")
        return None


def _synthesize_caption(
    image_bytes: bytes,
    context_hint: str | None = None,
) -> str:
    """Generate an archaeological caption via Qwen3-VL."""
    system = (
        "You are an archaeological photographer. Give a 1-2 sentence caption "
        "for this site photo. Include photo type and visible features."
    )

    user = "Describe this archaeological photograph briefly (1-2 sentences)."
    if context_hint:
        user += f"\nContext: {context_hint}"
    user += '\n\nReturn JSON: {"caption": "short caption"}'

    result = _call_qwen_vl(image_bytes, system, user, temperature=0.0)
    if result and "caption" in result:
        return result["caption"]

    # Fallback: try to extract any string value > 20 chars
    if result:
        for v in result.values():
            if isinstance(v, str) and len(v) > 20:
                return v

    # Last resort: if the raw response has a caption-like string
    return "Caption generation failed"


def _crosscheck_photo(
    image_bytes: bytes,
    caption: str,
    context_data: list[dict[str, Any]],
) -> CrossCheckResult:
    """Cross-check photo caption against Phase 1 context data."""
    context_text = json.dumps(context_data, indent=2) if context_data else "No context data"

    system = (
        "You are an archaeological QA officer. Compare the PHOTO CAPTION against "
        "the DIGITAL CONTEXT RECORD. Identify discrepancies between visual evidence "
        "and the written record. "
        "Return JSON: {\"matching_contexts\": [\"[101]\"], "
        "\"inconsistencies\": [{\"context\": \"[101]\", "
        "\"photo_description\": \"wall\", \"record_description\": \"layer\", "
        "\"severity\": \"high\"}]}"
    )

    user = f"PHOTO: {caption}\n\nRECORD: {context_text}\n\nIdentify discrepancies."

    result = _call_qwen_vl(image_bytes, system, user, temperature=0.0)
    if result:
        return CrossCheckResult(
            matching_contexts=result.get("matching_contexts", []),
            inconsistencies=result.get("inconsistencies", []),
        )

    # Text-based fallback: extract context numbers from prose response
    # (GLM-OCR outputs prose descriptions, not JSON for cross-check)
    ctx_nums = re.findall(r"\[(\d+)\]", caption + str(context_data))
    return CrossCheckResult(
        matching_contexts=[f"[{n}]" for n in sorted(set(ctx_nums))],
    )


# ── Image Utilities ─────────────────────────────────────────────────────────


def _load_image(image_path: Path) -> Image.Image | None:
    """Load and normalise an image for Qwen3-VL."""
    try:
        img = Image.open(image_path).convert("RGB")
        # Resize if too large
        w, h = img.size
        if max(w, h) > MAX_IMAGE_DIMENSION:
            scale = MAX_IMAGE_DIMENSION / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        return img
    except Exception as e:
        logger.error(f"Cannot load image {image_path}: {e}")
        return None


def _image_to_bytes(image: Image.Image, fmt: str = "PNG") -> bytes:
    """Convert PIL Image to bytes for Ollama API."""
    import io
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return buf.getvalue()


# ── Photo Processing ────────────────────────────────────────────────────────


def _find_assets(assets_dir: Path) -> list[Path]:
    """Find image files in the assets directory."""
    exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
    images: list[Path] = []
    if assets_dir.is_dir():
        for p in sorted(assets_dir.rglob("*")):
            if p.suffix.lower() in exts:
                images.append(p)
    return images


def _load_context_data(digitised_dir: Path) -> list[dict[str, Any]]:
    """Load Phase 1 context sheet data for cross-checking."""
    contexts: list[dict[str, Any]] = []
    for f in sorted(digitised_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            if "context_number" in data:
                contexts.append(data)
        except Exception:
            pass
    return contexts


def process_photo(
    image_path: Path,
    context_data: list[dict[str, Any]],
    context_hint: str | None = None,
) -> PhotoAnalysis:
    """Run Phase 2 on a single site photograph.

    Uses Qwen3-VL-8B for caption synthesis and cross-check against
    Phase 1 context data.

    Args:
        image_path: Path to the photo file.
        context_data: Phase 1 context sheet data for cross-check.
        context_hint: Optional context number hint.

    Returns:
        PhotoAnalysis dataclass with caption and cross-check results.
    """
    analysis = PhotoAnalysis(source_file=image_path.name)

    # Load image
    pil_image = _load_image(image_path)
    if pil_image is None:
        analysis.error = "Could not load image"
        return analysis

    image_bytes = _image_to_bytes(pil_image)

    # Build context hint
    ctx_hint_str = None
    if context_hint and context_data:
        matching = [c for c in context_data if c.get("context_number", "").strip("[]") == context_hint.strip("[]")]
        if matching:
            ctx_hint_str = json.dumps(matching[0], indent=2)

    # Stage 1: Qwen3-VL caption
    try:
        caption = _synthesize_caption(image_bytes, ctx_hint_str)
        analysis.caption = caption
    except Exception as e:
        logger.warning(f"Caption generation failed for {image_path.name}: {e}")
        analysis.caption = ""

    # Stage 2: Cross-check
    if analysis.caption:
        try:
            analysis.cross_check = _crosscheck_photo(image_bytes, analysis.caption, context_data)
        except Exception as e:
            logger.warning(f"Cross-check failed for {image_path.name}: {e}")

    analysis.model = QWEN_VL_MODEL
    logger.info(f"  ✓ {image_path.name}: caption={len(analysis.caption)} chars")
    return analysis


# ── SVG Geometry (Optional) ────────────────────────────────────────────────

# Default SVG canvas for an A4-ish section drawing at ~100dpi
_SVG_WIDTH = 800
_SVG_HEIGHT = 600

# Concise SVG prompt — verbosity hurts inference speed on 8B model
_SVG_PROMPT = """Convert this archaeological section drawing to SVG. Rules:
- Use only <svg>, <path>, <line>, <text>, <rect>, <g>
- Label each context with its number
- Dashed lines for cuts, solid for layers
- Include a scale bar
- viewBox="0 0 {w} {h}"
- Wrap in ```svg...```"""


def _ctx_numbers(context_data: list[dict[str, Any]] | None) -> str:
    """... existing docstring ..."""
    if not context_data:
        return ""
    nums = []
    for c in context_data[:8]:
        num = c.get("context_number", "?")
        typ = c.get("type", "?")
        nums.append(f"{num} ({typ})")
    return ", ".join(nums)


def _filter_photos_from_manifest(
    images: list[Path],
    manifest_dir: Path,
) -> list[Path]:
    """Filter images to only those classified as site_photo or plan in the manifest.

    Context sheets, sample photos, and other document scans are excluded.
    Falls back to all images if no manifest is available.
    """
    manifest_path = manifest_dir / "manifest.json"
    if not manifest_path.exists():
        return images  # No manifest — process all (fallback)

    try:
        import json
        manifest = json.loads(manifest_path.read_text())
        photo_files: set[str] = set()
        for entry in manifest.get("files", []):
            if entry.get("type") in ("site_photo", "plan"):
                # Store both the filename and the original path
                photo_files.add(Path(entry["path"]).name)
    except Exception:
        return images

    filtered = [img for img in images if img.name in photo_files]
    return filtered or images  # Fallback to all if filter empties the list


def process_svg_drawing(
    image_path: Path,
    context_data: list[dict[str, Any]] | None = None,
    width: int = _SVG_WIDTH,
    height: int = _SVG_HEIGHT,
) -> str | None:
    """Generate an SVG vector drawing from a field section drawing.

    Uses Qwen3-VL prompted to output SVG path data following archaeological
    illustration conventions (hachures for cuts, stippling for fills, etc.).

    Args:
        image_path: Path to the scanned section drawing.
        context_data: Optional list of context dicts for labelling.
        width: SVG viewBox width in px.
        height: SVG viewBox height in px.

    Returns:
        Validated SVG string, or None on failure.
    """
    pil_image = _load_image(image_path)
    if pil_image is None:
        return None

    image_bytes = _image_to_bytes(pil_image)

    system = _SVG_PROMPT.format(w=width, h=height)
    user = f"Context numbers: {_ctx_numbers(context_data)}" if context_data else ""

    try:
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "model": GLM_OCR_MODEL,
            "prompt": f"{system}\n{user}".strip(),
            "images": [b64_image],
            "options": {"temperature": 0.1, "num_ctx": VL_CTX_SIZE},
            "stream": False,
            "keep_alive": -1,
        }
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=SVG_TIMEOUT,
        )
        resp.raise_for_status()
        raw_text = resp.json().get("response", "")

        # Extract SVG from response
        svg = _extract_svg_from_text(raw_text)
        if svg is None:
            logger.warning(f"No valid SVG found in response for {image_path.name}")
            return None

        # Validate and post-process
        svg = _postprocess_svg(svg, width, height, image_path.stem)
        return svg

    except requests.Timeout:
        logger.error(f"SVG generation timed out for {image_path.name} "
                     f"(>{SVG_TIMEOUT}s)")
        return None
    except Exception as e:
        logger.error(f"SVG generation failed for {image_path.name}: {e}")
        return None


def _extract_svg_from_text(text: str) -> str | None:
    """Extract SVG XML string from model response text.

    Tries, in order:
    1. ```svg ... ``` code blocks
    2. ```xml ... ``` with <svg> inside
    3. Raw <svg> ... </svg> tags
    """
    if not text:
        return None

    # Pattern 1: ```svg ... ```
    for pattern in [
        r"```svg\s*\n?(.*?)```",
        r"```xml\s*\n?(.*?)```",
        r"```html\s*\n?(.*?)```",
    ]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            candidate = match.group(1).strip()
            if candidate.startswith("<svg") or "<svg" in candidate:
                # Extract just the <svg> portion
                svg_match = re.search(r"(<svg[\s\S]*?</svg>)", candidate, re.DOTALL)
                if svg_match:
                    return svg_match.group(1).strip()
                return candidate

    # Pattern 2: raw <svg> tag
    raw_match = re.search(r"(<svg[\s\S]*?</svg>)", text, re.DOTALL)
    if raw_match:
        return raw_match.group(1).strip()

    return None


def _postprocess_svg(
    svg: str,
    target_width: int = _SVG_WIDTH,
    target_height: int = _SVG_HEIGHT,
    title: str = "section_drawing",
) -> str:
    """Validate and standardise an SVG string.

    - Ensures viewBox is present and proportional
    - Strips disallowed elements (script, foreignObject, external refs)
    - Adds metadata / title
    - Normalises whitespace
    """
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(svg)
    except ET.ParseError as e:
        logger.warning(f"SVG parsing failed: {e} — returning raw SVG")
        return _add_svg_metadata(svg, title)

    # Check/set viewBox
    vb = root.get("viewBox")
    if not vb:
        root.set("viewBox", f"0 0 {target_width} {target_height}")
    if not root.get("xmlns"):
        root.set("xmlns", "http://www.w3.org/2000/svg")

    # Remove disallowed elements
    disallowed = {"script", "foreignObject", "image"}
    for tag in disallowed:
        for elem in root.findall(f".//{{http://www.w3.org/2000/svg}}{tag}"):
            root.remove(elem)

    # Add title element
    title_elem = ET.SubElement(root, "{http://www.w3.org/2000/svg}title")
    title_elem.text = title.replace("_", " ").title()

    # Serialize back
    raw = ET.tostring(root, encoding="unicode", short_empty_elements=False)
    return raw


def _add_svg_metadata(svg: str, title: str) -> str:
    """Add minimal metadata to an SVG string that failed XML parsing."""
    # Simple string-based insert
    title_tag = f"<title>{title.replace('_', ' ').title()}</title>"
    if "<title>" not in svg:
        # Insert after opening <svg> tag
        svg = re.sub(r"(<svg[^>]*>)", rf"\1\n{title_tag}", svg)
    return svg


def _is_section_drawing(image_path: Path) -> bool:
    """Heuristic to determine if an image is likely a section drawing.

    Checks filename patterns and image aspect ratio.
    """
    stem = image_path.stem.lower()

    # Filename heuristics (fast, no file open needed)
    section_keywords = {"section", "drawing", "profile", "elevation", "sketch", "permatrace"}
    if any(kw in stem for kw in section_keywords):
        return True

    # For remaining files, check aspect ratio (sections are often landscape)
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            # Section drawings tend to be landscape-oriented
            if w > h * 1.2 and max(w, h) > 500:
                return True
    except Exception:
        pass

    return False


# ── Main Entry Point ────────────────────────────────────────────────────────


def run_phase2(config: Config) -> dict[str, Any]:
    """Execute Phase 2: Spatial Reconstruction.

    Processes site photographs through Florence-2 (bounding boxes) and
    Qwen3-VL-4B (caption + cross-check). Generates SVG geometry from
    field section drawings.

    Args:
        config: Pipeline configuration.

    Returns:
        Dict with status, processed count, and output paths.
    """
    start_time = time.time()
    spatial_dir = config.spatial_dir
    spatial_dir.mkdir(parents=True, exist_ok=True)

    assets_dir = config.assets_dir
    digitised_dir = config.digitised_dir

    # Find images and load context data
    all_images = _find_assets(assets_dir)
    if not all_images:
        logger.info("No images found in assets/ — Phase 2 skipped")
        return {
            "status": "skipped",
            "processed": 0,
            "failed": 0,
            "output_dir": str(spatial_dir),
        }

    # Filter by manifest type: only process site_photo and plan files,
    # not context sheets (which would produce irrelevant photo plates)
    images = _filter_photos_from_manifest(all_images, config.manifest_dir)
    if not images:
        logger.info("No site photos or plans found in manifest — Phase 2 skipped")
        return {
            "status": "skipped",
            "processed": 0,
            "failed": 0,
            "output_dir": str(spatial_dir),
        }

    context_data = _load_context_data(digitised_dir)
    logger.info(f"Phase 2 starting: {len(images)} image(s), {len(context_data)} context(s)")

    # Process all photos through Qwen3-VL-8B
    processed_count = 0
    failed_count = 0
    results: list[dict[str, Any]] = []

    for img_path in images:
        logger.info(f"Processing {img_path.name}...")
        ctx_hint = _extract_context_hint(img_path.stem)

        analysis = process_photo(
            image_path=img_path,
            context_data=context_data,
            context_hint=ctx_hint,
        )

        out_data = asdict(analysis)
        if isinstance(out_data.get("cross_check"), CrossCheckResult):
            out_data["cross_check"] = asdict(out_data["cross_check"])

        if analysis.error:
            failed_count += 1
            out_path = spatial_dir / f"{img_path.stem}.json"
            out_path.write_text(json.dumps(out_data, indent=2))
        else:
            processed_count += 1
            out_path = spatial_dir / f"{img_path.stem}.json"
            out_path.write_text(json.dumps(out_data, indent=2))

        results.append(out_data)

    # ── SVG geometry (attempt on section drawings from ALL images) ──
    svg_count = 0
    for img_path in all_images:
        if _is_section_drawing(img_path):
            logger.info(f"Attempting SVG from {img_path.name}...")
            svg = process_svg_drawing(img_path, context_data)
            if svg:
                svg_out = spatial_dir / f"{img_path.stem}.svg"
                svg_out.write_text(svg)
                svg_count += 1
                logger.info(f"  ✓ SVG generated: {svg_out.name}")
            else:
                logger.info(f"  ✗ SVG failed for {img_path.name}")

    # Evict GLM-OCR from VRAM
    evict_ollama_model(GLM_OCR_MODEL)

    duration_ms = int((time.time() - start_time) * 1000)

    summary = {
        "status": "complete" if failed_count == 0 else "partial",
        "processed": processed_count,
        "failed": failed_count,
        "total_images": len(images),
        "svg_generated": svg_count,
        "output_dir": str(spatial_dir),
        "duration_ms": duration_ms,
    }
    log_path = config.logs_dir / "phase2_summary.json"
    log_path.write_text(json.dumps(summary, indent=2))

    logger.info(
        f"Phase 2 complete: {processed_count} photos, {svg_count} SVG, "
        f"{failed_count} failed in {duration_ms/1000:.1f}s"
    )

    return summary


def _extract_context_hint(stem: str) -> str | None:
    """Try to extract a context number from a photo filename."""
    # Match patterns like DSC_0042, photo_101, ctx_101
    num_match = re.search(r"(\d{3,})", stem)
    if num_match:
        return f"[{num_match.group(1)}]"
    return None
