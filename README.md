# HOARD

**Heritage Observation And Report Drafter**

A fully local, multi-stage AI pipeline that converts archaeological field data — context sheets, finds catalogues, site photographs, section drawings, and sample results — into a near-publication-ready grey literature report conforming to the relevant heritage authority standard.

Targets 6 GB VRAM, runs entirely on consumer hardware. Zero API calls, zero data leaves your machine.

---

## Pipeline

| Phase | Name | What it does | GPU? |
|---|---|---|---|
| 0 | Ingestion & Triage | Inventory files, normalise formats, assess quality, flag problems | No |
| 1 | Multi-Modal Digitisation | OCR for handwritten forms, checkbox extraction, table parsing | Yes |
| 2 | Spatial Reconstruction | Photo captioning, visual grounding, sketch-to-CAD geometry | Yes |
| 3 | Synthesis & Drafting | Reason through full site dataset, produce structured draft | Yes |
| 4 | Compliance Refinement | Restructure draft to match jurisdiction template conventions | Yes |
| 5 | Assembly & Export | Compile figures/tables/appendices, export DOCX/PDF/archive | No |

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

Phases 0 and 5 are fully implemented (no GPU). GPU-dependent phases (1–4) will be available after model evaluation. See `docs/user-guide.md` for full documentation.

## CLI Reference

| Command | Description |
|---|---|
| `erd init <name>` | Initialise a new project |
| `erd run --project <id>` | Run the pipeline (full or partial) |
| `erd run --project <id> --phase <N>` | Run a single phase |
| `erd run --project <id> --from-phase <N>` | Run from phase N onward |
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
|---|---|---|
| 0 | Ingestion & Triage | ✅ Complete (rule-based, no GPU) |
| 1 | Multi-Modal Digitisation | ⏳ Blocked — needs GPU (training ~24h) |
| 2 | Spatial Reconstruction | ⏳ Blocked — needs GPU |
| 3 | Synthesis & Drafting | ⏳ Blocked — needs GPU |
| 4 | Compliance Refinement | ⏳ Blocked — needs GPU (structural checks ready) |
| 5 | Assembly & Export | ✅ Complete (rule-based, no GPU) |
| — | Template engine | ✅ Complete — 14 jurisdiction templates |
| — | Review dashboard | ✅ Complete — interactive Rich TUI |
| — | Harris Matrix | ✅ Complete — pure-Python SVG generator |
| — | User guide | ✅ Complete — see `docs/user-guide.md` |

GPU-dependent phases will be available after model training completes.

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

## Documentation

Full documentation is available in [`docs/user-guide.md`](docs/user-guide.md), covering:
- Installation and quick start
- Complete CLI reference
- Pipeline phase walkthrough
- Jurisdiction template guide (all 14)
- Review dashboard and Harris Matrix usage
- GPU setup and troubleshooting

## Licence

MIT
