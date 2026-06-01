"""hoard.cli — Typer CLI entry points for hoard commands.

exports: app  (typer.Typer) — main CLI application
used_by: pyproject.toml → `hoard` console_scripts entry
rules:   All subcommands must print usage and exit gracefully before
         their phase implementation exists. Never require a GPU.
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Initial scaffold
"""
