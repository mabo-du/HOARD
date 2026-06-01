"""semantic_mapper.py — Lightweight semantic header mapping for ARK imports.

Replaces exact string-match column mapping with cosine-similarity embedding,
allowing HOARD to recognise ARK field names it has never seen before.
Runs entirely on CPU. Falls back gracefully if sentence-transformers is
not installed.

exports: ArkSemanticMapper, map_headers_semantic
used_by: hoard.ark.mapping  → guess_mapping_from_header
rules:   Must never import torch or any GPU-bound library.
         Must handle missing sentence-transformers gracefully.
         Embedding model loads lazily on first use (not at import time).
"""

from __future__ import annotations

import logging
from typing import Any

from hoard.ark.mapping import (
    ARK_CONTEXT_FIELDS,
    ARK_DRAWINGS_FIELDS,
    ARK_FINDS_FIELDS,
    ARK_PHOTOS_FIELDS,
    ARK_SAMPLES_FIELDS,
)

logger = logging.getLogger(__name__)

# ── Abbreviation expansion ──────────────────────────────────────────────────
# Before embedding, ARK column headers are pre-processed to expand common
# archaeological and database abbreviations into full words that the
# embedding model can better interpret.

ABBREVIATION_MAP: dict[str, str] = {
    "ctx": "context",
    "cxt": "context",
    "sf": "smallfind",
    "no": "number",
    "nr": "number",
    "id": "identifier",
    "ref": "reference",
    "desc": "description",
    "qty": "quantity",
    "mat": "material",
    "vol": "volume",
    "flot": "flotation",
    "env": "environmental",
    "arch": "archaeological",
    "strat": "stratigraphic",
    "geom": "geometry",
    "elev": "elevation",
    "grid": "gridreference",
    "ngr": "nationalgridreference",
    "her": "heritagerecord",
    "oas": "oasisidentifier",
    "ax": "accession",
    "mcm": "ministryofcitizenship",
    "ape": "areapotentialeffect",
    "photo_notes": "photo notes annotations",
    "ctx_description": "context description text",
    "recorded_by_initials": "recorded by person initials",
    "image_filename": "image file name",
    "view_direction": "view direction facing",
    "deposit_description": "description text content",
    "trench_name": "trench name code designation",
}


def _expand_abbreviations(header: str) -> str:
    """Expand known abbreviations in a column header.

    Splits on underscore/camelCase, expands each token, rejoins with
    spaces for embedding. Example: 'ctx_id' → 'context identifier'.
    """
    import re

    # Split on underscore or camelCase boundary
    tokens = re.split(r"[_\s]+", header)
    expanded = []
    for token in tokens:
        # Handle camelCase (e.g. 'trenchName' → ['trench', 'name'])
        sub_tokens = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$|\d)", token)
        if not sub_tokens:
            sub_tokens = [token]
        for st in sub_tokens:
            st_lower = st.lower()
            expanded.append(ABBREVIATION_MAP.get(st_lower, st_lower))
    return " ".join(expanded)


# ── Embedding similarity threshold ─────────────────────────────────────────

# Minimum cosine similarity for a semantic match to be accepted.
# Below this threshold, the static fallback mapping is used instead.
SIMILARITY_THRESHOLD = 0.30

# ── Canonical HOARD field descriptors ──────────────────────────────────────
# These are used to compute reference embeddings. Each HOARD field has a
# descriptive phrase that helps the embedding model understand its semantics.

CANONICAL_FIELDS: dict[str, str] = {
    # Context sheet fields
    "context_number": "context number identifier",
    "trench": "trench trench code area",
    "area": "area zone excavation",
    "description": "description text content",
    "interpretation": "interpretation archaeological",
    "period": "period chronological date",
    "period_detail": "period detail detailed sub period",
    "phase": "phase stratigraphic phase number",
    "date_from": "date from start earliest",
    "date_to": "date to end latest",
    "context_type": "context type layer cut fill",
    "recorded_by": "recorded by recorder name initials",
    "recorded_date": "recorded date recording",
    "length_m": "length metres dimension",
    "width_m": "width metres dimension",
    "depth_m": "depth thickness metres",
    "grid_ref": "grid reference coordinate",
    "easting": "easting coordinate easting",
    "northing": "northing coordinate northing",
    "elevation_m": "elevation height metres",
    "soil": "soil composition sediment",
    "colour": "colour color soil",
    "compaction": "compaction consistency deposit",
    "inclusions": "inclusions gravel charcoal",
    "relationships": "stratigraphic relationships",
    "strat_group": "stratigraphic group number",
    "comments": "comments notes extra annotations remarks",
    # Finds catalogue fields
    "find_number": "find number small find identifier",
    "object_type": "object type category finds",
    "material": "material composition",
    "sub_material": "sub material type specific",
    "quantity": "quantity count number sherds",
    "weight_g": "weight grams mass",
    "manufacture_tech": "manufacture technique technology",
    "condition": "condition preservation state",
    "completeness": "completeness how complete",
    "refit": "refit vessel joining",
    "bag_number": "bag number lot finds",
    "dating": "dating date chronological finds",
    # Sample register fields
    "sample_number": "sample number identifier",
    "sample_type": "sample type soil flot C14",
    "volume_ml": "volume millilitres sample",
    "processed": "processed processing status yes no",
    "process_method": "process method processing technique",
    "flot_fraction": "flot fraction flotation",
    "residue_fraction": "residue fraction residue",
    # Photo log fields
    "photo_id": "photo identifier image number",
    "filename": "filename file name image path",
    "direction": "direction facing view photograph",
    "photographer": "photographer person who took photo",
    "date_taken": "date taken photograph captured",
    "scale_info": "scale information photograph",
    # Drawing register fields
    "drawing_number": "drawing number identifier",
    "drawing_type": "drawing type section plan elevation",
    "sheet_number": "sheet number page multi page",
    "scale": "scale drawing scale",
    "draughtsperson": "draughtsperson drawn by person",
    "date_drawn": "date drawn drawing recorded",
}

# ── Mapping tables for reference phrases ───────────────────────────────────

MAPPING_TABLES: dict[str, list[tuple[str, str, str | None]]] = {
    "context": ARK_CONTEXT_FIELDS,
    "finds": ARK_FINDS_FIELDS,
    "samples": ARK_SAMPLES_FIELDS,
    "photos": ARK_PHOTOS_FIELDS,
    "drawings": ARK_DRAWINGS_FIELDS,
}


class ArkSemanticMapper:
    """Lightweight semantic header mapper for ARK CSV/JSON exports.

    Uses sentence-transformers (all-MiniLM-L6-v2) on CPU to embed ARK
    column headers and match them to canonical HOARD field names via
    cosine similarity. Falls back to static mapping if the embedding
    model is unavailable.

    The model loads lazily on first call to map_headers() — not at
    construction time. This means instantiating the class is cheap.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._reference_embeddings: dict[str, Any] | None = None
        self._available: bool | None = None  # None = not yet checked

    def _load_model(self) -> bool:
        """Try to load sentence-transformers. Returns True if available."""
        if self._available is not None:
            return self._available

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            self._available = True
            logger.debug("ArkSemanticMapper: loaded all-MiniLM-L6-v2 on CPU")
        except ImportError:
            logger.info("ArkSemanticMapper: sentence-transformers not installed; using static fallback")
            self._available = False
        except Exception as e:
            logger.warning("ArkSemanticMapper: failed to load embedding model: %s; using static fallback", e)
            self._available = False

        return self._available

    def _compute_reference_embeddings(self) -> None:
        """Pre-compute embeddings for all canonical HOARD field names."""
        if self._reference_embeddings is not None or not self._available or self._model is None:
            return

        field_names = list(CANONICAL_FIELDS.keys())
        descriptions = list(CANONICAL_FIELDS.values())
        embeddings = self._model.encode(descriptions, convert_to_tensor=False, show_progress_bar=False)

        self._reference_embeddings = dict(zip(field_names, embeddings))

    def map_headers(
        self,
        headers: list[str],
        source_type: str = "context",
    ) -> dict[str, str]:
        """Match ARK column headers to HOARD field names using semantic similarity.

        Args:
            headers: List of column header strings from the ARK export.
            source_type: One of 'context', 'finds', 'samples', 'photos', 'drawings'.

        Returns:
            {hoard_field_name: ark_column_name} mapping dict.
        """
        if not headers:
            return {}

        if not self._load_model():
            return {}

        self._compute_reference_embeddings()
        if self._reference_embeddings is None:
            return {}

        # Pre-process: expand abbreviations, then embed
        expanded_headers = [_expand_abbreviations(h) for h in headers]
        logger.debug("Semantic mapper expanded headers: %s", dict(zip(headers, expanded_headers)))
        ark_embeddings = self._model.encode(expanded_headers, convert_to_tensor=False, show_progress_bar=False)

        import numpy as np

        # Build reference embedding matrix
        ref_names = list(self._reference_embeddings.keys())
        ref_vectors = np.array([self._reference_embeddings[n] for n in ref_names])

        # Normalise
        ark_norm = ark_embeddings / np.linalg.norm(ark_embeddings, axis=1, keepdims=True)
        ref_norm = ref_vectors / np.linalg.norm(ref_vectors, axis=1, keepdims=True)

        # Cosine similarity matrix
        similarity = np.dot(ark_norm, ref_norm.T)  # (num_ark_cols, num_hoard_fields)

        result: dict[str, str] = {}
        assigned_hoard: set[str] = set()

        # Greedy assignment: for each ARK header, pick best matching unassigned HOARD field
        for i, ark_col in enumerate(headers):
            # Sort HOARD fields by similarity descending
            best_idx = int(np.argmax(similarity[i]))
            best_score = float(similarity[i][best_idx])

            if best_score < SIMILARITY_THRESHOLD:
                continue

            best_hoard = ref_names[best_idx]

            # If this HOARD field is already taken, try next best
            if best_hoard in assigned_hoard:
                # Find next best unassigned
                order = np.argsort(similarity[i])[::-1]
                for idx in order:
                    candidate = ref_names[int(idx)]
                    if candidate not in assigned_hoard and float(similarity[i][int(idx)]) >= SIMILARITY_THRESHOLD:
                        best_hoard = candidate
                        best_score = float(similarity[i][int(idx)])
                        break
                else:
                    continue  # No unassigned field found

            result[best_hoard] = ark_col
            assigned_hoard.add(best_hoard)

        return result


# ── Convenience function ────────────────────────────────────────────────────

_SEMANTIC_MAPPER: ArkSemanticMapper | None = None


def map_headers_semantic(
    headers: list[str],
    source_type: str = "context",
) -> dict[str, str]:
    """Convenience function: one-shot semantic header mapping.

    Uses a module-level singleton ArkSemanticMapper. Returns an empty dict
    if sentence-transformers is not installed.
    """
    global _SEMANTIC_MAPPER
    if _SEMANTIC_MAPPER is None:
        _SEMANTIC_MAPPER = ArkSemanticMapper()
    return _SEMANTIC_MAPPER.map_headers(headers, source_type)
