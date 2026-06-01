# HOARD User Guide

**Heritage Observation And Report Drafter** — a fully local, multi-stage AI
pipeline that converts archaeological field data into near-publication-ready
grey literature reports.

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Project Initialisation](#project-initialisation)
4. [Running the Pipeline](#running-the-pipeline)
5. [ARK Direct Data Input](#ark-direct-data-input)
6. [Reviewing Flags](#reviewing-flags)
7. [Exporting Reports](#exporting-reports)
8. [Jurisdiction Templates](#jurisdiction-templates)
9. [Pipeline Phases](#pipeline-phases)
10. [Harris Matrix](#harris-matrix)
11. [Configuration](#configuration)
12. [GPU Setup](#gpu-setup)
13. [Troubleshooting](#troubleshooting)

---

## Installation

### Prerequisites

- **Python 3.11+**
- **pip** (Python package manager)
- **[Ollama](https://ollama.com)** — for local model inference (Phases 1-4)
- **8 GB+ VRAM GPU** recommended — RTX 3070 Laptop verified

HOARD uses Ollama for all GPU inference. No cloud API calls or pandoc required —
DOCX is generated via python-docx and PDF/A-2b via WeasyPrint.

### Install HOARD

```bash
# From PyPI (once published)
pip install hoard-erd

# From source
git clone https://github.com/mabo-du/HOARD.git
cd HOARD
pip install -e ".[dev]"
```

### Verify Installation

```bash
erd --version
erd --help
```

You should see the CLI banner and available commands.

---

## Quick Start

```bash
# 1. Initialise a project
erd init "Stoneyfield Farm 2026" --jurisdiction historic_england_cl3

# 2. Place your field records in ./input/:
#    - Context sheets (JPG, PNG, PDF)
#    - Finds catalogues (CSV, XLSX)
#    - Site photographs (JPG, PNG)
#    - Plans and section drawings (PDF, SVG, PNG)

# 3a. Option A — Run Phase 0 for paper field records (no GPU needed)
erd run --project stoneyfield_2026 --phase 0

# 3b. Option B — Import from ARK if your site uses digital recording
#     (bypasses Phase 0 and Phase 1 OCR entirely)
# erd import-ark --project stoneyfield_2026 --input ./ark_exports/

# 4. Review any flagged items
erd review --project stoneyfield_2026

# 5. Run the full pipeline (GPU-dependent phases will be skipped)
erd run --project stoneyfield_2026
```

---

## Project Initialisation

```bash
erd init "Project Name" --jurisdiction <code> --output ./erd_workspace
```

| Option | Description | Default |
|--------|-------------|---------|
| `name` | Project name (required, positional) | — |
| `--jurisdiction` / `-j` | Jurisdiction template code | `historic_england_cl3` |
| `--output` / `-o` | Working directory root | `./erd_workspace` |

This creates: `./erd_workspace/{project_id}/config.yaml`

---

## Running the Pipeline

```bash
# Full pipeline
erd run --project <id>

# Single phase
erd run --project <id> --phase <N>

# From phase N onward
erd run --project <id> --from-phase <N>

# Specify input and workspace directories
erd run --project <id> --input ./field_records/ --workspace ./my_workspace
```

The pipeline is **resumable** — completed phases are automatically skipped.
To force re-run a phase, use `--phase` explicitly.

### Current Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 0 | Ingestion & Triage | ✅ Complete (no GPU) |
| 1 | Multi-Modal Digitisation | ⏳ GPU-dependent |
| 2 | Spatial Reconstruction | ⏳ GPU-dependent |
| 3 | Synthesis & Drafting | ⏳ GPU-dependent |
| 4 | Compliance Refinement | ⏳ GPU-dependent |
| 5 | Assembly & Export | ✅ Complete (no GPU) |

---

## ARK Direct Data Input

For excavations already using the **ARK (Archaeological Recording Kit)** digital
recording system, HOARD can import structured excavation data directly —
bypassing Phase 0 (file ingestion) and Phase 1 (OCR) entirely.

### When to Use ARK Import

Use `erd import-ark` when your excavation already records data digitally using
ARK or compatible systems. This applies to most commercial archaeology units
and many research excavations. The import saves approximately 2–4 hours of
pipeline time by skipping file triage and OCR for those records.

ARK import handles **5 data types:**

| Table | ARK Export File | Records Created |
|-------|-----------------|-----------------|
| Context sheets | `context.csv` / `contexts.csv` / `ctx_register.csv` | Context descriptions, interpretations, periods, dimensions |
| Finds catalogue | `finds.csv` / `finds_catalogue.csv` / `sf_register.csv` | Object types, materials, quantities, weights |
| Sample register | `samples.csv` / `sample.csv` / `environmental.csv` | Sample types, volumes, processing status |
| Photo log | `photos.csv` / `photo.csv` / `photo_log.csv` | Filenames, context links, directions |
| Drawing register | `drawings.csv` / `drawing.csv` / `plans.csv` | Drawing numbers, types, scales, draughtspersons |

### Basic Usage

```bash
cd my_project
erd import-ark --project stoneyfield_2026 --input ./ark_export/
```

Where `./ark_export/` contains the CSV or JSON files exported from ARK.

### Supported Formats

- **CSV** — standard comma-separated with header row. UTF-8 BOM is handled
  automatically. Common ARK field name variants are recognised.
- **JSON** — top-level arrays or wrapped in `{"data": [...]}` / `{"results": [...]}`
  (matching common ARK JSON export formats).

### Field Mapping

HOARD recognises ARK field names case-insensitively and maps them to the
internal schema. Common variants are pre-configured:

| ARK Source Field | Mapped To | Example |
|------------------|-----------|---------|
| `context_id`, `context_number`, `context_no`, `context`, `ctx` | `context_number` | `1001` |
| `trench_code`, `trench` | `trench` | `T1` |
| `object_type`, `object`, `type` (finds) | `object_type` | `Pottery` |
| `quantity`, `count`, `qty` | `quantity` | `12` |
| `weight_g`, `weight` | `weight_g` | `45.2` |
| `sample_type`, `type` (samples) | `sample_type` | `Bulk soil` |
| `file_name`, `filename`, `image` | `filename` | `IMG_101.jpg` |
| `drawing_no`, `drawing_number` | `drawing_number` | `D001` |

Unrecognised columns produce a warning but do not block the import. If your
ARK instance uses custom field names not in the mapping table, the import
still succeeds for all recognised fields — the unrecognised data is preserved
in the original export for offline reference.

### After Import

Once the import completes:

1. A **manifest** is written to `00_manifest/manifest.json` with synthetic
   file entries for each ARK table.
2. **Digitised records** are written to `01_digitised/` as individual JSON
   files — one per ARK row — matching the format expected by Phase 5
   assembly.
3. **Pipeline state** marks Phase 0 and Phase 1 as **bypassed**:

```
Phases 0 and 1 have been marked as bypassed. You can proceed
with Phase 2+ as normal.
```

You can then run subsequent phases directly:

```bash
# Skip straight to Phase 5 assembly (no GPU needed)
erd run --project stoneyfield_2026 --phase 5
```

When GPU models become available, you can run Phase 2+ normally:

```bash
erd run --project stoneyfield_2026 --from-phase 2
```

### Output Example

```json
// 01_digitised/context_0000.json
{
    "_source": "context",
    "_ark_fields_mapped": 6,
    "context_number": "1001",
    "trench": "T1",
    "description": "Dark brown silty clay",
    "interpretation": "Colluvial layer",
    "period": "Medieval",
    "context_type": "layer"
}
```

---

## Reviewing Flags

After running Phase 0 (and later phases), you can review flagged items:

```bash
erd review --project stoneyfield_2026
```

The review dashboard presents each flagged item one at a time:

```
┌── Review #p0_ctx_001_BLUR_LOW (1/3) ──────────────────────────┐
│ Phase: 0   File: assets/context_sheet_001.png                  │
│ Field: _quality   Confidence: N/A                              │
│ Issue: Image blur score 31.1 (threshold: 80)                   │
│                                                                │
│ Current value: BLUR_LOW                                        │
└────────────────────────────────────────────────────────────────┘

[a]ccept  [e]dit  [d]efer  [s]ummary  [q]uit
```

### Review Actions

| Key | Action | Description |
|-----|--------|-------------|
| `a` | Accept | Mark the flag as reviewed (AI value is acceptable) |
| `e` | Edit | Provide a corrected value and optional notes |
| `d` | Defer | Skip for now, revisit later |
| `s` | Summary | Show progress summary |
| `q` | Quit | Exit review session (progress saved in memory) |

After all items are reviewed or on quit, you can choose to save corrections
back to the workspace JSON files. Corrections update the pipeline state so
you can re-run from the corrected phase.

---

## Exporting Reports

```bash
erd export --project stoneyfield_2026 --format docx,pdf,zip
```

| Option | Description | Default |
|--------|-------------|---------|
| `--project` / `-p` | Project ID (required) | — |
| `--format` / `-f` | Comma-separated formats | `docx,pdf` |

Available formats: `docx`, `pdf`, `tei-xml`, `zip`

Output goes to: `./erd_workspace/{project_id}/05_final/`

> **Note:** Export requires Phase 5 implementation. Currently supports
> Markdown output; DOCX/PDF via pandoc is in development.

---

## Jurisdiction Templates

HOARD ships with **14 jurisdiction templates** for heritage authority
reporting standards:

```bash
# List all templates
erd templates list

# Show template details (coming soon)
erd templates show historic_england_cl3

# Validate a template file
erd templates validate ./my_template.yaml
```

### Available Jurisdictions

| Code | Authority | Region |
|------|-----------|--------|
| `historic_england_cl3` | Historic England — Evaluation | England |
| `historic_england_cl4` | Historic England — Excavation | England |
| `historic_environment_scotland` | HES — Data Structure Report | Scotland |
| `wales_rcahmw` | Cadw / RCAHMW | Wales |
| `ireland_nms` | National Monuments Service | Ireland |
| `netherlands_kna` | KNA 5.0 | Netherlands |
| `france_inrap` | INRAP / Code du Patrimoine | France |
| `germany_denkmalpflege` | Landesdenkmalpflege | Germany |
| `us_section106` | Section 106 (NRHP) | United States |
| `canada_ontario` | Ontario S&G | Canada |
| `australia_burra` | Burra Charter (ICOMOS) | Australia |
| `new_zealand` | Heritage NZ Pouhere Taonga | New Zealand |
| `south_africa_sahra` | SAHRA | South Africa |
| `international_generic` | Generic fallback | Any |

### Adding a New Template

1. Create a new YAML file in the `templates/` directory
2. Follow the schema from an existing template
3. No code changes required — the engine discovers templates automatically

```yaml
# templates/my_jurisdiction.yaml
jurisdiction: "My Heritage Authority — Excavation Report"
version: "2025"
mandatory_sections:
  - id: executive_summary
    label: "Executive Summary"
    max_words: 300
    required_fields:
      - project_name
      - ngr
# ... see existing templates for full schema
```

---

## Pipeline Phases

### Phase 0: Ingestion & Triage

*Rule-based, zero VRAM.*

- Enumerates all input files
- Converts HEIC/RAW/PDF to normalised PNG
- Runs image quality checks: blur, skew, exposure
- Classifies document types (context sheet, finds form, photo, etc.)
- Validates finds catalogue CSV/XLSX column headers
- Writes manifest.json with quality flags

### Phase 1: Multi-Modal Digitisation *(GPU-dependent)*

- Context sheet OCR via **GLM-OCR** (Ollama, 2.2 GB model) — *default*
- Alternative extractor: **NuExtract3** (Ollama, 2.7 GB Q4_K_M GGUF) — opt-in via `--extractor nuextract3`
  - 56% better schema adherence than base Qwen3.5-4B (0.651 vs 0.417 on structured extraction benchmarks)
  - RL-trained for exact JSON template following — reduced checkbox post-processing needed
  - Requires model pull first: `ollama pull hf.co/numind/NuExtract3-GGUF:Q4_K_M`
- Degraded document fallback via **Qwen3-VL-8B** (Ollama)
- Finds catalogue parsing via **Docling** (CPU-based)
- Pydantic structured output enforcement
- Post-extraction checkbox normalisation (cross/filled → boolean)
- Outputs validated against shared JSON Schema contract (`schemas/context-sheet-v1.json`)
- Use `--strict` flag to halt on schema validation failures
- Peak VRAM: ~2.8 GB (GLM-OCR), ~3.5 GB (NuExtract3)

### Phase 2: Spatial Reconstruction *(GPU-dependent)*

- Site photo and plan analysis via **Qwen3-VL-8B** (Ollama)
- Auto-captioning with fills/colour/ROMFA inclusion descriptions
- **Manifest-based filtering**: only `site_photo` and `plan` files processed
  (context sheets excluded from photo plates automatically)
- SVG section drawing generation from all images (for Phase 3 reference)
- Photo plates generated only if Phase 2 output exists
- Peak VRAM: ~3.5 GB (Qwen3-VL-8B)

### Phase 3: Synthesis & Drafting *(GPU-dependent)*

- Context assembly from all Phase 1-2 outputs
- Structured Markdown draft via **huihui_ai/qwen3.5-abliterated:4B** (Ollama)
- 10-section report structure: summary, intro, geology, methodology, results by area,
  results by period, finds, discussion, bibliography, appendix reference
- Human review triggers for uncertainty, conflicts, and missing sections
- Chunk-and-merge for large sites (500+ contexts) with per-period context filtering
- Peak VRAM: ~2.8 GB

### Phase 4: Compliance Refinement *(GPU-dependent)*

- Section-by-section compliance checking against jurisdiction template
- Template field defaults: 11 defaults with `{project_id}`, `{project_name}`,
  `{current_date}` template variables (eliminates most `[MISSING:]` placeholders)
- Prohibited term replacement (scientifically inaccurate language)
- Mandatory section verification and placeholder insertion
- Heading style correction and figure caption formatting
- Via **tripolskypetr/gemma4-uncensored-aggressive** (Ollama)
- Peak VRAM: ~2.1 GB

### Phase 5: Assembly & Export

*Rule-based, zero VRAM.*

- Figure resolution and embedding, photo plates from Phase 2 captions
- Appendix generation (context register, finds concordance, sample register)
- Harris Matrix SVG generation from inferred stratigraphic relationships
- Bibliography extraction from Phase 3 draft content
- **DOCX export** via `python-docx` (45 KB, archaeological template styling)
- **PDF/A-2b export** via WeasyPrint (80 MB with embedded context sheet images)
- **TEI-XML lightweight** semantic export for archival/LOD pipelines
- **PAdES digital signature** via pyHanko (optional — requires signing key)
- **ZIP archive** packaging all outputs
- Markdown draft always preserved as source

---

## Harris Matrix

HOARD generates a stratigraphic Harris Matrix SVG from context sheet
relationships. This is produced automatically during Phase 5, or can be
generated standalone:

```python
from erd.review import generate_harris_matrix

result = generate_harris_matrix(
    context_files=list(Path("01_digitised").glob("*.json")),
    output_path=Path("harris_matrix.svg"),
    title="Stoneyfield Farm 2026",
)
```

The matrix is colour-coded by period:

| Period | Colour |
|--------|--------|
| Prehistoric | Brown |
| Roman | Red |
| Medieval | Blue |
| Post-Medieval | Green |
| Modern | Grey |
| Undated | Light Grey |

Arrows point from later contexts to earlier contexts (standard Harris
convention). No graphviz is required — the renderer is pure Python.

---

## StratiGraph Integration

StratiGraph is a companion web app that visualises stratigraphic matrices from
HOARD Phase 1 output. It runs entirely in the browser — no backend required.

### Data Contract

HOARD and StratiGraph share a JSON Schema contract at `schemas/context-sheet-v1.json`.
Both projects validate against the same schema independently.

- **HOARD** writes `schema_version: "1.0.0"` into every Phase 1 output and
  runs advisory schema validation (use `--strict` to halt on violations)
- **StratiGraph** validates HOARD JSON files on import and warns about
  any schema mismatches

### Importing HOARD Output into StratiGraph

```bash
# 1. Start StratiGraph
cd ~/Projects/StratiGraph/app
npm install
npm run dev
# Opens at http://localhost:5173

# 2. Click Import → HOARD JSON Import tab

# 3. Select all ctx_sheet_*.json files from your HOARD project's
#    01_digitised/ directory. Hold Shift for multi-select.

# 4. Review the summary: contexts, relationships, any warnings

# 5. Click "Generate Harris Matrix"
```

### What Happens on Import

Each HOARD JSON is parsed into an HMDP (Harris Matrix Data Package) context:

| HOARD Field | HMDP Mapping | StratiGraph Usage |
|-------------|-------------|-------------------|
| `context_number` | `id` | Node label in graph |
| `type` | `type` (`Positive`/`Negative`/`Unknown`) | Node colour/shape |
| `description` + `interpretation` | `description` | Sidebar display |
| `period` | `period` | Period colour coding |
| `cuts` | `Above` relationships | Directed edges |
| `cut_by` | `Above` (reversed) | Directed edges |
| `fills` | `Above` relationships | Directed edges |
| `filled_by` | `Above` (reversed) | Directed edges |
| `same_as` | `Equals` relationships | Horizontal alignment |

**Stub contexts** are automatically created for any context IDs referenced
in relationship fields but whose sheet wasn't imported (e.g., a cut referenced
from a fill's `fills` field). These appear as `Unknown` type contexts for
manual identification.

### StratiGraph Features

- **DAG validation**: automatic cycle detection and transitive reduction
- **Harris Matrix rendering**: auto-layout via Cytoscape.js + Dagre
- **Publication mode**: free-drag nodes into pixel-perfect alignment
- **Phase grouping**: colour-coded period boxes
- **Finds heatmap**: density-based colouring by finds quantity
- **HOARD export**: generate EEDP (linear chronological paths) for AI prompts
- **Libby/OxCal export**: Bayesian chronological modelling integration
- **Export**: PNG, SVG, PDF

---

## Configuration

Projects are configured via `erd_workspace/{project_id}/config.yaml`:

```yaml
# HOARD project: Stoneyfield Farm 2026
project_id: stoneyfield_2026
project_name: Stoneyfield Farm 2026
jurisdiction: historic_england_cl3
```

The `Config` object is immutable after creation:

| Field | Description |
|-------|-------------|
| `project_id` | URL-safe project identifier |
| `project_name` | Human-readable project name |
| `jurisdiction` | Template code for compliance |
| `workspace_root` | Parent directory of all project workspaces |
| `input_dir` | Directory containing field records |

---

## GPU Setup

Phases 1–4 require a CUDA-capable GPU with at least 6 GB VRAM.

### Recommended hardware

- NVIDIA RTX 3060 (12 GB) or better
- NVIDIA RTX 4060 (8 GB)
- NVIDIA RTX 4070 (12 GB)
- M-series Mac with unified memory (16 GB+)

### Software requirements

```bash
# CUDA toolkit (Linux)
sudo apt-get install nvidia-cuda-toolkit

# Verify GPU is available
python -c "import torch; print(torch.cuda.is_available())"
```

### Ollama models

All GPU inference runs via Ollama. Pull models before first use:

```bash
# Phase 1: Context sheet OCR
ollama pull glm-ocr:latest

# Phase 1 fallback: Degraded document processing
ollama pull qwen3-vl:8b

# Phase 2: Photo/plan captioning
ollama pull qwen3-vl:8b  # (same model, shared with Phase 1 fallback)

# Phase 3: Report drafting
ollama pull huihui_ai/qwen3.5-abliterated:4B

# Phase 4: Compliance refinement
ollama pull tripolskypetr/gemma4-uncensored-aggressive:latest

# Verify all models
ollama list
```

Models load and evict sequentially — HOARD calls `/api/generate` with
`keep_alive: 0` to unload from VRAM when each phase finishes.

### VRAM budget

| Phase | Peak VRAM | Model(s) |
|-------|-----------|---------|
| 1 | ~2.8 GB | GLM-OCR (Ollama, 2.2 GB) |
| 2 | ~3.5 GB | Qwen3-VL-8B (Ollama) |
| 3 | ~2.8 GB | huihui_ai/qwen3.5-abliterated:4B (Ollama) |
| 4 | ~2.1 GB | tripolskypetr/gemma4-uncensored-aggressive (Ollama) |

Models load and clear sequentially — peak VRAM never exceeds the single
largest model at any moment. Benchmark with `--benchmark` flag:
```bash
PYTHONPATH=src python3 -m erd run \
    --project pinn_brook_park_2026 \
    --workspace /tmp/pinnbrook \
    --benchmark
```
This logs per-phase VRAM peak/average, GPU temperature, power draw,
and Ollama model memory to `logs/benchmarks/`.

---

## Troubleshooting

### "No input files found"

Ensure your field records are in the `./input/` directory (or specify with
`--input`). Accepted formats: JPG, PNG, PDF, HEIC, CSV, XLSX, DXF, SVG, TXT,
DOCX, MD.

### "Mandatory file check failed"

Pipeline requires at least:
- Context sheets (one or more)
- Finds catalogue (CSV, XLSX, or form image)

### "Phase X is not yet implemented"

Phases 1–4 require GPU. Run Phase 0 and Phase 5 only for now:

```bash
erd run --project <id> --phase 0
erd run --project <id> --phase 5
```

### "Review dashboard shows no flags"

Run a phase first to generate data:
```bash
erd run --project <id> --phase 0
erd review --project <id>
```

### "WeasyPrint fails on PDF export"

WeasyPrint requires system-level rendering libraries:

```bash
# Ubuntu/Debian
sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0

# Fedora
sudo dnf install pango cairo gdk-pixbuf2
```

### "Schema validation warnings during Phase 1"

This is normal for OCR-extracted data — some fields may have minor format
differences. Review the warnings in the log output. Use `--strict` if you
want Phase 1 to halt on validation failure for manual review.

### "HOARD JSON import in StratiGraph shows no relationships"

GLM-OCR extracts form text but cannot reliably parse the Harris Matrix
diagram drawn on the context sheet. Relationships (cuts, fills) are only
present if the OCR captured them from the form text. This is a known
limitation — relationships must be added manually in StratiGraph or
entered via CSV import.

### "No module named 'torch'"

PyTorch is only needed for GPU phases. The CPU-only phases (0, 5) and
the review dashboard work without it.

---

## CLI Reference

```bash
erd <command> [options]
```

### Global Options

| Option | Description |
|--------|-------------|
| `--version` / `-V` | Show version and exit |
| `--help` | Show help message |

### Commands

| Command | Description |
|---------|-------------|
| `init` | Initialise a new project |
| `run` | Run the pipeline (full or partial) |
| `import-ark` | Import structured data from ARK system exports |
| `review` | Open the review dashboard |
| `export` | Export final report |
| `templates` | List, show, or validate templates |

### `erd init`

```bash
erd init <name> [options]
```

| Argument | Description |
|----------|-------------|
| `name` | Project name (positional, required) |

| Option | Default |
|--------|---------|
| `--jurisdiction` / `-j` | `historic_england_cl3` |
| `--output` / `-o` | `./erd_workspace` |

### `erd run`

```bash
erd run [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--project` / `-p` | — | Project ID (required) |
| `--input` / `-i` | `./input` | Input directory |
| `--strict` / `-s` | `False` | Halt Phase 1 if schema contract validation fails |
| `--extractor` / `-e` | `glm-ocr` | Phase 1 extraction model: `glm-ocr` (default) or `nuextract3` |
| `--phase` | — | Run single phase only |
| `--from-phase` | — | Run from phase N onward |
| `--workspace` / `-w` | `./erd_workspace` | Workspace root |

### `erd import-ark`

```bash
erd import-ark [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--project` / `-p` | — | Project ID (required) |
| `--input` / `-i` | `./input` | Directory containing ARK export files |
| `--workspace` / `-w` | `./erd_workspace` | Workspace root |

Accepts CSV or JSON exports. Recognises context sheets, finds catalogues,
sample registers, photo logs, and drawing registers. Marks Phase 0 and Phase 1
as bypassed in pipeline state.

### `erd review`

```bash
erd review [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--project` / `-p` | — | Project ID (required) |
| `--workspace` / `-w` | `./erd_workspace` | Workspace root |
| `--reset` / `-r` | `False` | Reset all review decisions |

### `erd export`

```bash
erd export [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--project` / `-p` | — | Project ID (required) |
| `--format` / `-f` | `docx,pdf` | Output formats |
| `--workspace` / `-w` | `./erd_workspace` | Workspace root |

### `erd templates`

```bash
erd templates <action> [options]
```

| Action | Description |
|--------|-------------|
| `list` | List all available templates |
| `show` | Show template details (use `--name`) |
| `validate` | Validate a template file (use `--file`) |

---

## Project Structure

```
my_project/
├── input/                          # Place field records here
│   ├── context_sheet_001.jpg
│   ├── context_sheet_002.pdf
│   ├── finds_catalogue.csv
│   ├── site_photos/
│   └── plans/
├── erd_workspace/
│   └── stoneyfield_2026/
│       ├── config.yaml             # Project configuration
│       ├── pipeline_state.json     # Resumable pipeline state
│       ├── 00_manifest/
│       │   └── manifest.json       # File inventory and quality flags
│       ├── 01_digitised/           # Phase 1 JSON outputs
│       ├── 02_spatial/             # Phase 2 geometry and captions
│       ├── 03_draft/               # Phase 3 Markdown sections
│       ├── 04_refined/             # Phase 4 compliance reports
│       ├── 05_final/               # Final exported reports
│       ├── assets/                 # Normalised images
│       └── logs/                   # Per-phase logs
└── templates/
    ├── historic_england_cl3.yaml   # Jurisdiction templates
    └── ...
```

---

## Support

- **Issues:** https://github.com/mabo-du/HOARD/issues
- **Repository:** https://github.com/mabo-du/HOARD

Licensed under MIT. Built for the archaeological community.
