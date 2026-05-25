# HOARD — Deep Research Prompt

## Project Context (for the AI researcher)

**HOARD** (Heritage Observation And Report Drafter) is a fully local, multi-stage AI pipeline that converts archaeological field data — context sheets, finds catalogues, site photographs, section drawings, and sample results — into a near-publication-ready grey literature report conforming to the relevant heritage authority standard.

The pipeline targets **6 GB VRAM consumer GPUs** (e.g. NVIDIA RTX 3060 12 GB, RTX 4060 8 GB). It runs entirely on-device — zero API calls, no data leaves the machine.

Phases 0 (ingestion/triage) and 5 (assembly/export) are complete. Phases 1–4 require GPU and are the subject of this research.

### Pipeline Phases (for reference)

| Phase | Name | What it does | GPU? |
|-------|------|-------------|------|
| 0 | Ingestion & Triage | Inventory files, normalise formats, assess quality, flag problems | No |
| 1 | Multi-Modal Digitisation | OCR for handwritten forms, checkbox extraction, table parsing | Yes |
| 2 | Spatial Reconstruction | Photo captioning, visual grounding, sketch-to-CAD geometry | Yes |
| 3 | Synthesis & Drafting | Reason through full site dataset, produce structured draft | Yes |
| 4 | Compliance Refinement | Restructure draft to match jurisdiction template conventions | Yes |
| 5 | Assembly & Export | Compile figures/tables/appendices, export DOCX/PDF/archive | No |

### Current Model Selections (from technical design doc)

- Phase 1: TrOCR (handwriting), HTRflow (page segmentation), Chandra OCR 2 (form/checkbox), MinerU2.5-Pro (table parsing), PaddleOCR-VL-1.5 (distortion correction)
- Phase 2: Gemma 4-E2B (photo captioning), Zero-To-Cad-Qwen3-VL-2B (sketch-to-CAD)
- Phase 3: Qwen3.5-4B (synthesis/drafting)
- Phase 4: Gemma 4-E2B (compliance checking)

Note: `opendatalab/MinerU2.5-Pro` (as written in the design doc) returns HTTP 401. The correct HF repo appears to be `opendatalab/MinerU2.5-Pro-2604-1.2B` or the more popular `opendatalab/MinerU2.5-2509-1.2B` (1.4M downloads).

### What has already been researched

The user maintains a curated model list at HuggingFace (https://huggingface.co/models?num_parameters=min:0,max:6B&sort=created filtered to ≤6B params). Notable models already considered:

- Qwen/Qwen3-4B-Instruct-2507 (262K context, 4B params, Apache-2.0, Sep 2025)
- microsoft/Phi-4-mini-instruct (128K context, 3.8B params, MIT, Feb 2025)
- meta-llama/Llama-3.2-3B-Instruct (128K context, 3B params, Oct 2024)
- microsoft/Phi-3.5-mini-instruct (128K context, 4B params)
- nvidia/Nemotron-H-4B-Instruct-128K (128K context, 4B params, Oct 2025)
- ibm-granite/granite-3b-code-instruct-128k (128K context, 3B params)

---

## Research Questions

### Q1: ARK System Data Import — Real-World Export Format Research

ARK (Archaeological Recording Kit) is an open-source digital recording system widely used in commercial archaeology. HOARD has a generic CSV/JSON ARK import module, but needs hardening against real-world data.

**Please investigate:**

1. What are the major ARK versions in active use? We are aware of ARK v3, ARK v4, and FAIMS-based variants.
2. For each version, what are the actual column names and structures used in real-world CSV/JSON exports for:
   - Context sheets (context register)
   - Finds catalogues (small finds)
   - Sample registers (environmental samples)
   - Photo logs
   - Drawing registers
3. Are there any ARK export schema specifications publicly available?
4. Do any archaeological units publish example/sample ARK export data?
5. Are there newer digital field recording systems competing with or replacing ARK that we should also support? (e.g. FAIMS 3.0, OASIS, etc.)
6. What is the most common data interchange format used between archaeological field recording systems and report-generation tools?

**Desired output:** A summary of real-world ARK export column names per version, links to any public schemas or example files, and recommendations for which ARK versions to prioritise.

---

### Q2: Phase 1 OCR Model Landscape — Current State of the Art (2025–2026)

Phase 1 needs to digitise handwritten context sheets, extract checkbox values, parse tables, and correct distorted document images — all within a 6 GB VRAM budget.

**Please investigate each sub-question:**

#### 2a: Handwritten Text Recognition (TrOCR and alternatives)

- Is `microsoft/trocr-base-handwritten` still the best open-weight model for historical/handwritten document transcription, or have newer models surpassed it?
- What about `microsoft/trocr-large-handwritten`? Would it fit in 6 GB VRAM alongside other Phase 1 models?
- Are there any archaeological-domain fine-tunes of TrOCR besides `medieval-data/trocr-medieval-base` and `Riksarkivet/trocr-base-handwritten-hist-swe-2`?
- What about non-TrOCR alternatives (e.g. PaddleOCR's handwriting models, Google's Florence-2, etc.) that might be more accurate?
- Are there any 2025–2026 papers or releases specifically targeting handwritten document digitisation for heritage/cultural heritage applications?

#### 2b: Document Layout / Page Segmentation (HTRflow and alternatives)

- HTRflow is specified for page segmentation — is it still actively maintained?
- Are there better alternatives for segmenting complex archaeological form layouts (sections, tables, checkboxes, free-text fields, drawings)?
- What about YOLO-based layout detectors fine-tuned for forms?
- How do newer vision-language models (e.g. Qwen2.5-VL, Florence-2) compare for document layout analysis?

#### 2c: Table Parsing (MinerU)

- Which MinerU variant is the current recommended version?
  - `opendatalab/MinerU2.5-2509-1.2B` (1.4M downloads)
  - `opendatalab/MinerU2.5-Pro-2604-1.2B` (201K downloads)
  - Are there even newer versions?
- Are there lighter-weight alternatives for table extraction that fit within a 6 GB budget?

#### 2d: Distortion Correction

- Is PaddleOCR-VL-1.5 still the best for document perspective/correction, or are there newer alternatives?

#### 2e: Phase 1 Model Pipeline — VRAM Budget Feasibility

- Could all Phase 1 models run sequentially within 6 GB VRAM (loading and clearing each before the next)?
- What would the recommended loading/unloading order be?
- Are there any models we could replace with CPU-based alternatives to free VRAM?

**Desired output:** A recommended, up-to-date model selection for each Phase 1 sub-task, with HuggingFace links, approximate VRAM usage, and a proposed loading sequence.

---

### Q3: Phase 3 LLM Options — Small Model for Structured Document Drafting

Phase 3 needs to: (a) accept a structured prompt containing hundreds of context records, finds entries, and photo descriptions, (b) reason through the full site dataset, and (c) produce a well-formatted Markdown draft following a specific template. All within 6 GB VRAM.

**Please investigate:**

1. Given the 6 GB VRAM constraint (meaning ~3.5–5.5 GB for the model after KV cache and overhead), what is the optimal model size and quantization level?
   - Q4_K_M of a 4B model (~3.5 GB) — plenty of headroom
   - Q3_K_M of a 7B model (~4-5 GB) — tight but possible
   - Q4_K_M of a 7B model (~5.5 GB) — likely too tight with KV cache

2. We have already identified `Qwen3-4B-Instruct-2507` (262K context, very strong writing benchmarks) as the leading candidate. Are there any newer models (released since September 2025) that surpass it for structured document generation?

3. Are there any models specifically fine-tuned for academic/technical report generation, or for Markdown output?

4. For the 6 GB budget specifically, how much context (in tokens) can we realistically support with:
   - Qwen3-4B-Instruct-2507 at Q4_K_M?
   - A hypothetical 7B model at Q3_K_M?

5. Would a speculative decoding setup (small draft model + larger target model) fit within 6 GB and offer better quality?

6. Are there any inference optimisation techniques (other than standard quantization) that we should be aware of for running 4B–7B models in 6 GB?

**Desired output:** A definitive Phase 3 model recommendation with justification, expected context length support at 6 GB, and any optimisation tips.

---

### Q4: Jurisdiction-Specific Compliance — Recent Standard Updates (2025–2026)

HOARD has 14 jurisdiction templates that define compliance rules (mandatory sections, prohibited terms, heading styles, word limits). These need to reflect current heritage authority standards.

**Please investigate whether any of these jurisdictions have released updated standards in 2025 or 2026 that would affect our compliance rules:**

1. **England** — Historic England (CL3 Evaluation, CL4 Excavation): Any updates to Management of Research Projects in the Historic Environment (MoRPHE) or Historic England's reporting guidelines?
2. **Scotland** — Historic Environment Scotland (DSR): Any data structure report standard updates?
3. **Wales** — Cadw / RCAHMW: Any updates to Welsh archaeological reporting standards?
4. **Ireland** — National Monuments Service: Any Section 26 reporting requirement changes?
5. **Netherlands** — KNA 5.0 (Kwaliteitsnorm Nederlandse Archeologie): Any version updates?
6. **France** — INRAP / Code du Patrimoine: Any regulatory changes?
7. **Germany** — Landesdenkmalpflege: Any Lander-specific standard updates?
8. **United States** — Section 106 (NRHP Eligibility): Any recent guidance changes from the ACHP or NPS?
9. **Canada** — Ontario S&G for Consultant Archaeologists: Any updates to the Standards and Guidelines?
10. **Australia** — Burra Charter (ICOMOS): Any revisions or new practice notes?
11. **New Zealand** — Heritage NZ Pouhere Taonga: Any authority standard updates?
12. **South Africa** — SAHRA: Any amendments to the National Heritage Resources Act reporting requirements?

For any jurisdiction with confirmed updates: what specifically changed (new mandatory sections, removed sections, new format requirements, updated terminology)?

**Desired output:** A table of jurisdictions with 'No change confirmed' or specific details of what changed and when.

---

## Output Preferences

Please provide:
- Specific HuggingFace model URLs where applicable
- Version numbers and release dates
- Approximate VRAM usage figures where known
- Links to papers, blog posts, or GitHub repos for significant findings
- PubMed / arXiv IDs for academic papers cited
- Your confidence level for each recommendation (high/medium/low — based on evidence found)
