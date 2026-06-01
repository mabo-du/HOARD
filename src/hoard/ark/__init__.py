"""hoard.ark — ARK system direct data input (bypasses Phase 1 OCR).

For digital-first excavations using the ARK (Archaeological Recording Kit)
system, structured data can be imported directly — bypassing Phase 0 file
ingestion and Phase 1 multi-modal digitisation.

exports: import_ark_export, ArkImportResult
used_by: hoard.cli.main  → `hoard import-ark` command
rules:   Must never import torch or any GPU-bound library. Exported data
         must be compatible with Phase 5+ pipeline stages.
"""

from hoard.ark.loader import ArkImportResult, import_ark_export
from hoard.ark.mapping import guess_mapping_from_header, transform_row
from hoard.ark.semantic_mapper import ArkSemanticMapper, map_headers_semantic

__all__ = [
    "ArkImportResult",
    "ArkSemanticMapper",
    "import_ark_export",
    "guess_mapping_from_header",
    "map_headers_semantic",
    "transform_row",
]
