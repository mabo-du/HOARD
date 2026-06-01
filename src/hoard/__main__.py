"""__main__.py — Allow `python -m hoard` as alternative to `hoard` CLI.

usage: python -m hoard --help
used_by: developer workflow
rules:   Must delegate to hoard.cli.main:entry_point
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Initial scaffold
"""

from hoard.cli.main import entry_point

entry_point()
