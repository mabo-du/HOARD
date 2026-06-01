"""hoard.review — Review dashboard logic.

Manages the terminal-based review interface (rich/textual) where the
site director can accept, correct, or defer flagged items from any phase.

exports: ReviewSession, ReviewItem, ReviewDecision, FlagSource, load_flags_from_manifest,
         generate_harris_matrix, render_harris_svg, StratigraphicNode
used_by: hoard.cli.review, hoard.phases.phase5
rules:   Must support accept / edit / defer workflow. Edited values must
         be written back to the phase output JSON. Pipeline state must
         update to allow re-run from the corrected phase.
         Harris Matrix generation must not require graphviz.
"""

from hoard.review.dashboard import (
    FlagSource,
    ReviewDecision,
    ReviewItem,
    ReviewSession,
    load_flags_from_manifest,
    load_flags_from_workspace,
)
from hoard.review.harris import (
    StratigraphicNode,
    generate_from_json_list,
    generate_harris_matrix,
    render_harris_svg,
)

__all__ = [
    "FlagSource",
    "ReviewDecision",
    "ReviewItem",
    "ReviewSession",
    "StratigraphicNode",
    "generate_from_json_list",
    "generate_harris_matrix",
    "load_flags_from_manifest",
    "load_flags_from_workspace",
    "render_harris_svg",
]
