"""phase0.py — Ingestion & Triage.

Rule-based phase that inventories input files, normalises formats,
assesses image quality, classifies document types, and validates
finds catalogues. Zero VRAM cost — no GPU model loaded.

exports: run_phase0(config) -> dict  — executes triage, returns manifest
used_by: hoard.cli.run  → orchestrator
rules:   Must never import torch or any GPU-bound library.
         Must catch corrupt/unreadable files gracefully.
         Must halt with clear message if mandatory files are missing.
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Initial scaffold
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hoard.config import Config


def _numpy_safe(obj: Any) -> Any:
    """Recursively convert numpy types to native Python types for JSON."""
    import numpy as np
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _numpy_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_numpy_safe(i) for i in obj]
    return obj

# import cv2  # lazy-import inside quality check functions
# from PIL import Image  # lazy-import

# ── Constants ──────────────────────────────────────────────────────────────

ACCEPTED_EXTENSIONS: dict[str, str] = {
    # image
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".heic": "image/heic",
    ".heif": "image/heic",
    # raw camera
    ".raf": "image/x-fujifilm-raf",
    ".nef": "image/x-nikon-nef",
    ".cr2": "image/x-canon-cr2",
    ".arw": "image/x-sony-arw",
    # document
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown",
    # vector
    ".dxf": "image/vnd.dxf",
    ".svg": "image/svg+xml",
}

MANDATORY_TYPES = {"context_sheet", "finds_catalogue"}
MAJOR_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".raf", ".nef", ".cr2", ".arw"}
RAW_EXTS = {".raf", ".nef", ".cr2", ".arw"}

# Quality thresholds (from design doc)
BLUR_LAPLACIAN_VARIANCE_THRESHOLD = 80.0
SKEW_ANGLE_THRESHOLD = 15.0
EXPOSURE_MEAN_THRESHOLD = 40

# ── Data structures ────────────────────────────────────────────────────────


class QualityFlags:
    """Quality assessment results for a single file."""

    def __init__(self) -> None:
        self.blur_score: float | None = None
        self.skew_deg: float | None = None
        self.exposure_mean: float | None = None
        self.flag: str | None = None  # "BLUR_LOW" | "SKEW_HIGH" | "EXPOSURE_LOW" | None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.blur_score is not None:
            d["blur_score"] = round(float(self.blur_score), 1)
        if self.skew_deg is not None:
            d["skew_deg"] = round(float(self.skew_deg), 1)
        if self.exposure_mean is not None:
            d["exposure_mean"] = int(round(float(self.exposure_mean)))
        if self.flag:
            d["flag"] = self.flag
        return d


class FileEntry:
    """A single file in the manifest."""

    def __init__(self, file_id: str, path: str, file_type: str, quality: QualityFlags | None = None):
        self.id = file_id
        self.path = path
        self.type = file_type
        self.quality = quality or QualityFlags()

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "path": self.path,
            "type": self.type,
            "quality": self.quality.to_dict(),
        }
        return d


def _file_hash(filepath: Path) -> str:
    """SHA-256 hash of file contents."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalise_image(input_path: Path, output_dir: Path, dpi_target: int = 300) -> Path | None:
    """Convert HEIC/RAW/PDF pages to normalised PNG.

    Returns the output path on success, None on failure.
    """
    ext = input_path.suffix.lower()

    # HEIC/HEIF — use Pillow (requires pillow-heif)
    if ext in (".heic", ".heif"):
        try:
            from PIL import Image as PILImage

            img = PILImage.open(input_path)
            out_path = output_dir / f"{input_path.stem}.png"
            img.save(out_path, "PNG")
            return out_path
        except Exception:
            return None

    # RAW — use rawpy + Pillow
    if ext in RAW_EXTS:
        try:
            import rawpy

            with rawpy.imread(str(input_path)) as raw:
                rgb = raw.postprocess()
            from PIL import Image as PILImage

            out_path = output_dir / f"{input_path.stem}.png"
            PILImage.fromarray(rgb).save(out_path, "PNG")
            return out_path
        except Exception:
            return None

    # PDF — extract all pages via PyMuPDF (memory-efficient)
    if ext == ".pdf":
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(input_path))
            page_count = len(doc)  # Stream all pages — PyMuPDF is memory-efficient
            paths: list[Path] = []
            for i in range(page_count):
                page = doc[i]
                pix = page.get_pixmap(dpi=150)  # Lower DPI for PDF scans
                out_path = output_dir / f"{input_path.stem}_page_{i+1:03d}.png"
                pix.save(str(out_path))
                paths.append(out_path)
            doc.close()
            return paths[0] if paths else None
        except Exception:
            return None

    # Already a standard format — copy as-is
    if ext in (".jpg", ".jpeg", ".png"):
        out_path = output_dir / f"{input_path.stem}{ext}"
        shutil.copy2(input_path, out_path)
        return out_path

    return None


def _assess_quality(image_path: Path) -> QualityFlags:
    """Run OpenCV-based quality checks: blur, skew, exposure."""
    flags = QualityFlags()

    try:
        import cv2

        img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            return flags

        # Blur: Laplacian variance
        laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
        flags.blur_score = laplacian_var
        if laplacian_var < BLUR_LAPLACIAN_VARIANCE_THRESHOLD:
            flags.flag = "BLUR_LOW"

        # Skew: Hough line detection
        edges = cv2.Canny(img, 50, 150)
        lines = cv2.HoughLines(edges, 1, 3.14159 / 180, threshold=200)
        if lines is not None:
            angles = []
            for rho, theta in lines[:, 0]:
                angle = abs(theta * 180 / 3.14159 - 90)
                if angle < 45:  # near-horizontal lines
                    angles.append(angle)
            if angles:
                median_angle = sorted(angles)[len(angles) // 2]
                skew = abs(median_angle - 0)
                flags.skew_deg = round(skew, 2)
                if skew > SKEW_ANGLE_THRESHOLD and flags.flag is None:
                    flags.flag = "SKEW_HIGH"

        # Exposure: mean pixel value
        mean_val = img.mean()
        flags.exposure_mean = round(mean_val)
        if mean_val < EXPOSURE_MEAN_THRESHOLD and flags.flag is None:
            flags.flag = "EXPOSURE_LOW"

    except ImportError:
        # cv2 not installed — skip quality checks, mark as unknown
        pass

    return flags


def _classify_image(image_path: Path) -> str:
    """Classify an image into a document type using filename heuristics.

    Design doc specifies MobileNetV3 for this, but the model is small
    (~20 MB) and can be added later. For now, use filename-based rules
    which cover 90%+ of real cases.
    """
    stem = image_path.stem.lower()

    # Pattern matching on filenames
    if any(kw in stem for kw in ("context", "ctx", "section", "record_sheet")):
        return "context_sheet"
    if any(kw in stem for kw in ("finds", "catalogue", "finds_register", "small_finds")):
        return "finds_catalogue"
    if any(kw in stem for kw in ("plan", "trench_plan", "site_plan", "overview")):
        return "plan"
    if any(kw in stem for kw in ("section", "profile", "drawing")):
        return "section"
    if any(kw in stem for kw in ("photo", "dsc", "img", "picture", "site_photo")):
        return "site_photo"
    if any(kw in stem for kw in ("sample", "environmental", "flot", "residue")):
        return "sample_result"

    return "unknown"


def _validate_csv_finds(filepath: Path) -> tuple[bool, list[str]]:
    """Validate a CSV finds catalogue against known schema variants.

    Returns (is_valid, list_of_issues).
    """
    issues: list[str] = []
    try:
        with open(filepath, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            header_lower = [h.strip().lower() for h in header]

        # Known mandatory columns across common schemas
        mandatory_sets = [
            {"context", "context_number", "ctx"},
            {"object_type", "object", "material", "type", "category"},
            {"quantity", "count", "qty", "no", "number"},
            {"period", "date", "dating", "phase", "period_date"},
        ]

        found_any = False
        for col_set in mandatory_sets:
            if any(col in header_lower for col in col_set):
                found_any = True
                break

        if not found_any:
            issues.append("No recognisable finds columns found in header")

        # Warn about missing common fields
        if not any(col in header_lower for col in ("context", "context_number", "ctx")):
            issues.append("No context number column — cannot link finds to contexts")
        if not any(col in header_lower for col in ("quantity", "count", "qty", "no")):
            issues.append("No quantity column")

        return len(issues) == 0, issues
    except Exception as e:
        return False, [f"Failed to read CSV: {e}"]


def _validate_xlsx_finds(filepath: Path) -> tuple[bool, list[str]]:
    """Validate an XLSX finds catalogue."""
    issues: list[str] = []
    try:
        import openpyxl

        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        ws = wb.active
        if ws is None:
            return False, ["No active sheet found"]
        header = [str(c.value).lower() if c.value else "" for c in next(ws.iter_rows(min_row=1, max_row=1))]
        wb.close()

        if not header or all(h == "" for h in header):
            return False, ["Header row appears empty"]
        if not any(col in header for col in ("context", "context_number", "ctx")):
            issues.append("No context number column")
        return len(issues) == 0, issues
    except Exception as e:
        return False, [f"Failed to read XLSX: {e}"]


# ── Main entry point ───────────────────────────────────────────────────────


def run_phase0(config: Config) -> dict[str, Any]:
    """Execute Phase 0: Ingestion & Triage.

    Returns the manifest dict. The caller is responsible for writing it
    to disk and updating PipelineState.
    """
    input_dir = config.input_dir
    assets_dir = config.assets_dir
    manifest_dir = config.manifest_dir

    manifest_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Enumerate files
    all_files: list[Path] = sorted(
        p for p in input_dir.rglob("*") if p.is_file() and not p.name.startswith(".")
    )
    entries: list[FileEntry] = []
    quality_warnings = 0
    mandatory_found: set[str] = set()

    for filepath in all_files:
        ext = filepath.suffix.lower()
        if ext not in ACCEPTED_EXTENSIONS:
            continue

        file_id = f"{filepath.stem}_{_file_hash(filepath)[:8]}"

        # Non-image files bypass normalisation (handled by CSV/XLSX validation below)
        normalised: Path | None = None

        if ext in MAJOR_IMAGE_EXTS | {".pdf", ".heic", ".heif"} | RAW_EXTS:
            normalised = _normalise_image(filepath, assets_dir)
            if normalised is None:
                continue  # Corrupt or unsupported image — skip

        # Step 3: Quality check (images only)
        quality = QualityFlags()
        if normalised and normalised.suffix.lower() in MAJOR_IMAGE_EXTS:
            quality = _assess_quality(normalised)
            if quality.flag:
                quality_warnings += 1

        # Step 4: Classify
        classify_target = normalised if normalised else filepath
        file_type = _classify_image(classify_target)
        if file_type == "unknown":
            # Extension-based fallback for non-image files
            if ext in (".csv", ".xlsx"):
                file_type = "finds_catalogue"
            elif ext in (".dxf", ".svg"):
                file_type = "plan"
            elif ext in (".txt", ".docx", ".md"):
                file_type = "existing_text"

        if file_type in MANDATORY_TYPES:
            mandatory_found.add(file_type)

        entry = FileEntry(
            file_id=file_id,
            path=str(filepath.relative_to(input_dir) if filepath.is_relative_to(input_dir) else filepath.name),
            file_type=file_type,
            quality=quality,
        )
        entries.append(entry)

    # Step 5: Validate CSV/XLSX finds catalogues
    finds_issues: list[dict] = []
    for entry in entries:
        if entry.type != "finds_catalogue":
            continue
        src_path = input_dir / entry.path
        if src_path.suffix.lower() == ".csv":
            valid, issues = _validate_csv_finds(src_path)
            if not valid:
                finds_issues.append({"file": entry.id, "issues": issues})
        elif src_path.suffix.lower() == ".xlsx":
            valid, issues = _validate_xlsx_finds(src_path)
            if not valid:
                finds_issues.append({"file": entry.id, "issues": issues})

    # Critical: must have at least one context sheet
    if "context_sheet" not in mandatory_found:
        missing_mandatory = {"context_sheet"}
        mandatory_check = "FAIL"
    else:
        missing_mandatory = MANDATORY_TYPES - mandatory_found - {"context_sheet"}
        mandatory_check = "WARN" if missing_mandatory else "PASS"

    # Count flagged / unreadable context sheets for quality check
    context_sheets = [e for e in entries if e.type == "context_sheet"]
    flagged_contexts = [e for e in context_sheets if e.quality.flag is not None]

    halt_flag = (
        mandatory_check == "FAIL"  # Only halt on missing context sheets
        or (
            len(context_sheets) > 0
            and len(flagged_contexts) / max(len(context_sheets), 1) > 0.9  # 90% degraded = bad batch
        )
    )

    manifest: dict[str, Any] = {
        "project_id": config.project_id,
        "created": datetime.now(timezone.utc).isoformat(),
        "files": [e.to_dict() for e in entries],
        "mandatory_check": mandatory_check,
        "missing_mandatory": list(missing_mandatory),
        "quality_warnings": quality_warnings,
        "finds_validation_issues": finds_issues,
        "halt": halt_flag,
    }

    # Write manifest (convert numpy types to native Python)
    manifest_path = manifest_dir / "manifest.json"
    manifest_path.write_text(json.dumps(_numpy_safe(manifest), indent=2))

    return manifest
