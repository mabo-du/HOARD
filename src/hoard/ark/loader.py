"""loader.py — ARK export data importer.

Discovers ARK system export files (CSV/JSON), maps fields to HOARD's
internal representation, and writes structured data directly into the
workspace — bypassing Phase 0 file ingestion and Phase 1 OCR for
digital-first excavations.

exports: import_ark_export, ArkImportResult
used_by: hoard.cli.main  → `hoard import-ark` command
rules:   Must never import torch or any GPU-bound library.
         Generated manifests must be compatible with Phase 5+ pipeline stages.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hoard.ark.mapping import (
    ARK_CONTEXT_FIELDS,
    ARK_DRAWINGS_FIELDS,
    ARK_FINDS_FIELDS,
    ARK_PHOTOS_FIELDS,
    ARK_SAMPLES_FIELDS,
    SOURCE_TYPE_MAP,
    guess_mapping_from_header,
    transform_row,
)
from hoard.config import Config
from hoard.workspace import PipelineState

# ── Data contracts ─────────────────────────────────────────────────────────

IMPORT_TABLES: dict[str, dict[str, Any]] = {
    "context": {
        "filename_patterns": ("context", "contexts", "ctx_register"),
        "mapping": ARK_CONTEXT_FIELDS,
        "output_key": "context_sheets",
    },
    "finds": {
        "filename_patterns": ("finds", "small_finds", "finds_catalogue", "sf_register"),
        "mapping": ARK_FINDS_FIELDS,
        "output_key": "finds",
    },
    "samples": {
        "filename_patterns": ("samples", "sample", "environmental"),
        "mapping": ARK_SAMPLES_FIELDS,
        "output_key": "samples",
    },
    "photos": {
        "filename_patterns": ("photos", "photo", "images", "photo_log"),
        "mapping": ARK_PHOTOS_FIELDS,
        "output_key": "photos",
    },
    "drawings": {
        "filename_patterns": ("drawings", "drawing", "plans", "section_drawings"),
        "mapping": ARK_DRAWINGS_FIELDS,
        "output_key": "drawings",
    },
}


class ArkImportResult:
    """Result of an ARK import operation."""

    def __init__(self) -> None:
        self.files_found: int = 0
        self.files_parsed: int = 0
        self.total_records: int = 0
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.records_by_type: dict[str, int] = {}
        self.manifest_path: Path | None = None
        self.digitised_data: list[dict[str, Any]] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_found": self.files_found,
            "files_parsed": self.files_parsed,
            "total_records": self.total_records,
            "records_by_type": self.records_by_type,
            "errors": self.errors,
            "warnings": self.warnings,
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
        }


# ── File discovery ─────────────────────────────────────────────────────────


def _discover_ark_files(input_dir: Path) -> list[tuple[Path, str]]:
    """Find ARK export files in input_dir.

    Returns list of (file_path, source_type) tuples.
    """
    found: list[tuple[Path, str]] = []
    if not input_dir.is_dir():
        return found

    for f in sorted(input_dir.iterdir()):
        if not f.is_file() or f.name.startswith("."):
            continue
        stem = f.stem.lower()

        for table_name, table_config in IMPORT_TABLES.items():
            if stem in table_config["filename_patterns"]:
                found.append((f, table_name))
                break

    return found


# ── CSV parsing ─────────────────────────────────────────────────────────────


def _parse_csv(filepath: Path) -> list[dict[str, Any]]:
    """Parse a CSV file into a list of row dicts."""
    rows: list[dict[str, Any]] = []
    try:
        with open(filepath, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cleaned = {k.strip(): v.strip() if v else "" for k, v in row.items()}
                rows.append(cleaned)
    except Exception as e:
        raise ValueError(f"Failed to parse CSV {filepath}: {e}") from e
    return rows


# ── JSON parsing ────────────────────────────────────────────────────────────


def _parse_json(filepath: Path) -> list[dict[str, Any]]:
    """Parse a JSON file into a list of row dicts.

    Handles both top-level arrays and {'data': [...]} wrappers.
    """
    raw = json.loads(filepath.read_text())
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        # Common ARK JSON export wrappers
        for key in ("data", "results", "records", "rows", "items"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]
    raise ValueError(f"Unrecognised JSON structure in {filepath}")


# ── Per-type processing ─────────────────────────────────────────────────────


def _process_table(
    filepath: Path,
    source_type: str,
    mapping_table: list[tuple[str, str, str | None]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse and transform one ARK export file.

    Returns (transformed_records, warnings).
    """
    warnings: list[str] = []

    # Parse
    if filepath.suffix.lower() == ".json":
        raw_rows = _parse_json(filepath)
    else:
        raw_rows = _parse_csv(filepath)

    if not raw_rows:
        return [], [f"Empty file: {filepath.name}"]

    # Infer mapping from first row's headers
    header = list(raw_rows[0].keys())
    field_map = guess_mapping_from_header(header, mapping_table)

    if not field_map:
        return [], [f"No recognised ARK fields in {filepath.name}"]

    unrecognised = len(header) - len(field_map)
    if unrecognised > 0:
        warnings.append(f"{filepath.name}: {unrecognised} unrecognised column(s) ignored")

    # Transform
    records = [transform_row(row, field_map, source_type) for row in raw_rows]

    return records, warnings


# ── Data-source manifest generation ─────────────────────────────────────────


def _build_manifest(
    project_id: str,
    records_by_type: dict[str, int],
    errors: list[str],
    warnings: list[str],
    digitised_dir: Path,
) -> dict[str, Any]:
    """Build a Phase-0-compatible manifest for ARK-imported data."""
    manifest: dict[str, Any] = {
        "project_id": project_id,
        "created": datetime.now(timezone.utc).isoformat(),
        "import_method": "ark",
        "ark_direct_input": True,
        "phase0_bypassed": True,
        "phase1_bypassed": True,
        "total_records": sum(records_by_type.values()),
        "records_by_type": records_by_type,
        "files": [],
        "mandatory_check": "PASS",
        "missing_mandatory": [],
        "quality_warnings": 0,
        "finds_validation_issues": [],
        "halt": False,
        "import_errors": errors,
        "import_warnings": warnings,
        "digitised_dir": str(digitised_dir),
    }

    # Build synthetic file entries for the manifest (Phase 5 needs these)
    for source_type, count in records_by_type.items():
        hoard_type = SOURCE_TYPE_MAP.get(source_type, "unknown")
        manifest["files"].append({
            "id": f"ark_{source_type}",
            "path": f"ark_import/{source_type}.csv",
            "type": hoard_type,
            "quality": {},
            "ark_record_count": count,
        })

    return manifest


# ── Digitised data ──────────────────────────────────────────────────────────


def _write_digitised_data(
    records: list[dict[str, Any]],
    digitised_dir: Path,
    prefix: str,
) -> None:
    """Write transformed records as digitised-phase-style JSON files.

    Each record becomes its own JSON file (compatible with Phase 5's
    expectation of per-record JSON in 01_digitised/).
    """
    digitised_dir.mkdir(parents=True, exist_ok=True)
    for i, record in enumerate(records):
        record_path = digitised_dir / f"{prefix}_{i:04d}.json"
        record_path.write_text(json.dumps(record, indent=2))


# ── Main import ─────────────────────────────────────────────────────────────


def import_ark_export(config: Config) -> ArkImportResult:
    """Import ARK system export data for a project.

    Discovers ARK export files in config.input_dir, maps fields to HOARD's
    internal representation, and writes structured data into the workspace.

    Returns an ArkImportResult describing what was imported.
    """
    result = ArkImportResult()
    project_dir = config.project_dir
    manifest_dir = config.manifest_dir
    digitised_dir = config.digitised_dir

    project_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    # Discover ARK export files
    ark_files = _discover_ark_files(config.input_dir)
    result.files_found = len(ark_files)

    if not ark_files:
        result.errors.append("No ARK export files found")
        return result

    all_records: list[dict[str, Any]] = []
    records_by_type: dict[str, int] = {}

    for filepath, source_type in ark_files:
        mapping_table = IMPORT_TABLES[source_type]["mapping"]
        try:
            records, warnings = _process_table(filepath, source_type, mapping_table)
        except ValueError as e:
            result.errors.append(str(e))
            continue

        result.warnings.extend(warnings)
        result.files_parsed += 1

        if records:
            prefix = source_type
            _write_digitised_data(records, digitised_dir, prefix)
            all_records.extend(records)
            records_by_type[source_type] = len(records)
            result.total_records += len(records)

    result.records_by_type = records_by_type
    result.digitised_data = all_records

    # Generate manifest
    manifest = _build_manifest(
        config.project_id,
        records_by_type,
        result.errors,
        result.warnings,
        digitised_dir,
    )

    manifest_path = manifest_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    result.manifest_path = manifest_path

    # Update pipeline state: mark Phase 0 and Phase 1 as bypassed
    state = PipelineState(project_dir / "pipeline_state.json")
    state.complete_phase(
        0,
        summary=f"Bypassed via ARK import — {result.total_records} records from {result.files_parsed} files",
    )
    state.complete_phase(
        1,
        summary="Bypassed via ARK import — digital-first excavation data already structured",
    )

    return result
