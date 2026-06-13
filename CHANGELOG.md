# Changelog

All notable changes to HOARD are documented here. This project follows
[Semantic Versioning](https://semver.org/) and the format is based on
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [0.3.7] — 2026-06-14

### Added

- **`--gui-mode` flag** — `hoard run` now accepts `--gui-mode` which
  suppresses Rich console output and emits structured JSON events to
  stdout. Each pipeline milestone produces a JSON line consumable by
  desktop GUI tools (Trowel).
- **Event schema** — 9 event types covering the full pipeline lifecycle:

  | Event | Fires when | Payload |
  |-------|-----------|---------|
  | `phase_start` | A phase begins | phase, name |
  | `phase_skip` | A phase is skipped (already complete) | phase, name |
  | `phase_complete` | A phase finishes successfully | phase, status, metrics |
  | `phase_error` | A phase errors out | phase, error, hint |
  | `pipeline_halt` | Pipeline halts on Phase 0 failures | reason |
  | `review_required` | Phase generated flagged review items | phase, flagged_count, path |
  | `progress` | Item-level progress in long-running phases | phase, current, total, item |
  | `info` | Generic information message | message |

  All events pass through regardless of hardware tier. Ultra-light
  (cloud-only) users get the same GUI integration as local GPU users.
- **`progress` events** in Phase 1 and Phase 2 processing loops —
  Phase 1 emits progress per context sheet, Phase 2 per photo.
- **`review_required` events** after phases 0-4 when flagged items
  exist — lets Trowel pause and surface a review modal.
- **Event system** moved to `hoard.helpers.emit()` so any module can
  emit events. Set via `set_gui_mode(bool)` or `--gui-mode` CLI flag.
- **Research synthesis** — `docs/research-prompts/ux-research-synthesis.md`
  resolves two deep-research reports on CLI-to-GUI accessibility.
  Pivotal fact confirmed: Trowel has standalone PyInstaller builds,
  making Trowel integration the right first GUI move.

## [0.3.0] — 2026-06-12

### Added

- **Provider abstraction integration** — all 8 inference call sites across
  phases 1-4 now route through `ProviderRouter` instead of raw `requests.post()`
  calls to Ollama. Audit logging, cost tracking, and provider selection/fallback
  are now functional.
- **`route_sync()` method** on `ProviderRouter` — bridges async provider
  implementations to synchronous phase callers via `asyncio.run()`.
- **`generate_via_provider()` helper** in `hoard.helpers` — converts legacy
  Ollama payload format to `InferenceRequest`, handles reasoning chain
  extraction (`<think>` tags), and returns compat dict.
- **NuExtract3 extraction handler** — 407-line custom `NuExtract3ChatHandler`
  (Strategy 5 from research paper) now committed and wired into Phase 1 as
  an alternative extraction engine alongside GLM-OCR.

### Changed

- **`config.yaml` → `config.toml`** — file was always parsed as TOML but
  misleadingly named `.yaml`. All references updated across config, router,
  phase5, and the template.
- **`erd_workspace` → `hoard_workspace`** — all 14 references to the old
  project name in CLI defaults, docstrings, and tests renamed.
- **Docstring updates** — phase3, phase4, and providers updated to reflect
  provider abstraction; stale `Ollama API` section headers replaced.

### Fixed

- **Non-image file handling in Phase 0** — CSV, XLSX, TXT, DOCX, MD, DXF, and
  SVG files were silently ignored because the entry loop only processed
  normalised images. Non-image files now get direct entries.
- **Phase 0 halt threshold** — corrected from 99% (effective dead code) to 90%,
  matching the code comment's documented intent.
- **Phase 3 chunked token counting** — `total_tokens` now correctly sums
  `eval_count` from overview and all per-period LLM calls.
- **Phase 5 error handling** — export phase now wrapped in `try/except`,
  matching phases 1-4. `run_single_phase()` also gained error handling.
- **51 ruff lint violations** across 22 files resolved.
- **8 mypy type errors** resolved (docx stubs, content shadowing, PIL LANCZOS
  deprecation, Ollama payload types, ProviderRouter `.split()` bug).
- **9 test failures** resolved (sentence-transformers skip, phase0 CSV handling,
  Rich ANSI CLI output check).
- **5 missing dependencies** added to `[dev]` extras: `requests`, `docling`,
  `markdown`, `numpy`, `wand`.

### Removed

- **`erd_workspace/` directory** — stale test projects using old name deleted.
- **`src/hoard_erd.egg-info/`** — stale build artifact deleted.
- **Unused `requests` and `OLLAMA_BASE_URL` imports** from phases 1-4 after
  provider migration.
- **`in_table` dead state variable** from `docx_writer.py`.

## [0.2.3] — 2026-06-12

### Fixed

- **GitHub Release artifacts** — corrected artifact paths in release workflow
  so standalone executables are attached to GitHub Releases.
- **51 ruff lint violations** — resolved all pre-existing lint errors across
  22 files (unused imports, unused variables, f-strings without placeholders,
  undefined names, local-import variable shadowing in `main.py`).

## [0.2.2] — 2026-06-12

### Fixed

- **CI workflow** — switched from `uv pip install --system` to venv-based
  install to fix "externally managed" error on newer GitHub Actions runners.
  All subsequent steps (ruff, mypy, pytest, CLI verification) now source
  `.venv/bin/activate`.
- **Release workflow** — `uvx build` replaced with `uvx --from build
  pyproject-build` after the `build` package renamed its entry point.
  Removed redundant `uv venv` calls (setup-uv already creates `.venv`).
- **PyPI publishing** — distribution name changed from `hoard` to `hoard-erd`
  after discovering a 2013 name collision on PyPI. Import package remains
  `hoard`.

### Dependencies

- **heritage-models** v1.0.0 now published to PyPI, unblocking CI and
  release builds that previously failed on dependency resolution.

## [0.2.1] — 2026-06-12

### Fixed

- **Phase 3 chunked token counting** — `total_tokens` now correctly sums
  `eval_count` from the overview and all per-period LLM calls. Previously the
  calculation only counted the overview result twice and discarded all
  per-period token data.
- **Phase 0 halt threshold** — quality gate threshold corrected from 99% (which
  effectively never fired) to 90%, matching both the code comment and documented
  intent. The user-facing halt message now also displays the correct threshold.
- **Phase 5 error handling** — export phase now wrapped in `try/except
  RuntimeError` matching the pattern used by phases 1-4, preventing pipeline
  crash on export failure. `run_single_phase()` also gained error handling for
  all phases.
- **Google Gemini token tracking** — provider now extracts `usageMetadata`
  (`promptTokenCount`, `candidatesTokenCount`, `totalTokenCount`) from Gemini
  API responses instead of returning zero tokens.
- **ProviderRouter project scoping** — singleton factory now maintains
  per-project instances so audit logs are correctly scoped. Previously all
  projects shared a single instance with the first project's ID.
- **Finds catalogue path resolution** — Phase 0 now falls back to `assets_dir`
  when a finds catalogue path relative to `input_dir` is not found, fixing
  silent validation skip for catalogues normalised from PDFs.
- **Review dashboard thresholds** — quality flag descriptions now display the
  correct threshold values (blur <10.0, skew >45°, exposure <15) that match
  the actual constants in Phase 0.
- **TEI-XML export** — now converts Markdown structure (`##` → `<div
  type="section"><head>`, blank-line blocks → `<p>`) instead of cramming
  everything into a single escaped paragraph.
- **Bibliography regex** — now captures `et al.`, multi-author (`&`/`and`),
  and hyphenated surname citation patterns.

### Changed

- **Shared utility consolidation** — `load_json_safe`, `find_json_files`, and
  `evict_ollama_model` extracted from duplicate phase-level definitions into
  new `hoard.helpers` module. `OLLAMA_BASE_URL` now defined once in helpers
  instead of four separate hardcoded copies across phases 1-4.
- **Docling converter reuse** — `DocumentConverter()` is now instantiated once
  before the catalogue processing loop instead of per-file, reducing overhead.
- **models package docstring** — updated from stale placeholder referencing
  non-existent `ModelLoader`/`ModelRouter` classes to accurate status.

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

[Unreleased]: https://github.com/mabo-du/HOARD/compare/v0.3.7...HEAD
[0.3.7]: https://github.com/mabo-du/HOARD/compare/v0.3.6...v0.3.7
[0.3.0]: https://github.com/mabo-du/HOARD/compare/v0.2.3...v0.3.0
[0.2.3]: https://github.com/mabo-du/HOARD/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/mabo-du/HOARD/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/mabo-du/HOARD/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/mabo-du/HOARD/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mabo-du/HOARD/releases/tag/v0.1.0
