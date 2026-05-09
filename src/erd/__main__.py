"""__main__.py — Allow `python -m erd` as alternative to `erd` CLI.

usage: python -m erd --help
used_by: developer workflow
rules:   Must delegate to erd.cli.main:entry_point
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Initial scaffold
"""

from erd.cli.main import entry_point

entry_point()
