# HOARD

**Heritage Observation And Report Drafter**

A fully local, multi-stage AI pipeline that converts archaeological field data — context sheets, finds catalogues, site photographs, section drawings, and sample results — into a near-publication-ready grey literature report conforming to the relevant heritage authority standard.

Targets 6 GB VRAM, runs entirely on consumer hardware. Zero API calls, zero data leaves your machine.

---

## Pipeline

| Phase | Name | What it does | GPU? | Status |
|---|---|---|---|---|---|
| 0 | Ingestion & Triage | Inventory files, normalise formats, assess quality, flag problems | No | ✅ Complete |
| 1 | Multi-Modal Digitisation | GLM-OCR for handwritten forms, checkbox extraction, Docling table parsing | Yes | ✅ Complete |
| 2 | Spatial Reconstruction | Qwen3-VL-8B/GLM-OCR photo captioning, cross-check vs context sheets, SVG vectorisation | Yes | ✅ Complete |
| 3 | Synthesis & Drafting | Qwen3.5-4B reasoning through full site dataset, produce structured draft | Yes | ✅ Complete |
| 4 | Compliance Refinement | Gemma 4-E2B section-by-section restructuring to match jurisdiction template | Yes | ✅ Complete |
| 5 | Assembly & Export | python-docx DOCX, WeasyPrint PDF/A-2b, rectpack photo plates, TEI-XML, ZIP | No | ✅ Complete |

## Quick Start

```bash
# Install
pip install -e .

# Initialise a project
erd init "Stoneyfield Farm 2026" --jurisdiction historic_england_cl3

# Run Phase 0 (Ingestion & Triage — no GPU needed)
erd run --project stoneyfield_farm_2026 --input ./field_records --phase 0

# List available jurisdiction templates
erd templates list
```

Phases 0 and 5 are rule-based (no GPU). GPU-dependent phases (1–4) use Ollama for local
inference and run on consumer hardware with 8 GB+ VRAM.
```

See `docs/user-guide.md` for full documentation and `docs/HOARD_Technical_Design_v2.md` for the complete technical design.

## CLI Reference

| Command | Description |
|---|---|
| `erd init <name>` | Initialise a new project |
| `erd run --project <id>` | Run the pipeline (full or partial) |
| `erd run --project <id> --phase <N>` | Run a single phase |
| `erd run --project <id> --from-phase <N>` | Run from phase N onward |
| `erd run --project <id> --strict` | Halt Phase 1 on schema validation failure |
| `erd import-ark --project <id> --input <dir>` | Import structured data from ARK system exports (bypasses Phase 0/1) |
| `erd review --project <id>` | Interactive review dashboard for flagged items |
| `erd export --project <id> --format docx,pdf` | Export final report |
| `erd templates list` | List available jurisdiction templates |
| `erd templates show --name <code>` | Show template details |
| `erd templates validate --file <path>` | Validate a template file |

## Jurisdiction Templates

Reports conform to national heritage authority standards via declarative YAML templates. Currently available (14 jurisdictions):

| Code | Authority | Region |
|---|---|---|
| `historic_england_cl3` | Historic England — Evaluation (CL3) | England |
| `historic_england_cl4` | Historic England — Excavation (CL4) | England |
| `historic_environment_scotland` | HES — Data Structure Report (DSR) | Scotland |
| `wales_rcahmw` | Cadw / RCAHMW | Wales |
| `ireland_nms` | National Monuments Service (Section 26) | Ireland |
| `netherlands_kna` | KNA 5.0 (Kwaliteitsnorm Nederlandse Archeologie) | Netherlands |
| `france_inrap` | INRAP / Code du Patrimoine | France |
| `germany_denkmalpflege` | Landesdenkmalpflege (Länder-specific) | Germany |
| `us_section106` | Section 106 (NRHP Eligibility Evaluation) | United States |
| `canada_ontario` | Ontario S&G for Consultant Archaeologists | Canada |
| `australia_burra` | Burra Charter (ICOMOS / State Heritage) | Australia |
| `new_zealand` | Heritage NZ Pouhere Taonga | New Zealand |
| `south_africa_sahra` | SAHRA (National Heritage Resources Act) | South Africa |
| `international_generic` | Generic (fallback for uncovered jurisdictions) | Any |

Adding a new jurisdiction means writing a YAML file — no pipeline code changes required.

## Status

| Phase / Feature | Name | Status |
|---|---|---|---|
| 0 | Ingestion & Triage | ✅ Complete |
| 1 | Multi-Modal Digitisation | ✅ Complete — GLM-OCR + Docling + Qwen3-VL fallback |
| 2 | Spatial Reconstruction | ✅ Complete — Qwen3-VL / GLM-OCR captioning + cross-check + SVG |
| 3 | Synthesis & Drafting | ✅ Complete — Qwen3.5-4B with thinking mode capture |
| 4 | Compliance Refinement | ✅ Complete — Gemma 4-E2B section-by-section editing |
| 5 | Assembly & Export | ✅ Complete — python-docx DOCX + WeasyPrint PDF/A-2b + rectpack plates |
| — | Template engine | ✅ Complete — 14 jurisdiction templates |
| — | Review dashboard | ✅ Complete — interactive Rich TUI |
| — | Harris Matrix | ✅ Complete — pure-Python SVG generator |
| — | ARK direct data input | ✅ Complete — bypass Phase 0/1 for digital-first sites |
| — | Checkbox post-processing | ✅ Complete — GLM-OCR checkbox normaliser |
| — | SVG geometry | ✅ Complete — field section drawings to SVG |
| — | Photo plate layout | ✅ Complete — rectpack A4 bin-packing |
| — | CONTRIBUTING.md | ✅ Complete — development setup guide |
| — | User guide | ✅ Complete — see `docs/user-guide.md` |
| — | `--strict` flag | ✅ Complete — halt Phase 1 on schema validation failure |
| — | Schema contract | ✅ Complete — shared `schemas/context-sheet-v1.json` with StratiGraph |
| — | StratiGraph integration | ✅ Complete — HOARD JSON import into StratiGraph matrix viewer |
| — | NuExtract3 evaluation | ✅ Complete — benchmarked, requires vLLM (no Ollama GGUF yet) |

All 6 phases are implemented and E2E-verified with real archaeological data
(Pinn Brook Park, 49/50 contexts, CC-BY 4.0 via ADS). The full pipeline runs on
consumer hardware with 8 GB VRAM (RTX 3070 Laptop verified) using Ollama for
local model inference.

## Review Dashboard

After running a pipeline phase, review flagged items interactively:

```bash
erd review --project stoneyfield_2026
```

The terminal TUI presents each flagged item one at a time:
- **Accept** — mark the AI value as correct
- **Edit** — type a corrected value
- **Defer** — skip for later review

Corrections are written back to the workspace JSON, and pipeline state is updated so you can re-run from the corrected phase.

Supports flags from: image quality issues, low-confidence OCR fields, spatial grounding failures, draft uncertainty markers, and compliance findings.

## Harris Matrix

HOARD generates a stratigraphic Harris Matrix SVG from context sheet relationships — automatically during Phase 5, or standalone:

```bash
# Generated as part of Phase 5 assembly
erd run --project stoneyfield_2026 --phase 5
# Output: erd_workspace/stoneyfield_2026/05_final/harris_matrix.svg
```

Colour-coded by period, arrows pointing from later to earlier contexts. Pure Python — no graphviz required.

## ARK Direct Data Input

For excavations already using the **ARK** (Archaeological Recording Kit) digital
recording system, HOARD can import structured data directly — bypassing Phase 0
file triage and Phase 1 OCR entirely:

```bash
erd import-ark --project stoneyfield_2026 --input ./ark_exports/
```

Accepts CSV or JSON exports for **5 ARK table types:**
- **Context sheets** — context numbers, descriptions, interpretations, periods
- **Finds catalogues** — object types, materials, quantities, weights
- **Sample registers** — sample numbers, types, volumes, processing status
- **Photo logs** — filenames, context links, directions, descriptions
- **Drawing registers** — drawing numbers, types, scales, draughtspersons

Field names are matched case-insensitively against common ARK conventions —
custom ARK instance fields are recognised automatically. Unrecognised columns
are warned but don't block the import.

After import, Phases 0 and 1 are marked as **bypassed** in pipeline state,
and you can proceed directly to Phase 2+.

## StratiGraph Integration

StratiGraph ([github.com/mabo-du/stratigraph](https://github.com/mabo-du/stratigraph)) is a
companion web app that visualises stratigraphic matrices from HOARD Phase 1 output.

HOARD and StratiGraph share a **JSON Schema contract** at `schemas/context-sheet-v1.json`.
Both projects validate against the same schema independently:

1. Run HOARD Phase 1 to produce `ctx_sheet_*.json` files
2. Open StratiGraph → **Import** → **HOARD JSON Import** tab
3. Select the JSON files — relationships are inferred from `cuts`/`fills`/`same_as` fields
4. StratiGraph renders the Harris Matrix with auto-layout, cycle detection, and transitive reduction

See `docs/user-guide.md` for the full walkthrough.

## Documentation

Full documentation is available in [`docs/user-guide.md`](docs/user-guide.md), covering:
- Installation and quick start
- Complete CLI reference
- Pipeline phase walkthrough
- Jurisdiction template guide (all 14)
- Review dashboard and Harris Matrix usage
- **ARK direct data input**
- StratiGraph integration (HOARD JSON import)
- GPU setup and troubleshooting

## Licence

MIT
