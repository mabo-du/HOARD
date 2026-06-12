# HOARD User Guide

**Heritage Observation And Report Drafter** — a fully local, multi-stage AI
pipeline that converts archaeological field data into near-publication-ready
grey literature reports. All 6 phases are implemented and E2E-verified.
Runs locally via Ollama with optional cloud provider fallback (OpenAI,
Anthropic, Google Gemini).

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
11. [Ecosystem Integration](#ecosystem-integration)
12. [Multi-Provider AI](#multi-provider-ai)
13. [Configuration](#configuration)
14. [GPU Setup](#gpu-setup)
15. [Troubleshooting](#troubleshooting)
16. [CLI Reference](#cli-reference)
17. [Project Structure](#project-structure)

---

## Installation

### Prerequisites

- **Python 3.11+**
- **pip** (Python package manager)
- **[Ollama](https://ollama.com)** — for local model inference (Phases 1-4)
- **8 GB+ VRAM GPU** recommended — RTX 3070 Laptop verified

HOARD uses Ollama for all GPU inference. DOCX is generated via python-docx,
PDF/A-2b via WeasyPrint. No pandoc required.

### Install HOARD

```bash
# From PyPI (recommended)
pip install hoard-erd

# From source
git clone https://github.com/mabo-du/HOARD.git
cd HOARD
pip install -e ".[dev]"
```

### Install ecosystem tools (optional)

```bash
# heritage-cli — unified entry point for all ecosystem tools
pip install heritage-cli

# heritage-models — shared Pydantic data types
pip install heritage-models

# heritage-vocab — offline Getty vocabulary lookup
pip install heritage-vocab
```

### Pull Ollama models

```bash
ollama pull glm-ocr:latest            # Phase 1: context sheet OCR
ollama pull qwen3-vl:8b               # Phase 1 fallback + Phase 2 captioning
ollama pull huihui_ai/qwen3.5-abliterated:4B  # Phase 3: drafting
ollama pull tripolskypetr/gemma4-uncensored-aggressive:latest  # Phase 4: compliance

# Optional: NuExtract3 for improved structured extraction
ollama pull hf.co/numind/NuExtract3-GGUF:Q4_K_M
```

### Verify Installation

```bash
hoard --version
hoard --help
```

---

## Quick Start

```bash
# 1. Initialise a project
hoard init "Stoneyfield Farm 2026" --jurisdiction historic_england_cl3

# 2. Place field records in ./input/ — context sheets (JPG/PNG/PDF),
#    finds catalogues (CSV/XLSX), site photos, plans, section drawings

# 3. Run Phase 0 (no GPU needed)
hoard run --project stoneyfield_2026 --phase 0

# 4. Review any flagged items (image quality, missing files)
hoard review --project stoneyfield_2026

# 5. Run the full pipeline (GPU required for Phases 1-4)
hoard run --project stoneyfield_2026

# 6. Export the final report
hoard export --project stoneyfield_2026 --format docx,pdf,zip
```

---

## Project Initialisation

```bash
hoard init "Project Name" --jurisdiction <code> --output ./erd_workspace
```

| Option | Description | Default |
|--------|-------------|---------|
| `name` | Project name (required, positional) | — |
| `--jurisdiction` / `-j` | Jurisdiction template code | `historic_england_cl3` |
| `--output` / `-o` | Working directory root | `./erd_workspace` |
| `--detect/--no-detect` | Auto-detect hardware and suggest model tier | `--detect` |

On first run, HOARD probes your GPU, checks Ollama availability, tests
network connectivity, and suggests an appropriate model tier:

```
Detected Hardware:
  GPU: NVIDIA RTX 3070 Laptop (8 GB VRAM)
  CPU: 8 cores
  Ollama: Available
  Network: Online

Recommended Tier: standard — adequate VRAM (6.1 GB free)
```

Tiers range from `ultra_light` (no GPU, cloud-only) through `budget`,
`standard`, to `performance` (16-24 GB VRAM, larger local models).

---

## Running the Pipeline

```bash
# Full pipeline
hoard run --project <id>

# Single phase
hoard run --project <id> --phase <N>

# From phase N onward
hoard run --project <id> --from-phase <N>

# Strict mode — halt Phase 1 on schema validation failure
hoard run --project <id> --strict

# Use NuExtract3 for Phase 1 extraction (opt-in)
hoard run --project <id> --extractor nuextract3
```

The pipeline is **resumable** — completed phases are tracked in
`pipeline_state.json` and automatically skipped on subsequent runs.

### Pipeline Status

| Phase | Name | GPU | Time (50 contexts) |
|:---:|------|:---:|:---:|
| 0 | Ingestion & Triage | No | ~1 min |
| 1 | Multi-Modal Digitisation | Yes | ~10 min |
| 2 | Spatial Reconstruction | Yes | ~15 min |
| 3 | Synthesis & Drafting | Yes | ~8 min |
| 4 | Compliance Refinement | Yes | ~5 min |
| 5 | Assembly & Export | No | ~2 min |

---

## ARK Direct Data Input

For excavations already using the **ARK** (Archaeological Recording Kit) digital
recording system, HOARD can import structured data directly — bypassing
Phase 0 file ingestion and Phase 1 OCR. This saves approximately 2-4 hours
of pipeline time.

```bash
hoard import-ark --project stoneyfield_2026 --input ./ark_exports/
```

ARK import handles **5 data types:**

| Table | File Patterns | Records |
|-------|--------------|---------|
| Context sheets | `context.csv`, `contexts.csv`, `ctx_register.csv` | Context descriptions, interpretations, periods |
| Finds catalogue | `finds.csv`, `finds_catalogue.csv`, `sf_register.csv` | Object types, materials, quantities, weights |
| Sample register | `samples.csv`, `sample.csv`, `environmental.csv` | Sample types, volumes, processing status |
| Photo log | `photos.csv`, `photo.csv`, `photo_log.csv` | Filenames, context links, directions |
| Drawing register | `drawings.csv`, `drawing.csv`, `plans.csv` | Drawing numbers, types, scales |

Field names are matched case-insensitively — custom ARK instance fields are
recognised automatically via semantic embedding similarity (all-MiniLM-L6-v2).

After import, Phases 0 and 1 are marked as **bypassed** in pipeline state.
Proceed directly to Phase 2+:

```bash
hoard run --project stoneyfield_2026 --from-phase 2
```

---

## Reviewing Flags

After running any phase, review items flagged for human attention:

```bash
hoard review --project stoneyfield_2026
```

The terminal TUI presents each flagged item one at a time:

```
┌── Review #p0_ctx_001_BLUR_LOW (1/3) ──────────────────────────┐
│ Phase: 0   File: assets/context_sheet_001.png                  │
│ Field: _quality   Confidence: N/A                              │
│ Issue: Image blur score 31.1 (threshold: 80)                   │
│ Current value: BLUR_LOW                                        │
└────────────────────────────────────────────────────────────────┘

[a]ccept  [e]dit  [d]efer  [s]ummary  [q]uit
```

| Key | Action | Description |
|-----|--------|-------------|
| `a` | Accept | Mark as reviewed (AI value is acceptable) |
| `e` | Edit | Provide a corrected value |
| `d` | Defer | Skip for later review |
| `s` | Summary | Show progress summary |
| `q` | Quit | Exit (progress saved) |

Flags are generated by all phases: image quality issues (Phase 0), low-confidence
OCR fields (Phase 1), spatial grounding failures (Phase 2), draft uncertainty
markers (Phase 3), and compliance findings (Phase 4). Corrections are written
back to the workspace JSON and pipeline state is updated.

---

## Exporting Reports

```bash
hoard export --project stoneyfield_2026 --format docx,pdf,zip
```

| Option | Description | Default |
|--------|-------------|---------|
| `--project` / `-p` | Project ID (required) | — |
| `--format` / `-f` | Comma-separated formats | `docx,pdf` |
| `--workspace` / `-w` | Workspace root | `./erd_workspace` |

Available formats:
- **docx** — python-docx with heading-styled sections, Markdown tables, inline images
- **pdf** — WeasyPrint PDF/A-2b with XMP metadata, font subsetting, sRGB colour profile
- **tei-xml** — lightweight TEI wrapper with Dublin Core metadata header
- **zip** — archive including all pipeline outputs, Harris Matrix SVG, logs

Output directory: `{workspace}/{project_id}/05_final/`

Optional PAdES digital signatures (requires signing key):
```bash
# Generate a signing key
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ~/.config/hoard/signing.pem \
  -out ~/.config/hoard/signing.pem \
  -subj "/CN=HOARD Report Signing Key"

# Export with signed PDF
hoard export --project stoneyfield_2026 --format docx,pdf,signed-pdf
```

---

## Jurisdiction Templates

HOARD ships with **14 jurisdiction templates** for heritage authority reporting
standards. Templates are declarative YAML files — no code changes needed to
add a new jurisdiction.

```bash
# List all templates
hoard templates list

# Show template details (YAML with syntax highlighting)
hoard templates show --name historic_england_cl3

# Validate a template file
hoard templates validate --file ./my_template.yaml
```

### Available Jurisdictions

| Code | Authority | Region |
|------|-----------|--------|
| `historic_england_cl3` | Historic England — Evaluation (CL3) | England |
| `historic_england_cl4` | Historic England — Excavation (CL4) | England |
| `historic_environment_scotland` | HES — Data Structure Report (DSR) | Scotland |
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

Create a YAML file in the `templates/` directory:

```yaml
# templates/my_jurisdiction.yaml
jurisdiction: "My Heritage Authority — Excavation Report"
version: "1.0"
extends: "international_generic"  # optional: inherit from another template

mandatory_sections:
  - id: executive_summary
    label: "Executive Summary"
    max_words: 300
    required_fields: [project_name, ngr, dates]
```

Templates support tool-specific extension blocks for the ecosystem
(HOARD and Trowel can co-exist in a single file):

```yaml
# Shared core (understood by both HOARD and Trowel)
jurisdiction: "Example"
mandatory_sections: [...]

# HOARD-specific (Trowel ignores this block)
hoard:
  llm_prompt: "..."
  extraction_schema: { ... }

# Trowel-specific (HOARD ignores this block)
trowel:
  cover_page_template: "cover.html"
```

---

## Pipeline Phases

### Phase 0: Ingestion & Triage

*Rule-based, zero VRAM.*

- Enumerates all input files recursively
- Converts HEIC/RAW/PDF to normalised PNG (via wand/ImageMagick)
- Runs OpenCV quality checks: blur score, skew angle, exposure level
- Classifies document types by filename patterns (context_sheet, finds_catalogue,
  site_photo, plan, section, sample_result, existing_text)
- Validates finds catalogue CSV/XLSX column headers
- Halts if mandatory file types are missing or >90% of context sheets are degraded
- Writes `00_manifest/manifest.json` with quality flags per file

### Phase 1: Multi-Modal Digitisation *(GPU-dependent)*

- **Default extractor: GLM-OCR** (0.9B, ~2.2 GB VRAM) — MIT license, JSON schema
  adherence via Multi-Token Prediction
- **Opt-in extractor: NuExtract3** (4B, ~3.5 GB VRAM) — `--extractor nuextract3`,
  RL-trained for exact JSON template following (56% better schema adherence)
- **Degraded document fallback**: Qwen3-VL-8B when GLM-OCR fails after 2 attempts
- Finds catalogue parsing via Docling (Granite-Docling-258M, CPU-based, Apache 2.0)
- CSV/XLSX tabular data via pandas
- Schema validation against shared `heritage-data-package-v1.json`
- Checkbox post-processing via regex (cross/filled → boolean)
- Use `--strict` flag to halt the pipeline on schema validation failures

### Phase 2: Spatial Reconstruction *(GPU-dependent)*

- Site photo and plan analysis via **Qwen3-VL-8B** (~5.5 GB VRAM)
- Manifest-based filtering: only `site_photo` and `plan` files processed
  (context sheets excluded from photo plates automatically)
- Auto-captioning with fills, colour, inclusions, orientation descriptions
- Cross-checks against Phase 1 context data for consistency
- SVG section drawing generation via GLM-OCR prompt engineering
- Context hint extraction for Phase 3 synthesis

### Phase 3: Synthesis & Drafting *(GPU-dependent)*

- Context assembly from all Phase 1-2 outputs
- **Qwen3.5-4B** (~2.8 GB VRAM) with thinking-mode capture for stratigraphic reasoning
- Structured Markdown draft with `##section:id` code-block labels
- 10-section report structure: summary, introduction, geology, methodology,
  results by area, results by period, finds, discussion, bibliography, appendix
- Chunk-and-merge for large sites (>70K characters): groups contexts by period,
  processes each group, merges into a cohesive draft
- Human review triggers for: low-confidence statements, hallucinated context
  numbers, structural uncertainty

### Phase 4: Compliance Refinement *(GPU-dependent)*

- **Gemma 4-E2B** (~2.1 GB VRAM) section-by-section editing
- Template-driven restructuring: each section rewritten to match jurisdiction
  template's mandatory sections, required fields, and style guide
- Default value interpolation: 11 template variables (`{project_id}`,
  `{project_name}`, `{current_date}`, etc.) — eliminates most `[MISSING:]` placeholders
- Prohibited term scanning with preferred alternative suggestions
- Word count enforcement per section
- Heading style correction and figure caption format checking

### Phase 5: Assembly & Export

*Rule-based, zero VRAM.*

- Figure resolution: `[FIG:filename]` tokens replaced with embedded Markdown images
- Appendix generation:
  - **Context Register** — table of all contexts with type, description, period
  - **Finds Concordance** — table of all finds by context with material, quantity
  - **Sample Register** — table of all samples with type and processing notes
- **Harris Matrix SVG** — topological level assignment, period colour-coded nodes,
  arrow rendering (pure Python, no graphviz)
- **Photo plates** — rectpack A4 bin-packing (only Phase-2-processed images)
- **Bibliography extraction** — citation pattern detection from Phase 3 draft
- **DOCX export** — python-docx with cover page, heading-styled sections (H1/H2/H3),
  justified body text (11pt Calibri), Markdown tables, inline images
- **PDF/A-2b export** — WeasyPrint, A4 CSS stylesheet, XMP Dublin Core metadata,
  sRGB colour profile, page headers/footers
- **TEI-XML** — lightweight semantic export with Dublin Core header
- **ZIP archive** — packages all pipeline outputs
- **PAdES signatures** — optional digital signature via pyHanko (requires key)

---

## Harris Matrix

HOARD generates a stratigraphic Harris Matrix SVG from context sheet relationships
automatically during Phase 5:

```bash
hoard run --project stoneyfield_2026 --phase 5
# Output: erd_workspace/stoneyfield_2026/05_final/harris_matrix.svg
```

Or standalone via Python:

```python
from pathlib import Path
from hoard.review import generate_harris_matrix

generate_harris_matrix(
    context_files=sorted(Path("01_digitised").glob("*.json")),
    output_path=Path("harris_matrix.svg"),
    title="Stoneyfield Farm 2026",
)
```

**Features:**
- Colour-coded by period (Prehistoric=Brown, Roman=Red, Medieval=Blue,
  Post-Medieval=Green, Modern=Grey, Undated=Light Grey)
- Arrows point from later to earlier contexts (standard Harris convention)
- Pure Python — no graphviz, no external dependencies
- Legend included in the SVG

---

## Ecosystem Integration

HOARD is one component of a broader open-source heritage science ecosystem:

| Tool | Function | Integration |
|------|----------|-------------|
| **StratiGraph** | Interactive Harris Matrix viewer | HOARD Phase 1 JSON imports directly via shared schema contract |
| **Trowel** | Desktop report drafter | Bidirectional JSON import/export; shared jurisdiction templates |
| **Libby** | Radiocarbon calibration | StratiGraph exports OxCal CQL payloads for Libby calibration |
| **Cache & Carry** | Offline collections management | Getty vocabulary lookup for material/period normalisation |
| **Dibble** | 3D lithic analysis | Specialist finds appendix via JSON data bridge |
| **heritage-cli** | Unified ecosystem CLI | Single `heritage` command routing to all tools |

### With StratiGraph

```bash
# 1. Run HOARD Phase 1
hoard run --project stoneyfield_2026 --phase 1

# 2. Import into StratiGraph
cd ~/Projects/StratiGraph/app
npm install && npm run dev
# Open http://localhost:5173 → Import → HOARD JSON Import
# Select ctx_sheet_*.json files from 01_digitised/

# 3. StratiGraph renders the Harris Matrix, detects cycles,
#    computes transitive reduction, and can export EEDP paths
#    for HOARD Phase 3 synthesis or OxCal CQL for Libby
```

### With heritage-cli

```bash
# Install the unified CLI
pip install heritage-cli

# Run HOARD pipeline
heritage run --project stoneyfield_2026 --auto

# Run a multi-tool pipeline with review gates
heritage run --project stoneyfield_2026 --pipeline pipeline.yaml

# Calibrate samples (if Libby is installed)
heritage calibrate --project stoneyfield_2026

# Check ecosystem tool status
heritage tools list
```

### Pipeline orchestration example

Create a `pipeline.yaml` for multi-tool workflows:

```yaml
steps:
  - project: hoard
    phases: [0, 1, 2]
  - gate: review
    message: "Review the Harris Matrix in StratiGraph before proceeding"
    action: "stratigraph import --path output/01_digitised"
  - project: hoard
    phases: [3, 4]
  - gate: review
    message: "Review the draft before final export"
  - project: hoard
    action: export
    formats: [docx, pdf]
```

```bash
heritage run --project stoneyfield_2026 --pipeline pipeline.yaml
```

---

## Multi-Provider AI

HOARD supports **four AI backends** for GPU phases, selectable per phase.
All inference is routed through the `ProviderRouter`, which handles provider
selection, fallback chains, audit logging, and cost tracking automatically.

| Provider | Format | When to use |
|----------|--------|-------------|
| **Ollama** (default) | Local GPU inference | Full privacy, offline, 8+ GB VRAM |
| **OpenAI** | Cloud API | Fast prose, GPT-4o-mini from $0.15/M tokens |
| **Anthropic** | Cloud API | Best narrative quality (Claude Sonnet 4) |
| **Google Gemini** | Cloud API | Cheapest cloud option ($0.10/M tokens), 1M context |

### Hardware tiers

HOARD auto-detects your hardware and suggests a tier on `hoard init`:

| Tier | VRAM | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|------|:----:|---------|---------|---------|---------|
| Ultra-light | No GPU | Cloud API | Cloud API | Cloud API | Cloud API |
| Budget | 6 GB | GLM-OCR | Qwen3-VL-4B | Qwen3.5-4B | Gemma 4-E2B |
| Standard | 8-12 GB | GLM-OCR | Qwen3-VL-8B | Qwen3.5-4B | Gemma 4-E2B |
| Performance | 16-24 GB | NuExtract3 | PaliGemma 2 | Qwen3-8B | Gemma 4-9B |

Override the tier per run:

```bash
hoard run --project X --tier ulta_light      # cloud only (needs API keys)
hoard run --project X --tier budget           # minimum local models
hoard run --project X --offline               # never use cloud APIs
```

### Routing modes

| Mode | Behaviour |
|------|-----------|
| **Manual** (strict) | Uses only the explicitly configured provider per phase |
| **Auto** | Cascading availability: try local first, cloud fallback |
| **Quality** | Local for extraction phases (1, 2), cloud for prose (3, 4) |

Configured in `~/.config/hoard/config.yaml`:

```toml
[system]
routing_mode = "quality"
privacy_tier = "strict_local"
hardware_tier = "auto"
```

### Privacy tiers

| Tier | Data sent to cloud |
|------|-------------------|
| **Strict Local** (default) | No data ever leaves your machine |
| **Sanitized Cloud** | Text only; coordinates and images stay local |
| **Full Hybrid** | Full data flow (institutional DPAs recommended) |

### API key management

```bash
# Store an API key (encrypted at rest with AES-256-GCM)
hoard keys set openai sk-...
hoard keys set anthropic sk-ant-...
hoard keys set google AIza...

# List configured providers
hoard keys list

# Remove a key
hoard keys remove openai
```

Keys are encrypted with PBKDF2-SHA256 (100K iterations) + AES-256-GCM and
stored in `~/.config/hoard/credentials.yaml.enc`. Master password from
`HOARD_VAULT_KEY` environment variable or interactive prompt.

### Cost comparison

Per typical 50-context site report:

| Provider | Estimated cost | Notes |
|----------|:-------------:|-------|
| Local (Ollama) | $1.95 (hardware amortised) | Privacy guaranteed |
| Gemini 2.5 Flash-Lite | ~$0.09 | 1M context window |
| GPT-4o-mini | ~$0.13 | Fast, widely available |
| Claude Sonnet 4 | ~$0.46 | Best prose quality |
| Gemini 2.5 Pro | ~$2.94 | Premium capability |

---

## Configuration

### Global config: `~/.config/hoard/config.yaml`

Controls the multi-provider AI behaviour:

```toml
[system]
routing_mode = "quality"
privacy_tier = "strict_local"
hardware_tier = "auto"
latency_budget_seconds = 60
cloud_preferred_phases = [3, 4]

[phases.phase3]
# provider = "anthropic"
# model = "claude-sonnet-4-20250514"
```

### Project config: `{workspace}/{project_id}/config.yaml`

Created by `hoard init`:

```yaml
project_id: stoneyfield_2026
project_name: Stoneyfield Farm 2026
jurisdiction: historic_england_cl3
extractor: glm-ocr
strict: false
```

### Credential vault: `~/.config/hoard/credentials.yaml.enc`

Encrypted with AES-256-GCM. Contains API keys for cloud providers.
Managed via `hoard keys` subcommands.

### Ecosystem config: `~/.config/heritage/config.toml`

Shared across all heritage ecosystem tools (HOARD, StratiGraph, Trowel, etc.):

```toml
[paths]
workspace = "~/heritage_workspace"

[defaults]
jurisdiction = "historic_england_cl3"
```

---

## GPU Setup

### Recommended hardware

- NVIDIA RTX 3060 (12 GB) or better
- NVIDIA RTX 4060/4070 (8-12 GB)
- M-series Mac with unified memory (16 GB+)

### VRAM budget by tier

**Standard tier** (8-12 GB, recommended):
| Phase | Model | VRAM |
|:---:|-------|:----:|
| 1 | GLM-OCR | ~2.2 GB |
| 2 | Qwen3-VL-8B | ~5.5 GB |
| 3 | Qwen3.5-4B | ~2.8 GB |
| 4 | Gemma 4-E2B | ~2.1 GB |

Models load and evict sequentially via `keep_alive=0` — peak VRAM never exceeds
the single largest model.

### Benchmarking

```bash
hoard run --project pinn_brook_2026 --benchmark
```

Logs per-phase VRAM peak/average, GPU temperature, power draw, and Ollama
model memory to `logs/benchmarks/`.

### Verify

```bash
# Check GPU
nvidia-smi

# Check Ollama
ollama list
ollama ps
```

---

## Troubleshooting

### "No input files found"
Ensure your field records are in the `./input/` directory (or use `--input`).
Accepted formats: JPG, PNG, PDF, HEIC, CSV, XLSX, DXF, SVG, TXT, DOCX, MD.

### "Mandatory file check failed"
Pipeline requires at least one context sheet and one finds catalogue (CSV/XLSX
or form image).

### "ModuleNotFoundError: No module named 'hoard.providers.credentials'"
Install the cryptography dependency: `pip install cryptography`

### "WeasyPrint fails on PDF export"
WeasyPrint requires Pango and Cairo system libraries:
```bash
# Ubuntu/Debian
sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0
# Fedora
sudo dnf install pango cairo gdk-pixbuf2
```

### "Schema validation warnings during Phase 1"
Normal for OCR-extracted data. Use `--strict` to halt on validation failure
if you want to review every discrepancy.

### "HOARD JSON import in StratiGraph shows no relationships"
GLM-OCR cannot reliably parse the Harris Matrix diagram drawn on context
sheets. Relationships (cuts/fills) are only present if the OCR captured them
from the form text. Add relationships manually in StratiGraph or via CSV import.

### "Export shows 'no output generated'"
Ensure the pipeline has been run at least through Phase 3 before exporting.
```bash
hoard run --project <id> --from-phase 0
hoard export --project <id> --format docx,pdf
```

---

## CLI Reference

### Global Options

| Option | Description |
|--------|-------------|
| `--version` / `-V` | Show version and exit |
| `--help` | Show help message |

### Commands

| Command | Description |
|---------|-------------|
| `init` | Initialise a new project |
| `run` | Run the pipeline (full, partial, or multi-tool pipeline) |
| `import-ark` | Import structured data from ARK system exports |
| `review` | Open the review dashboard for flagged items |
| `export` | Export final report in specified formats |
| `templates list` | List available jurisdiction templates |
| `templates show --name <code>` | Show template YAML with syntax highlighting |
| `templates validate --file <path>` | Validate a template YAML file |
| `keys set <provider> <key>` | Store an encrypted API key |
| `keys list` | List configured API keys |
| `keys remove <provider>` | Remove an API key |
| `keys unlock` | Unlock the credential vault |
| `keys init` | Initialise a new credential vault |

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
└── erd_workspace/
    └── stoneyfield_2026/
        ├── config.yaml             # Project configuration
        ├── pipeline_state.json     # Resumable pipeline state
        ├── logs/
        │   ├── phase0.log
        │   └── provider_audit.json  # AI inference audit trail
        ├── 00_manifest/
        │   └── manifest.json       # File inventory + quality flags
        ├── 01_digitised/           # Phase 1 JSON outputs
        ├── 02_spatial/             # Phase 2 geometry + captions
        ├── 03_draft/               # Phase 3 Markdown draft sections
        ├── 04_refined/             # Phase 4 compliance-refined draft
        └── 05_final/               # Final exports
            ├── report.md
            ├── report_20260609_143022.docx
            ├── report_20260609_143022.pdf
            ├── report_20260609_143022.xml
            ├── archive_20260609_143022.zip
            └── harris_matrix.svg
```

---

## Licence

MIT — built for the archaeological community.

---

## Support

- **Issues:** https://github.com/mabo-du/HOARD/issues
- **Repository:** https://github.com/mabo-du/HOARD
- **Research papers:** `docs/research-papers/`
