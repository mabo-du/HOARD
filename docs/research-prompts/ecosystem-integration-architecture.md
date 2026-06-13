# HOARD — Ecosystem Integration Architecture

## Project Context (for the AI researcher)

**HOARD** (Heritage Observation And Report Drafter) is a fully local, multi-stage AI pipeline that converts archaeological field data — context sheets, finds catalogues, site photographs, section drawings, and sample results — into a near-publication-ready grey literature report. All 6 pipeline phases are implemented and E2E-verified with real archaeological data (Pinn Brook Park, CC-BY 4.0 via ADS). 14 jurisdiction templates exist.

HOARD is part of a larger **heritage science open-source ecosystem** under active development by the same developer. The ecosystem already has bidirectional integration with **StratiGraph** (interactive Harris Matrix viewer, shared JSON Schema contract) and **Trowel** (premium desktop report drafter, HOARD JSON import/export). Several other sibling projects exist in varying stages of maturity.

### The Core Problem

Each project in the ecosystem is being built independently with its own data models, JSON schemas, and import/export formats. There is no shared data model, no unified vocabulary backend, and no cross-project orchestration layer. This creates:

1. **Schema drift** — similar concepts (context sheets, finds, samples, stratigraphic relationships) are re-defined per project with subtly different field structures
2. **Duplicated integration code** — every project that needs Getty vocabulary, C14 calibration, or lithic classification must build its own bridge
3. **No cross-project pipeline** — a user cannot currently run HOARD Phase 0→1, visualise the matrix in StratiGraph, calibrate C14 dates in Libby, then finish the report in HOARD Phase 3→5 in a single workflow
4. **Inconsistent jurisdiction templates** — Trowel has 19 templates, HOARD has 14; they partially overlap but have no shared format

### The Ecosystem (projects that could integrate)

| Project | Function | Tech Stack | Maturity | Current Integration |
|---------|----------|------------|----------|-------------------|
| **HOARD** | AI grey-lit report pipeline | Python, Ollama, typer | ✅ Production (6 phases) | — |
| **StratiGraph** | Interactive Harris Matrix | Tauri 2, React, Cytoscape.js | ✅ Released | Shared JSON schema with HOARD |
| **Trowel** | Desktop report drafter | PyQt6, pandas, Jinja2 | ✅ Released | Bidirectional HOARD JSON import/export |
| **Libby** | Radiocarbon calibration | FastAPI, Svelte 5, iosacal | ✅ Released | None (StratiGraph exports OxCal CQL) |
| **Cache & Carry** | Offline CMS + Getty vocab | Tauri, Rust, cr-sqlite | ✅ Released | None |
| **Dibble** | 3D lithic analysis | Python, PyVista, scikit-learn | In development | Trowel reads Dibble CSV output |
| **DIG** | GPR/magnetometry processing | Rust/PyO3, PySide6 | In development | None |
| **Fritts** | Dendrochronology | PyQt6, scipy | In development | None |
| **Cartulary** | EAD finding-aid generator | TypeScript, Tauri 2 | ✅ Released | None |
| **Argus** | Satellite site surveillance | FastAPI, Celery, PostGIS | In development | None |
| **IsoMap** | Isotopic data standardisation | Tauri 2, React, Python | In development | None |

### What Already Exists

- **HOARD ↔ StratiGraph**: Shared `schemas/context-sheet-v1.json` and `schemas/context-relationships-v1.json` validated independently by both projects
- **HOARD ↔ Trowel**: `trowel/hoard_import.py` reads HOARD Phase 1 JSON; `trowel/hoard_export.py` writes HOARD-compatible format
- **StratiGraph ↔ Libby**: StratiGraph exports OxCal CQL sequences for Libby calibration
- **Trowel ↔ Cache & Carry**: Trowel has `vocab_terms.py` querying Cache & Carry's SQLite vocabulary DB
- **DIG implementation plan**: Explicitly cites HOARD as a sibling integration target
- **All projects**: MIT licensed, offline-first, consumer-hardware-friendly

### What Does NOT Yet Exist (gaps to research)

- A **shared core data model** (protocol, schema package, or contract) that all projects can import
- A **unified integration bus** that lets HOARD push data to StratiGraph → Libby → HOARD in a single pipeline
- **Cross-project jurisdiction template format** shared between HOARD and Trowel
- A **shared vocabulary service** wrapping Cache & Carry's Getty vocab for all projects
- **Event-driven pipeline triggers** (e.g., HOARD Phase 1 complete → auto-open in StratiGraph)
- **Cross-project CLI** (`hoard calibrate` calling Libby, `hoard lithics` calling Dibble, etc.)

---

## Research Questions

### Q1: Shared Data Model Design

Design a minimal, versioned, cross-project data model for archaeological field data that HOARD, Trowel, StratiGraph, Libby, Cache & Carry, Dibble, DIG, Fritts, Argus, and IsoMap can all import as a shared dependency.

**Key constraints:**
- Must not require a server, database, or network connection
- Must be implementable in Python (HOARD/Trowel/Dibble/Fritts/DIG) AND TypeScript (StratiGraph/Libby frontend/Cache & Carry/Cartulary) AND Rust (DIG core/Cache & Carry/StratiGraph)
- Must be versioned with a clear migration path
- Must NOT require a schema registry, GraphQL endpoint, or any runtime dependency beyond the language itself
- Each project should be able to use only the subset it needs (e.g., Libby doesn't need context sheet data)
- Must support both JSON (for file-based IPC) and native types (for in-process use)

**Questions to investigate:**

1. What format should the shared model take? Options:
   - A standalone JSON Schema registry (`schemas/*-v1.json` per project, cross-referenced by `$ref`)
   - A language-agnostic IDL (Protocol Buffers, FlatBuffers, Cap'n Proto) with code generation
   - A shared Python package (`heritage-models`) + TypeScript types package (`@heritage/types`)
   - Frictionless Data Table Schema (already used by StratiGraph's HMDP)
   - A dedicated crate: `heritage-core` in Rust with `pyo3` bindings and `wasm-pack` TypeScript types

2. What is the minimal set of shared types? Propose a hierarchy covering:
   - `StratigraphicUnit` / `ContextSheet` — shared by HOARD/StratiGraph/Trowel
   - `Find` (with material, type, weight, count sub-types) — HOARD/Trowel/Dibble
   - `Sample` (with environmental, C14, isotopic sub-types) — HOARD/Libby/IsoMap/Paleo
   - `Photo` / `Drawing` — HOARD/StratiGraph/Trowel
   - `Site` / `Project` metadata — all projects
   - `StratigraphicRelationship` — HOARD/StratiGraph/Trowel
   - `Chronology` (calibrated dates, HPD ranges, SPD data) — Libby/HOARD/Fritts

3. How should the cross-referencing work? For example, a Find references a StratigraphicUnit by ID — should that be a string UUID or a typed reference? What about cross-project references (HOARD context sheet → Libby calibration date)?

4. How do we handle **schema evolution**? If HOARD adds a field to ContextSheet in v2, does StratiGraph break? Propose a compatibility strategy (forward/backward, must-ignore-unknown-fields, etc.).

5. **Specific to the ecosystem**: Should we design a unified IPC protocol (JSON messages over stdio, Unix socket, or MCP protocol) that any project can speak, or is file-based IPC sufficient? What are the trade-offs?

### Q2: Cross-Project Pipeline Orchestration

Design an orchestration layer that lets a user run a single end-to-end archaeological workflow spanning multiple projects:

```
Field photos/context sheets (input)
  → HOARD Phase 0 (triage)
  → HOARD Phase 1 (digitise) 
  → StratiGraph (visualise/validate Harris Matrix)
  → Libby (calibrate C14 from samples)
  → Dibble (classify lithics)
  → HOARD Phase 3 (synthesise draft with all specialist data)
  → HOARD Phase 4 (compliance check)
  → HOARD Phase 5 (final report)
```

**Questions:**

1. Should orchestration be a **new CLI tool** (`heritage run --pipeline`) or an **extension of HOARD's existing `hoard run` command** (which already supports `--phase` and `--from-phase`)?

2. How should **cross-project data flow** work? For example, HOARD Phase 1 finds C14 samples → passes them to Libby → Libby returns calibrated ranges → HOARD Phase 3 includes them. What's the transport: files in a shared workspace, Unix sockets, MCP calls, or a pub/sub bus?

3. How should **state and resumability** work across projects? HOARD has `PipelineState` JSON per project. Should there be a unified `EcosystemState` that tracks which projects have processed which data?

4. What is the **failure model**? If Libby is not installed, should the pipeline (a) abort, (b) skip Libby-dependent sections, or (c) insert `[MISSING: C14 calibration — Libby not available]` placeholders?

5. How should **jurisdiction templates** be shared between HOARD and Trowel (currently 14 vs 19 with partial overlap)? Propose a unified template format with a common directory (`~/.config/heritage/templates/`) that both tools read. How would extension work (Trowel templates with fields HOARD doesn't need)?

### Q3: Unified Vocabulary Service

Cache & Carry provides sub-millisecond offline Getty AAT/ULAN/TGN lookup from a local SQLite database. Trowel already uses this for vocabulary autocomplete. HOARD Phase 1 (context sheet digitisation) and Phase 4 (compliance drafting) could benefit from standardised materials, periods, and artefact types.

**Questions:**

1. Should the vocabulary service be a **standalone MCP server** (like Courier's pattern) that any project can query over stdio or TCP, or an importable **library/SDK**?

2. What is the correct **query interface**? Propose a minimal API: `search(term, vocabulary, limit)` → `[{id, label, broader, narrower, alt_labels}]`. Should it support SPARQL-like queries or is simple term search sufficient?

3. How do we handle **period thesauri** differently from materials? Archaeological periods are hierarchical (Bronze Age → Late Bronze Age → Urnfield), hierarchical with geography (Hallstatt ≠ Hallstatt in UK), and sometimes contested. What's the right data model?

4. Can this vocabulary service also serve as the **normalisation backend** for HOARD Phase 1's context sheet extraction? Currently HOARD extracts free-text materials and periods from OCR and stores them as-is. A vocabulary-backed normalisation step could map "flint" → "Flint/Chert" (AAT: 300011754), etc.

5. Should the vocabulary service also handle **unit normalisation** (cm vs m, g vs kg, ppm vs %)?

### Q4: Cross-Project CLI Command Design

Design a unified `heritage` CLI that wraps the ecosystem commands consistently:

| Current | Proposed Unified |
|---------|-----------------|
| `hoard run --project X --phase 1` | `hoard run --project X --phase 1` (unchanged) |
| `hoard calibrate` (doesn't exist) | `heritage calibrate --project X` → calls Libby |
| `hoard lithics` (doesn't exist) | `heritage lithics --project X --input ./scans/` → calls Dibble |
| `trowel open --project X` | `heritage review --project X` |
| `stratigraph import` | `heritage matrix --project X` |
| `hoard export --format docx,pdf` | `heritage publish --project X --format docx,pdf` |

**Questions:**

1. Is a `heritage` CLI the right approach, or should each project remain independently callable with a shared `heritage-run` orchestration tool? What are the Python packaging implications?

2. Should the CLI be in a **separate package** (`heritage-cli`) that depends on the ecosystem projects, or a **meta-package** that re-exports their entry points?

3. What is the **discoverability** story? `heritage tools list` → shows installed ecosystem tools and their status?

4. How should **configuration** work? A single `~/.config/heritage/config.yaml` that each project reads, or per-project configs?

---

## Research Priority

**Q1 (Shared Data Model)** is the highest priority — everything else depends on it. Without a shared model, every integration requires ad-hoc mapping code that will drift apart over time.

**Q2 (Pipeline Orchestration)** is the highest-value outcome for users — a single command that runs the full ecosystem pipeline.

**Q3 (Vocabulary Service)** and **Q4 (CLI Design)** are important but can be prototyped independently.

---

## Deliverables

For each question, please provide:

1. **Recommendation** with clear rationale and trade-offs discussed
2. **Architecture diagram** (ASCII or Mermaid) showing the components and data flow
3. **Concrete implementation plan** — what files to create, what code to write, in what order
4. **Schema fragments** (JSON Schema, Protobuf, or TypeScript) for the key types
5. **Migration path** from current ad-hoc integration to unified system — can be incremental
6. **Risk assessment** — what could go wrong and how to mitigate

Focus on practical, implementable solutions. The entire ecosystem is maintained by a single developer working in evenings — any architecture that requires a team, a server, or a CI/CD pipeline to validate is not viable.

---

## Architect's Decisions (Confirmed 2026-06-08)

After reviewing four Deep Research papers covering both this prompt and the Multi-Provider AI Abstraction prompt, the following architectural decisions were confirmed:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **IDL approach** | TypeSpec → JSON Schema Draft 2020-12 | Multi-language compilation (Python/Rust/TS); JSON Schema remains the transport format |
| **Provider interface** | Python Protocol (not ABC) | More Pythonic, lighter than ABC |
| **Credential management** | Standalone AES-256-GCM YAML file (`~/.config/hoard/credentials.yaml.enc`) | Mirrors Kryptis schema; simpler to backup and reason about for 4-5 API keys |
| **Vocabulary service** | Python importable library wrapping Cache & Carry SQLite (NOT MCP) | MCP introduces subprocess lifecycle overhead; start simple, upgrade to MCP later |
| **Config format** | TOML (`~/.config/heritage/config.toml`) | `tomllib` is stdlib in Python 3.11+ |
| **Template format** | YAML with shared core + tool-specific extension blocks | Simpler than subdirectory approach; Paper 2's `hoard:`/`trowel:` extension pattern |
| **Orchestration** | Combined: YAML pipeline format + state machine execution | YAML defines the DAG, state machine drives resumability |
| **Review gates** | Checkpoint-based with human review; mandatory at key transitions | Archaeological synthesis needs expert validation |
| **Migration strategy** | Incremental, non-destructive overlay | Existing workflows continue unchanged; new capabilities are opt-in |
| **CLI approach** | Separate `heritage-cli` meta-package (Typer + Rich) | Non-destructive overlay on existing project CLIs |
| **Project timeline** | 4-6 months (not 2-3) | Other active projects limit focused availability |

**Implementation order (6 phases):**
1. **Phase A** — HOARD internal fixes (config parsing, CLI gaps, dead code)
2. **Phase B** — Multi-provider AI abstraction (parallel with C)
3. **Phase C** — Schema unification (parallel with B)
4. **Phase D** — Cross-project CLI
5. **Phase E** — Pipeline orchestration
6. **Phase F** — Unified vocabulary + templates
