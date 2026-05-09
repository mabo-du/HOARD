"""erd.templates — Jurisdiction template engine.

Loads YAML template files from templates/{jurisdiction_code}.yaml and
provides schema validation, section ordering, required field checking,
and prohibited term scanning.

exports: TemplateEngine, TemplateSchema  (classes)
used_by: erd.phases.phase4, erd.cli.templates
rules:   Templates must be pure YAML — no embedded logic. Adding a new
         jurisdiction must not require pipeline code changes.
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Initial scaffold
"""
