"""hoard — Heritage Observation And Report Drafter.

Multi-stage AI pipeline converting archaeological field data into
near-publication-ready grey literature reports. Fully local, targets
6 GB VRAM, jurisdiction-templated.

exports: (package) — use hoard.cli.main:app as entry point
used_by: pyproject.toml → `hoard` CLI command
rules:   No model inference logic in this file; orchestration only.
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Initial scaffold
"""

__version__ = "0.1.0"
