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

Phase 0 is the only phase currently implemented. GPU-dependent phases (1–4) will be available after model evaluation — see [`HOARD_Planning_v1.md`](HOARD_Planning_v1.md) for the roadmap.

## CLI Reference

| Command | Description |
|---|---|
| `erd init <name>` | Initialise a new project |
| `erd run --project <id>` | Run the pipeline |
| `erd run --project <id> --phase <N>` | Run a single phase |
| `erd run --project <id> --from-phase <N>` | Run from phase N onward |
| `erd review --project <id>` | Review dashboard for flagged items |
| `erd export --project <id>` | Export final report |
| `erd templates list` | List available jurisdiction templates |

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

**Phase 0 (Ingestion & Triage)** — complete and testable.
**Phases 1–5** — implementation in progress. GPU-dependent phases are blocked pending model training completion (~24h).

See [`HOARD_Planning_v1.md`](HOARD_Planning_v1.md) for the full development roadmap.

## Licence

MIT
