# HOARD

**Heritage Observation And Report Drafter**

A fully local, multi-stage AI pipeline that converts archaeological field data — context sheets, finds catalogues, site photographs, section drawings, and sample results — into a near-publication-ready grey literature report conforming to the relevant heritage authority standard.

Targets 8 GB VRAM consumer GPUs. Runs entirely on-device via Ollama — zero API calls, zero data leaves your machine.

---

## Features

### End-to-End Report Generation
Converts raw field records (context sheets, finds catalogues, photographs, section drawings, sample results) into a complete grey literature report in six automated phases — from file triage through to publication-ready DOCX, PDF/A-2b, TEI-XML, and ZIP export. All six phases are implemented and E2E-verified on real archaeological data.

### Multi-Provider AI
Switch between four AI backends per pipeline phase — **Ollama** (local GPU), **OpenAI**, **Anthropic Claude**, and **Google Gemini** — with intelligent routing based on task requirements, privacy constraints, and hardware availability. Configure once; HOARD selects the optimal provider automatically.

### Hardware Tier System
Auto-detects your GPU, VRAM, and Ollama models on first run and suggests an appropriate tier:
- **Ultra-light** — no GPU needed, cloud-only inference
- **Budget** — 6 GB VRAM, compact local models
- **Standard** — 8-12 GB VRAM, full local pipeline
- **Performance** — 16-24 GB VRAM, high-end local models

### 14 Jurisdiction Templates
Reports conform to heritage authority standards in England, Scotland, Wales, Ireland, Netherlands, France, Germany, US, Canada, Australia, New Zealand, and South Africa — all driven by declarative YAML templates. Adding a new jurisdiction means writing one YAML file; no code changes required.

### Interactive Review Dashboard
After each pipeline phase, a terminal TUI presents flagged items (blurred images, low-confidence OCR, spatial mismatches, compliance warnings) for Accept/Edit/Defer review. Corrections write back to the workspace and update pipeline state for re-runnable workflows.

### Offline Getty Vocabulary
Standardises materials, periods, and artefact types against Getty AAT/ULAN/TGN terms using the `heritage-vocab` library — works offline with a built-in fallback covering common archaeological terms. No API calls required.

### Harris Matrix Generator
Pure-Python SVG stratigraphic matrix from context relationships. Colour-coded by period, arrows from later to earlier contexts. No graphviz or external tools needed.

### Cryptographically Signed PDFs
Optional PAdES-B/LTV digital signatures via pyHanko for legally compliant report certification.

### Cloud-Ready Credential Vault
API keys for OpenAI, Anthropic, and Google are stored encrypted at rest (AES-256-GCM + PBKDF2) and managed via `hoard keys set/list/remove`. Cross-compatible with the Kryptis vault format.

### Ecosystem Integration
HOARD shares data contracts and workflows with [StratiGraph](https://github.com/mabo-du/stratigraph) (Harris Matrix viewer), Trowel (desktop report drafter), Libby (radiocarbon calibration), Cache & Carry (offline collections management), and Dibble (3D lithic analysis) — all accessible through the unified `heritage` CLI.

## Quick Start

```bash
# Install
pip install hoard            # from PyPI
# or from source
git clone https://github.com/mabo-du/HOARD.git
cd HOARD && pip install -e ".[dev]"

# Install Ollama and pull models
ollama pull glm-ocr qwen3-vl:8b qwen3.5-4b gemma4

# Initialise a project
hoard init "Stoneyfield Farm 2026" --jurisdiction historic_england_cl3

# Run Phase 0 (no GPU needed)
hoard run --project stoneyfield_farm_2026 --input ./field_records --phase 0

# List available jurisdiction templates
hoard templates list
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `hoard init <name>` | Initialise a new project |
| `hoard run --project <id>` | Run the pipeline (full or partial) |
| `hoard run --project <id> --phase <N>` | Run a single phase |
| `hoard run --project <id> --from-phase <N>` | Run from phase N onward |
| `hoard run --project <id> --strict` | Halt Phase 1 on schema validation failure |
| `hoard run --project <id> --extractor nuextract3` | Use NuExtract3 for Phase 1 extraction (opt-in) |
| `hoard import-ark --project <id> --input <dir>` | Import structured data from ARK system exports |
| `hoard review --project <id>` | Interactive review dashboard for flagged items |
| `hoard export --project <id> --format docx,pdf` | Export final report |
| `hoard templates list` | List available jurisdiction templates |
| `hoard templates show --name <code>` | Show template details with syntax highlighting |
| `hoard templates validate --file <path>` | Validate a template YAML file |
| `hoard keys set <provider> <key>` | Store an encrypted API key for cloud providers |
| `hoard keys list` | List configured API keys |
| `hoard keys unlock` | Unlock the credential vault |

## Ecosystem Integration

HOARD is one component of a broader heritage science open-source ecosystem:

| Tool | Function | Integration |
|------|----------|-------------|
| **StratiGraph** | Interactive Harris Matrix editor (Tauri 2 + React) | [Shared JSON Schema](schemas/heritage-data-package-v1.json) — HOARD Phase 1 exports import directly |
| **Trowel** | Desktop report drafter (PyQt6) | Bidirectional JSON import/export, shared jurisdiction templates |
| **Libby** | Radiocarbon calibration (FastAPI + Svelte 5) | StratiGraph exports OxCal CQL / JSON payloads to Libby |
| **Cache & Carry** | Offline collections management (Tauri + Rust) | Getty AAT/ULAN/TGN vocabulary for term normalisation |
| **Dibble** | 3D lithic analysis (Python + PyVista) | Specialist finds appendix data via JSON bridge |
| **heritage-cli** | Unified ecosystem CLI | `heritage run/calibrate/lithics/review/matrix/publish` |

## Jurisdiction Templates

Reports conform to national heritage authority standards via declarative YAML templates. Currently 14 jurisdictions:

| Code | Authority | Region |
|------|-----------|--------|
| `historic_england_cl3` | Historic England — Evaluation (CL3) | England |
| `historic_england_cl4` | Historic England — Excavation (CL4) | England |
| `historic_environment_scotland` | HES — Data Structure Report | Scotland |
| `wales_rcahmw` | Cadw / RCAHMW | Wales |
| `ireland_nms` | National Monuments Service | Ireland |
| `netherlands_kna` | KNA 5.0 | Netherlands |
| `france_inrap` | INRAP / Code du Patrimoine | France |
| `germany_denkmalpflege` | Landesdenkmalpflege | Germany |
| `us_section106` | Section 106 (NRHP) | United States |
| `canada_ontario` | Ontario S&G | Canada |
| `australia_burra` | Burra Charter / ICOMOS | Australia |
| `new_zealand` | Heritage NZ Pouhere Taonga | New Zealand |
| `south_africa_sahra` | SAHRA | South Africa |
| `international_generic` | Generic fallback | Any |

Adding a new jurisdiction means writing a single YAML file — no pipeline code changes required. Templates support `extends` inheritance for regional variations (e.g. US state-level overrides).

## Documentation

- **[Full User Guide](docs/user-guide.md)** — installation, phase walkthroughs, ARK import, review dashboard, GPU setup, troubleshooting
- **`hoard --help`** — inline CLI reference
- **Research papers** — see `docs/research-papers/` for architectural deep-dives on multi-provider AI, ecosystem integration, schema unification, and model selection

## Licence

MIT

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and pull request workflow.
