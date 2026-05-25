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

- Distortion correction via PaddleOCR-VL-1.5 (conditional — only when flagged)
- Holistic layout + handwriting + checkbox extraction via Chandra OCR 2
- Complex table parsing via MinerU2.5-Pro-2604-1.2B
- All models load sequentially; peak VRAM ~2.8 GB

### Phase 2: Spatial Reconstruction *(GPU-dependent)*

- Initial visual grounding (bounding box extraction) via Florence-2-large
- Semantic captioning + cross-check vs. context sheets via Qwen3-VL-4B-Instruct
- Digital geometry from field drawings via 2D SVG vectorization (primary) or Build123d (optional 3D)

### Phase 3: Synthesis & Drafting *(GPU-dependent)*

- Context assembly from all Phase 1-2 outputs
- Structured Markdown draft via Qwen3-4B-Thinking-2507 (262K context)
- Human review triggers for uncertainty and conflicts
- Chunk-and-merge for large sites (500+ contexts)

### Phase 4: Compliance Refinement *(GPU-dependent)*

- Section-by-section compliance checking
- Mandatory section verification
- Prohibited term replacement
- Heading style correction
- Figure caption formatting

### Phase 5: Assembly & Export

*Rule-based, zero VRAM.*

- Figure resolution and embedding
- Appendix generation (context register, finds concordance, sample register)
- Harris Matrix SVG generation
- Bibliography extraction
- DOCX/PDF export via pandoc
- Archive ZIP packaging

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

### Model downloads

Models are downloaded automatically on first use via HuggingFace.
For offline environments, pre-download:

```bash
pip install huggingface-hub
huggingface-cli download datalab-to/chandra-ocr-2
huggingface-cli download opendatalab/MinerU2.5-Pro-2604-1.2B
huggingface-cli download Qwen/Qwen3-VL-4B-Instruct-GGUF
huggingface-cli download Qwen/Qwen3-4B-Thinking-2507-GGUF
huggingface-cli download unsloth/gemma-4-E2B-it-GGUF
huggingface-cli download microsoft/Florence-2-large
```

### VRAM budget

| Phase | Peak VRAM | Model(s) |
|-------|-----------|---------|
| 1 | ~2.8 GB | Chandra OCR 2 (holistic layout + handwriting + forms) |
| 2 | ~2.9 GB | Qwen3-VL-4B-Instruct (visual grounding + captioning) |
| 3 | ~5.1 GB | Qwen3-4B-Thinking-2507 + 85k KV cache |
| 4 | ~2.1 GB | Gemma 4-E2B (compliance refinement) |

Models load and clear sequentially — peak VRAM never exceeds the single
largest model at any moment.

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

### "pandoc: command not found"

Install pandoc for DOCX/PDF export (see [Installation](#installation)).
Markdown output is always produced regardless.

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
