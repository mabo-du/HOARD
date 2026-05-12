"""mapping.py — ARK export field mappings and data transformations.

Maps ARK system column names (which vary by instance customisation) to
HOARD's internal representation. Supports CSV and JSON export formats.

exports: ARK_FIELD_MAPS, ark_context_mapping, ark_finds_mapping,
         ark_samples_mapping, ark_photos_mapping, guess_mapping_from_header
used_by: erd.ark.loader
rules:   All mappings are data-only — no imports from GPU-bound libraries.
         Mapping tables can be extended by users via config overrides.
"""

from __future__ import annotations

from typing import Any

# ── Default field mappings ─────────────────────────────────────────────────
# Each entry: (ARK_column, map_to, transform_fn_or_None)

ARK_CONTEXT_FIELDS: list[tuple[str, str, str | None]] = [
    ("context_id",       "context_number",  None),
    ("context_number",   "context_number",  None),
    ("context_no",       "context_number",  None),
    ("context",          "context_number",  None),
    ("ctx",              "context_number",  None),
    ("trench_code",      "trench",          None),
    ("trench",           "trench",          None),
    ("area",             "area",            None),
    ("description",      "description",     None),
    ("interpretation",   "interpretation",  None),
    ("period",           "period",          None),
    ("period_detail",    "period_detail",   None),
    ("phase",            "phase",           None),
    ("date_from",        "date_from",       None),
    ("date_to",          "date_to",         None),
    ("type",             "context_type",    None),
    ("category",         "context_type",    None),
    ("filled_by",        "recorded_by",     None),
    ("recorded_by",      "recorded_by",     None),
    ("recorded_date",    "recorded_date",   None),
    ("length_m",         "length_m",        None),
    ("width_m",          "width_m",         None),
    ("depth_m",          "depth_m",         None),
    ("grid_reference",   "grid_ref",        None),
    ("easting",          "easting",         None),
    ("northing",         "northing",        None),
    ("elevation_m",      "elevation_m",     None),
    ("soil_components",  "soil",            None),
    ("colour",           "colour",          None),
    ("compaction",       "compaction",      None),
    ("inclusions",       "inclusions",      None),
    ("relationships",    "relationships",   None),
    ("stratigraphic_group", "strat_group",  None),
    ("group",            "strat_group",     None),
    ("comments",         "comments",        None),
    ("notes",            "comments",        None),
]

ARK_FINDS_FIELDS: list[tuple[str, str, str | None]] = [
    ("context_id",       "context_number",  None),
    ("context_number",   "context_number",  None),
    ("context_no",       "context_number",  None),
    ("context",          "context_number",  None),
    ("find_id",          "find_number",     None),
    ("small_find_no",    "find_number",     None),
    ("sf_no",            "find_number",     None),
    ("object_type",      "object_type",     None),
    ("object",           "object_type",     None),
    ("type",             "object_type",     None),
    ("material",         "material",        None),
    ("material_1",       "material",        None),
    ("sub_material",     "sub_material",    None),
    ("quantity",         "quantity",        None),
    ("count",            "quantity",        None),
    ("qty",              "quantity",        None),
    ("weight_g",         "weight_g",        None),
    ("weight",           "weight_g",        None),
    ("period",           "period",          None),
    ("dating",           "period",          None),
    ("date",             "period",          None),
    ("description",      "description",     None),
    ("comments",         "comments",        None),
    ("manufacture",      "manufacture_tech", None),
    ("technology",       "manufacture_tech", None),
    ("preservation",     "condition",       None),
    ("condition",        "condition",       None),
    ("completeness",     "completeness",    None),
    ("refit",            "refit",           None),
    ("bag_no",           "bag_number",      None),
    ("grid_reference",   "grid_ref",        None),
]

ARK_SAMPLES_FIELDS: list[tuple[str, str, str | None]] = [
    ("context_id",       "context_number",  None),
    ("context_number",   "context_number",  None),
    ("sample_id",        "sample_number",   None),
    ("sample_no",        "sample_number",   None),
    ("sample_type",      "sample_type",     None),
    ("type",             "sample_type",     None),
    ("volume_ml",        "volume_ml",       None),
    ("volume",           "volume_ml",       None),
    ("weight_g",         "weight_g",        None),
    ("processed",        "processed",       None),
    ("process_method",   "process_method",  None),
    ("flot_fraction",    "flot_fraction",   None),
    ("residue_fraction", "residue_fraction", None),
    ("description",      "description",     None),
    ("comments",         "comments",        None),
    ("period",           "period",          None),
]

ARK_PHOTOS_FIELDS: list[tuple[str, str, str | None]] = [
    ("photo_id",         "photo_id",        None),
    ("file_name",        "filename",        None),
    ("filename",         "filename",        None),
    ("image",            "filename",        None),
    ("context_id",       "context_number",  None),
    ("context_number",   "context_number",  None),
    ("direction",        "direction",       None),
    ("direction_taken",  "direction",       None),
    ("description",      "description",     None),
    ("caption",          "description",     None),
    ("taken_by",         "photographer",    None),
    ("photographer",     "photographer",    None),
    ("date_taken",       "date_taken",      None),
    ("scale",            "scale_info",      None),
]

ARK_DRAWINGS_FIELDS: list[tuple[str, str, str | None]] = [
    ("drawing_id",       "drawing_number",  None),
    ("drawing_no",       "drawing_number",  None),
    ("drawing_number",   "drawing_number",  None),
    ("context_id",       "context_number",  None),
    ("context_number",   "context_number",  None),
    ("drawing_type",     "drawing_type",    None),
    ("type",             "drawing_type",    None),
    ("sheet_no",         "sheet_number",    None),
    ("description",      "description",     None),
    ("scale",            "scale",           None),
    ("drawn_by",         "draughtsperson",  None),
    ("date_drawn",       "date_drawn",      None),
    ("trench",           "trench",          None),
    ("area",             "area",            None),
]

# ── Mapped category lookup ─────────────────────────────────────────────────

SOURCE_TYPE_MAP: dict[str, str] = {
    "context": "context_sheet",
    "finds": "finds_catalogue",
    "samples": "sample_result",
    "photos": "site_photo",
    "drawings": "plan",
}

# ── Mapping resolver ────────────────────────────────────────────────────────


def _build_lookup(mappings: list[tuple[str, str, str | None]]) -> dict[str, str]:
    """Build a {lowercase_ark_column: hoard_field} lookup dict."""
    return {ark_col.lower(): hoard_field for ark_col, hoard_field, _ in mappings}


def guess_mapping_from_header(
    header: list[str],
    mapping_table: list[tuple[str, str, str | None]],
) -> dict[str, str]:
    """Match an export's header row against a mapping table.

    Returns {hoard_field: ark_column} — one entry per recognised field.
    Unrecognised columns are silently dropped.
    """
    lookup = _build_lookup(mapping_table)
    result: dict[str, str] = {}
    for col in header:
        col_lower = col.strip().lower()
        if col_lower in lookup:
            hoard_field = lookup[col_lower]
            if hoard_field not in result:  # first match wins
                result[hoard_field] = col
    return result


def transform_row(
    row: dict[str, Any],
    field_map: dict[str, str],
    source_type: str,
) -> dict[str, Any]:
    """Transform a single ARK row dict into a HOARD-structured record.

    Args:
        row: Raw ARK row (column_name → value).
        field_map: {hoard_field: ark_column} from guess_mapping_from_header.
        source_type: One of 'context', 'finds', 'samples', 'photos', 'drawings'.

    Returns:
        Transformed record dict with HOARD field names.
    """
    record: dict[str, Any] = {
        "_source": source_type,
        "_ark_fields_mapped": len(field_map),
    }
    for hoard_field, ark_column in field_map.items():
        value = row.get(ark_column, "")
        if isinstance(value, str):
            value = value.strip()
        record[hoard_field] = value
    return record
