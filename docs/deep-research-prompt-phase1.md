# HOARD — Deep Research Prompt: Phase 1 Multi-Modal Digitisation

## Project Context

**HOARD** (Heritage Observation And Report Drafter) is a fully local, multi-stage AI pipeline that converts archaeological field data — handwritten context sheets, finds catalogues, site photographs, section drawings, and sample results — into a near-publication-ready grey literature report.

The pipeline targets **6-8 GB VRAM consumer GPUs** (RTX 3070 laptop 8GB). It runs entirely on-device (zero API calls). Phase 1 is the first GPU-dependent stage.

### Pipeline Phases (for reference)

| Phase | Name | GPU? | Status |
|-------|------|------|--------|
| 0 | Ingestion & Triage | No | Built |
| **1** | **Multi-Modal Digitisation** | **Yes** | **🔥 RESEARCH NEEDED** |
| 2 | Spatial Reconstruction | Yes | Researched (Florence-2 + Qwen3-VL-4B) |
| 3 | Synthesis & Drafting | Yes | Built (Qwen3.5-4B via Ollama) |
| 4 | Compliance Refinement | Yes | Built (Gemma 4-E2B via Ollama) |
| 5 | Assembly & Export | No | Scaffolded (pandoc) |

### Current Phase 1 Design (from technical design v2)

The design doc currently specifies a sequential pipeline:

1. **PaddleOCR-VL-1.5** (conditional) — distortion correction for blurry/skewed documents
2. **Chandra OCR 2** (datalab-to/chandra-ocr-2) — holistic layout + handwriting + checkbox extraction (4B params, 2.8 GB VRAM at 4-bit)
3. **MinerU2.5-Pro-2604-1.2B** (opendatalab/MinerU2.5-Pro-2604-1.2B) — complex cross-page table parsing (1.2B params, 2.4 GB VRAM)

These were selected approximately 3-4 weeks ago via the first round of Deep Research. Given how fast the model landscape has moved (new Qwen3.5, Gemma 4, Llama 4, etc.), these selections may already be outdated.

### What Already Exists

- **Phase 0 (file triage)** — built and tested; classifies documents by type (context_sheet, finds_form, plan, etc.)
- **Phase 1 routing logic** — defined in the design doc (which model gets which document type)
- **Output JSON schema** — defined in the design doc
- **Ollama models available locally**: `glm-ocr:latest` (1.1B, F16), `qwen3-vl:8b` (8.8B, Q4_K_M), `huihui_ai/qwen3.5-abliterated:4B`

### The Problem

Phase 1 is the most critical phase — if the OCR/vision models fail to extract accurate context data, all downstream phases (3, 4, 5) produce garbage. Yet it's the only phase where model selection hasn't been re-evaluated in light of April-May 2026 releases.

---

## Research Questions

### Q1: What Is the State of the Art in Small VLM-Based Document Extraction (May 2026)?

The paradigm has shifted from cascaded models (separate detection + segmentation + HTR + OCR) to unified Vision-Language Models that handle layout, handwriting, checkboxes, and tables in a single pass. **Please investigate:**

- **Chandra OCR 2** (datalab-to/chandra-ocr-2) — claimed 85.9% on olmOCR benchmark. Is it still competitive? Are there newer models (Chandra 3? Chandra-2026?) that supersede it?
- **GLM-OCR** (1.1B, F16) — already installed locally. A custom-renderer OCR model in Ollama. What benchmark scores exist? Is it suitable for complex structured form extraction (context sheets with checkboxes, coded fields, handwriting)?
- **GOT-OCR-2** / **GOT-OCR-2.5** — general OCR models. Any updates in 2026?
- **Qwen3-VL variants** — the 4B vision model was selected for Phase 2 captioning. Are there dedicated Qwen VL document models?
- **Phi-3.5-vision-instruct** / **Phi-4-vision** — already in your HF cache. Could these serve as document parsers?
- **Docling** (IBM, MIT) — a toolkit rather than a model, but uses DocLayNet + TableFormer for layout-aware PDF extraction. Mentioned in the fine-tuning research as the corpus pipeline. Could it serve as Phase 1 directly?
- **Any new small vision models released in April-May 2026** that target document understanding specifically

For each candidate, provide:
- Parameter count and VRAM footprint at 4-bit
- License (must be Apache 2.0, MIT, or compatible for open-source distribution)
- Supported input types (handwriting? checkboxes? form fields? tables? sketches?)
- Benchmark performance on document understanding tasks (ocrBench, olmOCR, DocVQA, etc.)
- Availability of GGUF format or Ollama support
- Whether it natively outputs structured JSON or requires post-processing

### Q2: What Is the Optimal Phase 1 Model Architecture for 8GB VRAM?

Phase 1 needs to handle **three distinct document types** from a typical archaeological evaluation:

| Document Type | Content | Challenges |
|--------------|---------|------------|
| **Context sheet** (handwritten form) | Context number, type (cut/layer/deposit), soil description, inclusions, interpretation, finds list, sketches | Handwriting variability, checkboxes, coded fields, mixed print/handwriting |
| **Finds catalogue** (typed/printed) | Tables: context number, object type, quantity, period, notes | Cross-page tables, varied column layouts, sometimes handwritten annotations |
| **Existing typed notes** (DOCX/TXT/MD) | Free-text narrative or partial draft | Minimal — straightforward text ingestion |

**Please recommend:**
- The optimal model architecture for 8GB VRAM. Options to evaluate:
  - **Single VLM for everything** (e.g., one 4B model handles both context sheets and tables)
  - **Two specialist models** (VLM for forms + table parser for catalogues)
  - **Three models** (distortion corrector + form extractor + table parser — as currently designed)
- Whether **PaddleOCR-VL-1.5** is still needed as a pre-processor, or whether modern VLMs handle distortion natively
- Whether **MinerU** (1.2B) is the best table parser, or whether newer/smaller alternatives exist
- The optimal VRAM budget split between models given the 8GB ceiling
- Whether **llama.cpp router mode** is appropriate for Phase 1 model swapping (same pattern as Phase 2-4), or whether Python torch loading is more suitable for vision models

### Q3: How Should Structured Output Be Enforced?

Phase 1 must output structured JSON conforming to a canonical schema. The model output needs to map to fields like:
```json
{
  "context_number": "[374]",
  "type": "layer",
  "cut_by": ["[312]", "[356]"],
  "cuts": [],
  "fills": ["[375]"],
  "description": "Mid brown silty clay...",
  "interpretation": "Probable ploughsoil horizon.",
  "period": "Post-medieval",
  "finds": [
    {"type": "ceramic", "qty": 3, "period": "Post-medieval"}
  ],
  "samples": [],
  "review_flags": []
}
```

**Please investigate:**
- Whether modern VLMs can reliably output structured JSON directly (constrained decoding, grammar, or schema enforcement)
- Whether **Ollama's JSON mode** (`format: "json"`) is sufficient, or whether a post-processing parser is needed
- How to handle low-confidence fields (the schema has `review_flags` for fields below confidence threshold)
- How to validate the output JSON against the canonical schema (required fields, data types, controlled vocabulary)

### Q4: What Is the Fallback Strategy for Low-Quality Documents?

Real archaeological documents include:
- 1990s dot-matrix printed forms
- Carbon-copy context sheets with faint text
- Mud-stained or water-damaged field records
- Photocopied sheets (3rd+ generation copies)

**Please investigate:**
- What image pre-processing improves VLM extraction accuracy (deskew, contrast enhancement, adaptive thresholding, denoising)
- Whether the Phase 0 quality flags (BLUR_LOW, SKEW_HIGH, EXPOSURE_LOW) should route to different models or pre-processing paths
- The accuracy degradation curve for each candidate model on degraded documents
- Whether specialised HTR models (trocr-medieval-base, historical-swe) are still worth having as an alternative pipeline path

### Q5: Integration with Existing Infrastructure

- Should Phase 1 use **Ollama** (same pattern as Phase 3/4), or **llama.cpp server** directly, or **transformers** (`pipeline`)?
- Vision models often need image preprocessing — how should images be converted and passed to the model?
- How should the existing Phase 0 manifest feed into Phase 1 routing?

---

## Research Deliverables

Please return:

1. **Recommended model architecture** — single model vs. multi-model, with rationale and VRAM budget
2. **Per-model details** — names, HuggingFace links, VRAM, license, benchmark scores, GGUF/Ollama availability
3. **Structured output strategy** — how to enforce JSON schema output with confidence thresholds
4. **Document pre-processing required** — what image corrections improve accuracy
5. **Fallback paths** — what happens when documents are too degraded for the primary model
6. **Dependency list** — Python packages, model downloads, Ollama imports needed
7. **Implementation risk register** — known failure modes and mitigations

## Key Constraints

- **6-8 GB VRAM** (RTX 3070 laptop 8GB)
- **Zero API calls** — all models must run locally
- **Open-source licenses** only (Apache 2.0, MIT, BSD, CC-BY)
- **Ollama or llama.cpp** preferred for model serving
- Must integrate with existing **Phase 0 manifest routing** and **Phase 1 output schema**
