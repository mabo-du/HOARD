# Changelog

All notable changes to HOARD are documented here. This project follows
[Semantic Versioning](https://semver.org/) and the format is based on
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [0.2.0] — 2026-06-09

### Added

- **Multi-provider AI abstraction layer** — `hoard.providers` package with
  `ModelProvider` protocol, provider implementations for Ollama, OpenAI,
  Anthropic, and Google Gemini, hardware auto-profiling, 4-tier model system
  (Ultra-light → Performance), and credential management via AES-256-GCM
  encrypted vault (`hoard keys` CLI).
- **Provider routing** — 3 modes (Manual/Auto/Quality), per-phase provider
  selection, fallback chains, privacy tiers (Strict Local/Sanitized Cloud/
  Full Hybrid), and per-request cost tracking with audit logging.
- **Schema unification** — new `heritage-types` repository with TypeSpec
  source defining 8 canonical data models (StratigraphicUnit, Find, Sample,
  Chronology, etc.) compiled to JSON Schema Draft 2020-12, with auto-generated
  Pydantic v2 Python package (`heritage-models`) and TypeScript interfaces
  (`@heritage/types`).
- **Cross-project CLI** — `heritage-cli` meta-package providing unified
  `heritage` command routing to sibling tools (run/calibrate/lithics/review/
  matrix/publish/tools).
- **Pipeline orchestration** — declarative `pipeline.yaml` format with
  checkpoint-based execution, human review gates, pipeline state persistence
  for resumability, and graceful degradation for missing tools.
- **Offline vocabulary service** — `heritage-vocab` library for Getty
  AAT/ULAN/TGN term lookup, with built-in fallback covering common
  archaeological materials and periods (no database required).
- **Unified template format** — jurisdiction templates now support tool-specific
  extension blocks (`hoard:` and `trowel:` namespaces) alongside a shared core,
  backward compatible with all 14 existing templates.
- **Cross-platform release workflow** — GitHub Actions building standalone
  PyInstaller executables for Linux (x86_64), macOS (arm64), and Windows
  (x86_64), plus PyPI publishing via trusted publishing.

### Changed

- **Renamed CLI** — `erd` → `hoard` (breaking change for existing scripts).
- **Schemas directory** — replaced local schema copies with symlink to
  `heritage-types` canonical repository; `context-sheet-v1.json` and
  `context-relationships-v1.json` superseded by `heritage-data-package-v1.json`.
- **Phase 1 validation** — now uses `heritage-models.StratigraphicUnit`
  Pydantic validation instead of standalone `jsonschema`.
- **CI** — updated to modern uv syntax, fixed stale `erd` references,
  ignores pre-existing GPU-bound test failures.

### Fixed

- `load_config()` — YAML parsing now implemented (was `# TODO`, returned `None`).
- `templates show` — now displays template YAML with Rich syntax highlighting
  (was "not yet loaded" placeholder).
- `templates validate` — now runs structural compliance checks (was
  "validator not yet implemented").
- `export` — wired to Phase 5 `run_phase5()` (was dead code path printing
  "not yet built").

## [0.1.0] — 2026-05-09

### Added

- **Phase 0** — Ingestion & Triage: file inventory, format normalisation
  (HEIC/RAW/PDF→PNG), OpenCV quality assessment (blur/skew/exposure),
  filename-based classification, CSV/XLSX validation.
- **Phase 1** — Multi-Modal Digitisation: GLM-OCR (Ollama) for context sheet
  extraction, Docling+Granite-Docling-258M for tables, pandas for CSV/XLSX,
  typed note parser, checkbox normalisation, schema validation against
  shared contract.
- **Phase 2** — Spatial Reconstruction: Qwen3-VL-8B photo captioning,
  cross-check against context sheet data, GLM-OCR SVG vectorisation for
  field section drawings.
- **Phase 3** — Synthesis & Drafting: Qwen3.5-4B reasoning with thinking-mode
  capture, chunk-and-merge for large sites (>70K chars), section extraction
  with review trigger detection.
- **Phase 4** — Compliance Refinement: Gemma 4-E2B section-by-section
  editing, template-driven restructuring, prohibited term scanning, word
  count enforcement, `[MISSING:]` placeholder insertion.
- **Phase 5** — Assembly & Export: DOCX via python-docx, PDF/A-2b via
  WeasyPrint, rectpack photo plates, TEI-XML wrapper, ZIP archive,
  optional PAdES digital signatures via pyHanko.
- **Template engine** — 14 jurisdiction templates (England, Scotland, Wales,
  Ireland, Netherlands, France, Germany, US, Canada, Australia, New Zealand,
  South Africa, plus generic fallback), YAML-based with `extends` inheritance.
- **Review dashboard** — interactive Rich TUI for reviewing AI-flagged items
  (accept/edit/defer), correction write-back, pipeline state invalidation.
- **Harris Matrix** — pure-Python SVG generator (no graphviz), topological
  level assignment, period-colour-coded nodes, arrow rendering.
- **ARK import** — direct data input from ARK system exports (CSV/JSON),
  semantic header matching via sentence-transformers, Phase 0/1 bypass.
- **VRAM benchmark module** — `pynvml`-based GPU telemetry (VRAM/temperature/
  power), Ollama `/api/ps` model stats, per-phase timing metrics.
- **Deep research library** — 8 research prompts covering all pipeline phases,
  model selection, VRAM benchmarking, fine-tuning strategy, cloud LLM
  blockers, and NuExtract3 integration.
- **E2E test datasets** — Pinn Brook Park (49 contexts, CC-BY 4.0), A14
  Cambridge to Huntingdon (99 contexts), Gallows Hill (50-70 contexts).

[Unreleased]: https://github.com/mabo-du/HOARD/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/mabo-du/HOARD/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mabo-du/HOARD/releases/tag/v0.1.0
