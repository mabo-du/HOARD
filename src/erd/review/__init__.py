"""erd.review — Review dashboard logic.

Manages the terminal-based review interface (rich/textual) where the
site director can accept, correct, or defer flagged items from any phase.

exports: ReviewSession, ReviewItem, ReviewDecision  (classes)
used_by: erd.cli.review
rules:   Must support accept / edit / defer workflow. Edited values must
         be written back to the phase output JSON. Pipeline state must
         update to allow re-run from the corrected phase.
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Initial scaffold
"""
