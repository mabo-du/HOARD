# HOARD — Development Plan v1

**Heritage Observation And Report Drafter**
*Planning document derived from Initial_Idea and HOARD_Technical_Design_v2.md*
*Created: 9 May 2026 · Status: Planning*

---

## 1. Current State Assessment

| Artifact | Status | Completeness |
|---|---|---|
| Initial_Idea | Complete | Concept-level vision, core functions, market gap |
| Technical Design v2 | Complete | Full pipeline architecture, model choices, schemas, CLI design, error handling, testing strategy |
| Code | Not started | No project scaffolding, no repo initialised |
| Model evaluation | Not started | All models assumed from documentation — no archaeological-domain eval |
| Jurisdiction templates | Not started | Template engine designed, zero templates written |
| Test data | Not started | Need 3 reference excavations with published reports |

**The technical design is unusually thorough for this stage — it substantially de-risks implementation. The gap is not in design but in execution priority and early validation of the riskiest assumptions.**

---

## 2. Risk Heatmap

| Risk | Likelihood | Impact | Phase Detected | Mitigation |
|---|---|---|---|---|
| **Zero-To-CAD produces unusable geometry from field sketches** | High | High (Phase 2) | Design doc acknowledges | Treat as experimental from day 1; evaluate in Sprint 1; if poor, replace with structured manual input path |
| **TrOCR accuracy on archaeological handwriting degrades below 90%** | Medium | High (Phase 1) | Design doc flags | Confidence gating + review dashboard mitigate; but needs early eval on real context sheets |
| **Qwen3.5-4B Thinking Mode behaviour differs from documented** | Medium | High (Phase 3) | Not flagged | Model may not produce hidden reasoning chains in the format assumed. Must prototype this before building Phase 3. |
| **6 GB VRAM budget is too tight in practice** | Medium | Medium (all phases) | Design doc budgets | Sequential load/clear is sound; but llama.cpp KV cache sizing needs real measurement |
| **Jurisdiction template engine is under-specified for real-world edge cases** | Medium | Medium (Phase 4) | Design doc has schema | Need to write 3 templates to validate the schema before building the engine |
| **ARK system integration scope creep** | Medium | Low-Medium | Listed as Open Question | Defer to v2.1; v1 focuses on file-based input |
| **Model availability / name mismatch at download time** | Low | High (Phase 1-3) | Not flagged | Several models (Chandra OCR 2, MinerU2.5-Pro, Zero-To-CAD) may have different exact names on HF. Verify in Sprint 0. |

---

## 3. Recommended Sprint Plan

### Sprint 0 — Scaffold & Validate (Week 1)

**Goal:** Prove the pipeline can be built before committing to full implementation.

| Task | Output | Est. Effort |
|---|---|---|
| **0.1 — Repo setup** | Python project scaffold (pyproject.toml, src/erd/, tests/, templates/), git init, README | 2h |
| **0.2 — CLI skeleton** | `erd init`, `erd run`, `erd review`, `erd export`, `erd templates` using Click/Typer; all commands print usage and exit | 3h |
| **0.3 — Model availability sweep** | Script that attempts to download each model (TrOCR, Chandra, MinerU, Qwen3.5-4B, Gemma-4-E2B, Zero-To-CAD) from HF; logs exact repo IDs, quantisation variants available, and file sizes | 3h |
| **0.4 — TrOCR archaeological eval** | Take 5 sample context sheets (handwritten, any typeface); run through HTRflow + TrOCR; report per-field accuracy vs manual transcription | 4h |
| **0.5 — Qwen3.5-4B Thinking Mode eval** | Feed one complete context sheet JSON + finds data to Qwen via llama.cpp; observe whether Thinking Mode produces a reasoning chain and whether it follows the `section:*` output format | 3h |
| **0.6 — VRAM smoke test** | Load each model sequentially on target hardware (6 GB GPU); log actual VRAM consumption with `nvidia-smi`; compare to design doc budget | 2h |
| **0.7 — Write first jurisdiction template** | Create `templates/historic_england_cl3.yaml` per design doc schema; validate against a published HE-compliant report | 3h |

**Sprint 0 exit criteria:**
- [ ] All model names/quantisations confirmed available
- [ ] TrOCR field accuracy on real context sheets ≥ 80% (fallback plan if below)
- [ ] Qwen3.5-4B produces usable reasoning chain in Thinking Mode
- [ ] VRAM peak per phase ≤ design doc budget (±15%)
- [ ] CLI skeleton merged with `erd --help` working
- [ ] Historic England template written

**If Sprint 0 reveals a blocker:**
- TrOCR < 80% → Test fallback model (trocr-medieval variant, or switch to PaddleOCR-VL as primary)
- Qwen Thinking Mode doesn't work as expected → Re-assess Phase 3 architecture; consider non-thinking Qwen with chain-of-thought prompting
- VRAM exceeds 5.5 GB on any phase → Adjust quantisation (Q3_K_M or Q2_K), or accept CPU offload for Phase 3 KV cache

---

### Sprint 1 — Phase 0: Ingestion & Triage (Week 2)

**Goal:** A working, testable ingestion pipeline that produces valid manifest JSON.

- Implement file enumeration + hash + extension normalisation
- Implement HEIC/RAW/PDF-to-PNG conversion with minimum DPI enforcement
- Implement OpenCV quality checks (blur, skew, exposure)
- Implement MobileNetV3 image classifier
- Implement CSV validation against known schema variants
- Implement manifest JSON writer + quality summary printer
- Implement halt-on-failure logic for mandatory files
- Unit tests for each quality flag function with synthetic images
- Integration test: feed a known-bad scan directory, verify correct flags

**Exit criteria:**
- [ ] 100% unit test coverage on quality flag functions
- [ ] Manifest JSON validates against schema
- [ ] Pipeline halts with clear message when mandatory file missing
- [ ] Blur/skew/exposure thresholds tuned on 20+ real site photographs

---

### Sprint 2 — Phase 1: Multi-Modal Digitisation (Week 3-4)

**Goal:** Convert scanned records to structured JSON with confidence scoring.

- Implement model loader with sequential load/clear (llama.cpp server or HF transformers)
- Implement HTRflow + TrOCR pipeline for context sheets
- Implement Chandra OCR 2 for checkbox/field extraction
- Implement MinerU2.5-Pro for table parsing (finds catalogues)
- Implement PaddleOCR-VL distortion correction pre-processor
- Implement routing logic from manifest type + quality flags
- Implement review flag generation (confidence < threshold)
- Unit tests: synthetic forms with known answers
- Integration test: full Phase 1 run on 5-context-site dataset

**Exit criteria:**
- [ ] All four model pathways (TrOCR, Chandra, MinerU, PaddleOCR) produce valid schema output
- [ ] Routing logic selects correct model for each input type
- [ ] Confidence thresholds produce review flags at expected rate
- [ ] VRAM peak ≤ 2.0 GB (actual measurement)
- [ ] Field capture rate ≥ 90% on test dataset

---

### Sprint 3 — Phase 2: Spatial Reconstruction (Week 4-5)

**Goal:** Generate captioned photo annotations and first-pass CadQuery geometry.

- Implement Gemma 4-E2B captioning pipeline (photo → structured caption)
- Implement Gemma visual grounding (section drawing → bounding box labels)
- Implement cross-check between photo captions and context sheet data
- Implement Zero-To-CAD pipeline (grounded section → CadQuery script)
- Implement sandbox execution + validation
- Implement REQUIRES_REVIEW flag on all geometry
- Unit tests: CadQuery script validity; caption JSON schema

**Exit criteria:**
- [ ] Photo captions contain structured archaeological descriptions
- [ ] Bounding box labels match context numbers from Phase 1 data
- [ ] Cross-check identifies at least one real inconsistency in test data
- [ ] Zero-To-CAD produces executable CadQuery for ≥ 60% of test drawings
- [ ] VRAM peak ≤ 2.5 GB

---

### Sprint 4 — Phase 3: Synthesis & Drafting (Week 5-6)

**Goal:** Produce a structured first draft from all Phase 1-2 data.

- Implement context assembly from Phase 1-2 outputs
- Implement Qwen3.5-4B server mode via llama.cpp
- Implement system prompt with jurisdiction template schema
- Implement section-by-section output parsing (code block extraction)
- Implement reasoning chain logging
- Implement review triggers (uncertain phrases, missing contexts, phasing contradictions)
- Implement chunk-and-merge fallback for large sites
- Integration test: feed Stoneyfield-level dataset, evaluate draft quality against published report

**Exit criteria:**
- [ ] Draft contains all mandatory sections from jurisdiction template
- [ ] All context numbers in draft are present in input data (zero hallucinated refs)
- [ ] Reasoning chain logged to file
- [ ] Review triggers fire on at least one of: ambiguous dating, missing contexts, contradictory phasing
- [ ] VRAM peak ≤ 5.0 GB (including KV cache)
- [ ] Draft quality: period identification ≥ 85% agreement with published report

---

### Sprint 5 — Phase 4: Compliance Refinement (Week 6-7)

**Goal:** Restructure draft to match jurisdiction template with no factual changes.

- Implement section-by-section compliance pass via Gemma 4-E2B
- Implement mandatory section presence check
- Implement required field verification within sections
- Implement prohibited term scanning and replacement
- Implement heading style correction
- Implement figure caption reformatting
- Implement hallucination guard verification
- Unit tests: template schema parsing; prohibited term detection

**Exit criteria:**
- [ ] All mandatory sections present in output
- [ ] Prohibited term rate = 0%
- [ ] Zero new factual claims added (verify against Phase 3 draft diff)
- [ ] Placeholder insertion works for missing required fields
- [ ] VRAM peak ≤ 2.5 GB

---

### Sprint 6 — Phase 5: Assembly & Export + Review Dashboard (Week 7-8)

**Goal:** Deliverable-ready DOCX/PDF with review workflow.

- Implement figure reference resolution (`[FIG:xxx]` → embedded image)
- Implement appendix generation (Context Register, Finds Concordance, Sample Register)
- Implement bibliography generation
- Implement pandoc export pipeline (DOCX, PDF)
- Implement Harris Matrix SVG generation via graphviz
- Implement archive ZIP packaging
- Implement `erd review` terminal dashboard (rich or textual)
- Implement accept/reject/edit workflow for flagged items
- Integration test: full pipeline end-to-end on Stoneyfield dataset

**Exit criteria:**
- [ ] DOCX opens correctly with heritage org styles
- [ ] PDF generates with embedded fonts
- [ ] All figures, tables, cross-references resolve
- [ ] Review dashboard supports accept / edit / defer for each flag
- [ ] Full pipeline runtime ≤ 25 min on target hardware
- [ ] Acceptance criteria from design doc all met

---

### Sprint 7 — Testing, Docs & Polish (Week 8-9)

- Build integration test dataset (3 reference sites with published reports)
- Run full pipeline against all 3; compare output to published versions
- Write user documentation (CLI reference, tutorial, template authoring guide)
- Create example project
- Performance tuning pass
- Address design doc open questions (decision record for each)

---

## 4. Key Architecture Decisions to Confirm in Sprint 0

These should be resolved before Sprint 1 begins:

| Decision | Options | Recommendation | Rationale |
|---|---|---|---|
| CLI framework | Click vs Typer | **Typer** | Built on Click, native async support, auto `--help`, better for the review dashboard later |
| Inference server | llama.cpp server vs HF transformers vs vLLM | **llama.cpp server** | Design doc is correct: vLLM overhead is unjustified on single GPU; HF transformers lack server-mode KV cache management |
| Review dashboard | Terminal (rich/textual) vs Web (FastAPI+HTMX) | **Terminal (textual)** for v1 | Zero extra dependencies; can add web UI later; textual supports mouse/interactive TUI |
| Config format | YAML vs TOML vs JSON | **YAML** | Matches jurisdiction template format; PyYAML already in dependency list |
| Project data store | SQLite vs flat files | **Flat files** for v1 | Pipeline is phase-sequential; JSON files per phase are simpler and more inspectable; SQLite may be needed later for the review dashboard state |
| ARK system integration | v1 vs v2.1 | **v2.1** | Significant API reverse-engineering effort; file-based input covers the primary use case |

---

## 5. Dependency Acquisition Work Plan (Sprint 0, parallel track)

| Model | Source | Size | Action |
|---|---|---|---|
| MobileNetV3 | torchvision.models | ~20 MB | pip install, no separate download |
| PaddleOCR-VL-1.5 | HuggingFace | ~700 MB | `huggingface-cli download` |
| TrOCR base handwritten | HuggingFace | ~1.2 GB | `huggingface-cli download` |
| HTRflow | pip | ~200 MB | `pip install htrflow` |
| Chandra OCR 2 | HuggingFace | ~4 GB (4-bit GGUF) | `huggingface-cli download` — verify 4-bit variant exists |
| MinerU2.5-Pro | HuggingFace | ~7 GB | `huggingface-cli download` — largest download |
| Qwen3.5-4B Q4_K_M | HuggingFace (Unsloth) | ~2.5 GB GGUF | `huggingface-cli download` |
| Gemma 4-E2B Q4_K_M | HuggingFace (Unsloth) | ~2.1 GB GGUF | `huggingface-cli download` |
| Zero-To-CAD | HuggingFace | ~2 GB | `huggingface-cli download` — verify repo exists |
| llama.cpp | GitHub releases | ~50 MB binary | Download pre-built server binary for platform |
| Total download | | ~20 GB | |

---

## 6. Open Questions (from Design Doc) — Proposed Decisions

From $4 design doc "Open Questions for v2.1":

1. **Review dashboard: terminal vs web?** → Terminal (textual) for v1. Zero extra deps, fast to build. Web UI in v2 if user research shows demand.

2. **Harris Matrix auto-generator in v1?** → Yes. It's a straightforward graphviz rendering from already-available stratigraphic data in the context JSON. Low effort, high value for the report appendices. Include in Sprint 6.

3. **CPU-only hardware spec?** → Defer to v2.1. Target hardware is 6 GB GPU. Document that M-series Mac (unified memory) works. CPU-only x86 is possible but Phase 3 would be 10-20x slower.

4. **ARK system integration?** → v2.1. File-based input covers the primary use case (post-excavation analysis).

5. **Show reasoning chain to user?** → Log to file; do not show in default workflow. Add `erd review --reasoning` flag in v2 to expose it on demand.

---

## 7. Immediate Next Step (What to Do Now)

**Action:** Start Sprint 0.

1. `git init` the repo at `/home/mark/Projects/HOARD`
2. Create the project scaffold with `pyproject.toml`
3. Run the model availability sweep to verify all model names and sizes
4. Run the TrOCR eval on 5 sample context sheets
5. Run the VRAM smoke test on available hardware

Each of these is parallelisable and produces information that directly validates or invalidates the design assumptions before anyone writes significant pipeline code.

Would you like me to begin Sprint 0, or discuss/revise any part of this plan first?
