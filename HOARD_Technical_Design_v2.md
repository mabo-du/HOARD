HOARD: Heritage Observation And Report Drafter

**Technical Design Document**

*Local Multi-Stage Pipeline · 6 GB VRAM Target (8 GB VRAM verified) · v2.0*

 

Revised: 25 May 2026  ·  Status: Draft for Review

*Updated to reflect 2026 Deep Research findings (Rounds 1-5): Phase 1: GLM-OCR + Granite-Docling replaces Chandra OCR 2 + MinerU (licensing compliance); Qwen3.5-4B (prompt-engineered, fine-tuning deferred) replaces Qwen3-4B-Thinking-2507; semantic ARK header mapping; jurisdiction template updates for England (Dec 2025/Feb 2026), Netherlands KNA 5.0 (Mar 2026), Ontario ERO 026-0216 (Mar 2026); Phase 4 RAG-based compliance (no fine-tune); Phase 5 Markdown→Jinja→WeasyPrint document generation pipeline with specialist appendix deterministic NLG.*


# **Document Purpose & Scope**

This document is the authoritative technical design for the Excavation Report Drafter: a fully local, multi-stage AI pipeline that converts raw field data — handwritten context sheets, finds catalogues, site photographs, section drawings, and sample results — into a near-publication-ready grey literature report conforming to the relevant national or regional heritage authority standard.

This revision substantially expands the original outline to provide: concrete intermediate data schemas, per-model VRAM budgets, confidence-gated review triggers, fallback strategies, a jurisdiction template engine specification, a CLI interface design, error handling policies, and a testing plan. A developer reading this document should be able to produce a working implementation without further scoping research.

| **ℹ  NOTE** | The pipeline is intentionally modular. Each phase writes its output to disk before the next phase loads. This allows models to be loaded and cleared sequentially, keeping peak VRAM within the 6 GB envelope, and allows individual phases to be re-run without repeating earlier work. |
| :-: | - |



# **System Architecture Overview**

The pipeline consists of five discrete phases plus a final assembly step. Each phase is an independent Python process invoked by a CLI orchestrator. All intermediate outputs are written to a structured working directory (./erd\_workspace/\{project\_id\}/).


| **Phase** | **Name** | **Input** | **Output** | **Primary Model(s)** |
| - | - | - | - | - |
| 0 | Ingestion & Triage | Raw files (PDF, JPG, PNG, CSV) | File manifest JSON + quality flags | Rule-based + ARK semantic mapper |
| 1 | Multi-Modal Digitisation | Scanned images, photos, PDFs | Structured JSON + Markdown tables | GLM-OCR (handwriting/forms) + Granite-Docling-258M (tables) + Qwen3-VL-4B (fallback) |
| 2 | Spatial Reconstruction | Plans, sections, drawings | CadQuery Python + annotated images | Zero-To-CAD + Gemma 4-E2B |
| 3 | Synthesis & Drafting | All Phase 1-2 outputs | Structured draft (Markdown) | Qwen3.5-4B (QLoRA fine-tuned on ADS grey literature corpus) |
| 4 | Compliance Refinement | Draft + jurisdiction template + RAG vector store | Compliant report (Markdown) | Gemma 4-E2B (prompt-engineered, NOT fine-tuned) + lightweight RAG over current template docs |
| 5 | Assembly & Export | Refined report + assets | Final DOCX + PDF/A-2b + archive ZIP | Hybrid: python-docx (DOCX) + WeasyPrint (PDF/A-2b) + rectpack/Graphviz (figures) + pyHanko (signatures) |


## **Working Directory Structure**

| erd\_workspace/   \{project\_id\}/     00\_manifest/        \# Phase 0 file manifest and quality report     01\_digitised/       \# Phase 1 JSON outputs per source document     02\_spatial/         \# Phase 2 CadQuery scripts and annotated images     03\_draft/           \# Phase 3 Markdown draft sections     04\_refined/         \# Phase 4 jurisdiction-compliant Markdown     05\_final/           \# Final DOCX, PDF, archive ZIP     assets/             \# Copied/normalised input images for embedding     logs/               \# Per-phase logs with model confidence scores     pipeline\_state.json \# Resumable pipeline state |
| - |


## **Resumability**

Each phase checks pipeline\_state.json before running. If a phase is marked "complete" it is skipped. This allows the pipeline to be re-started after a crash or power cut without re-running expensive inference steps. Individual phases can be force-re-run with the --rerun-phase N flag.




| **PHASE** **0** | **Ingestion & Triage** *Normalise inputs, assess quality, flag problems before expensive inference begins* |
| :-: | - |


## **Purpose**

Before any model is loaded, all input files are inventoried, normalised, and assessed for quality. This phase is entirely rule-based and costs zero VRAM. Its job is to catch problems early — corrupt files, unreadable scans, missing mandatory fields — so that the researcher is informed before the pipeline spends 20 minutes on Phase 1.

## **Input Specification**

The pipeline accepts the following input types, placed in an ./input/ directory or specified individually via CLI flags:

| **File Type** | **Expected Source** | **Format(s) Accepted** | **Mandatory?** |
| - | - | - | - |
| Context sheets | Site recording forms (handwritten or printed) | JPG, PNG, PDF, HEIC | Yes |
| Finds catalogue | Finds register (typed CSV or handwritten form) | CSV, XLSX, JPG, PNG, PDF | Yes |
| Site photographs | Field photography | JPG, PNG, HEIC, RAF, NEF | No |
| Plans | Drawn or CAD-exported site plans | JPG, PNG, PDF, DXF, SVG | No |
| Section drawings | Drawn section profiles | JPG, PNG, PDF, SVG | No |
| Sample results | Environmental / dating lab reports | PDF, CSV, TXT | No |
| Existing text | Previously typed notes or partial draft | TXT, DOCX, MD | No |


## **Triage Steps**

1. Enumerate all files in the input directory and log extensions, sizes, and hashes.

2. Convert HEIC, RAW, and multi-page PDF inputs to normalised PNG (300 DPI minimum) using Pillow / Wand. Store in 

3. Run a fast image quality check using OpenCV: detect blur (Laplacian variance \< 80 = flag), extreme skew (\> 15° = flag), and underexposure (mean pixel value \< 40 = flag).

4. Classify each image as: context\_sheet, finds\_form, site\_photo, plan, section, or unknown using a lightweight classifier (MobileNetV3, \< 20 MB, no GPU needed).

5. For CSV/XLSX finds catalogues: validate column headers against known schema variants; flag missing mandatory columns.

6. Write the file manifest and quality report to 00\_manifest/manifest.json.

7. Print a human-readable quality summary to stdout and halt if any MANDATORY file is missing or if \> 30% of context sheets are flagged as unreadable.


## **Manifest Schema**

| // 00\_manifest/manifest.json \{   "project\_id": "stoneyfield\_2026",   "created": "2026-05-09T14:32:00Z",   "files": \[     \{       "id": "ctx\_001",       "path": "assets/context\_sheet\_001.png",       "type": "context\_sheet",       "quality": \{         "blur\_score": 142.3,         "skew\_deg": 1.2,         "exposure\_mean": 178,         "flag": null       \}     \},     \{       "id": "ctx\_002",       "path": "assets/context\_sheet\_002.png",       "type": "context\_sheet",       "quality": \{         "blur\_score": 31.1,         "flag": "BLUR\_LOW"       \}     \}   \],   "mandatory\_check": "PASS",   "quality\_warnings": 1 \} |
| - |




| **PHASE** **1** | **Multi-Modal Digitisation** *Convert physical records into structured JSON — the data substrate for all later phases* |
| :-: | - |


## **Overview**

Phase 1 transforms scanned archaeological documents into structured JSON. Rather than a fixed cascade of models, it uses a **tri-partite routing strategy** driven by the Phase 0 manifest. Each document type is routed to the specialist model best suited for it. VRAM is managed via Ollama's `keep_alive` parameter rather than llama.cpp router mode (which suffers race conditions on sub-12GB cards).

## **Key Research Finding (May 2026)**

The landscape of document extraction has shifted decisively toward unified Vision-Language Models. Two critical licensing changes drove the model selection:

| Model | Status | Reason |
|---|---|---|
| **Chandra OCR 2** | ❌ Rejected | OpenRAIL-M license imposes revenue cap ($2M) — blocks open-source distribution to CRM units |
| **MinerU** | ❌ Rejected | AGPL-3.0 viral license requires source disclosure for network use — prohibitive for commercial CRM |
| **PaddleOCR-VL-1.5** | ❌ Replaced | Modern VLMs handle distortion natively; no longer needed as separate pre-processor |
| **GLM-OCR** (0.9B) | ✅ Adopted | MIT / Apache 2.0, 94.62 OmniDocBench, native JSON schema output, 2.2 GB VRAM |
| **Granite-Docling-258M** | ✅ Adopted | Apache 2.0, <1 GB VRAM, replaces MinerU for table parsing without AGPL concerns |
| **Qwen3-VL-4B** | ✅ Fallback | Apache 2.0, 4B params, used when GLM-OCR fails on degraded documents |

## **Model Routing Logic**

| **Document Type** | **Routed To** | **Why** |
|---|---|---|
| context\_sheet (handwritten form) | GLM-OCR + Pydantic structured output | MIT license, native JSON schema adherence, fast Multi-Token Prediction |
| finds\_catalogue (typed/printed) | Docling + Granite-Docling-258M | Apache 2.0, layout-aware table extraction, cross-page merging |
| finds\_catalogue (CSV/XLSX) | pandas direct parse | Zero VRAM, faster than any model |
| plan / section / site\_photo | Phase 2 (spatial) | Handled by Florence-2 + Qwen3-VL-4B in Phase 2 |
| existing\_text (DOCX/TXT/MD) | Docling CPU parser | Zero VRAM, direct text ingestion |
| Degraded / low-confidence | Qwen3-VL-4B fallback | 4B params, better resilience to noise, Apache 2.0 |


## **1a — Document Pre-Processing (CPU, zero VRAM)**

Degraded archaeological documents (faint carbon copies, mud-stained sheets, poor photocopies) are pre-processed by CPU-bound OpenCV algorithms before VLM inference:

| **Quality Flag** | **Algorithm** | **Effect** |
|---|---|---|
| SKEW\_HIGH | Hough Line Transform → affine rotation | Realigns skewed scans to horizontal |
| EXPOSURE\_LOW / BLUR\_LOW | CLAHE (Contrast Limited Adaptive Histogram Equalization) | 8x8 tile contrast enhancement, pulls faint handwriting from muddy backgrounds |
| Any flag | Adaptive thresholding + morphological opening/closing | Separates ink from background noise; bridges broken strokes in cursive |

Images are also resized to a maximum of 2048px on the longest edge to prevent KV cache overflow in GLM-OCR (which requires `num_ctx` ≥ 16384 for high-res image processing).


## **1b — Context Sheet Extraction (GLM-OCR)**

| **Parameter** | **Value** |
|---|---|
| Model | zai-org/GLM-OCR (0.9B params: 0.4B CogViT + 0.5B GLM decoder) |
| VRAM footprint | ~2.2 GB via Ollama |
| License | MIT (weights) / Apache 2.0 (code) |
| OmniDocBench score | 94.62 |
| Key architecture | Multi-Token Prediction (MTP) — predicts multiple tokens per step for fast OCR throughput |
| Ollama context | `num_ctx: 16384` required for image processing |
| Temperature | 0.0 (greedy decoding — no creative hallucination) |
| Structured output | Pydantic schema injected via Ollama `format` parameter (constrained decoding) |
| Output validation | `ContextSheet.model_validate_json()` — secondary Pydantic enforcement layer |
| Low-confidence handling | Self-reported via `review_flags` array in schema; model appends flag when uncertain |

The Pydantic schema constrains the model's token generation at the tensor level — the decoding algorithm masks logits that would violate the JSON grammar. This ensures structurally valid output:

```python
class ContextSheet(BaseModel):
    context_number: str
    type: str                    # layer, cut, deposit, etc.
    cut_by: list[str]
    cuts: list[str]
    fills: list[str]
    description: str
    interpretation: str
    period: str
    finds: list[Find]
    samples: list[dict]
    review_flags: list[dict]     # self-reported ambiguity
```

## **1c — Table & Catalogue Parsing (Docling)**

| **Parameter** | **Value** |
|---|---|
| Model | ibm-granite/granite-docling-258M (258M params: SigLIP2 + Granite 165M) |
| VRAM footprint | <1 GB |
| License | Apache 2.0 |
| Framework | Docling library (IBM/MIT) — replaces MinerU entirely |
| Key capability | Heron layout models for cross-page table merging; Markdown/HTML/JSON export |
| Performance | 12-page extraction in 8.2s (vs MinerU 14.7s) |
| Input types | PDF, image, DOCX, TXT, HTML — all handled by same pipeline |
| Typed notes | CPU-bound parser for DOCX/TXT/MD — zero VRAM cost |

## **1d — Fallback for Degraded Documents**

If GLM-OCR fails Pydantic validation after 2 attempts, the pipeline:
1. Evicts GLM-OCR from VRAM (`keep_alive: 0`)
2. Loads **Qwen3-VL-4B** as fallback
3. Attempts extraction again with the same image
4. Flags output with `review_flags: [{field: "_model", issue: "Fallback model used"}]`
5. If fallback also fails: marks document for human review with blank placeholder JSON

## **VRAM Management Protocol**

Rather than llama.cpp router mode (which has race conditions on rapid model switching), Phase 1 uses **Ollama's `keep_alive` parameter** for deterministic VRAM control:

```
1. Load GLM-OCR with keep_alive=-1     → locked in VRAM during context sheet batch
2. Process all context sheets            → GLM-OCR stays resident
3. Evict GLM-OCR: keep_alive=0          → VRAM freed immediately
4. gc.collect() + time.sleep(2)         → garbage collection
5. Load Docling (via transformers)      → <1 GB for table processing
6. Process all catalogues                → Docling stays resident
7. Unload Docling                        → VRAM freed
```

Absolute peak VRAM = max(2.2 GB, <1 GB) = **2.2 GB** — comfortably within 8 GB.

## **Phase 1 VRAM Budget**

| **Route** | **Task** | **Model** | **VRAM** | **Lifecycle** |
|---|---|---|---|---|
| Route 1 | Handwriting + forms + checkboxes | GLM-OCR | ~2.2 GB | Load → batch → evict |
| Route 2 | Tables + typed documents | Granite-Docling-258M | <1 GB | Load → batch → evict |
| Route 3 | Typed notes (DOCX/TXT/MD) | Docling CPU parser | 0 GB | No GPU needed |
| Fallback | Degraded documents | Qwen3-VL-4B | ~2.8 GB | Evict GLM-OCR first, then load |
| **Peak** | Worst case (GLM-OCR) | | **~2.2 GB** | 5.8 GB headroom on 8 GB GPU |

### Checkbox & Categorical Field Post-Processing

GLM-OCR outputs checkbox lines verbatim (e.g. `"Layer (✓) Cut ( ) Deposit ( ) Fill ( )"`). A lightweight post-processor normalises these into clean categorical values:

| **Raw GLM-OCR Output** | **Parsed Value** |
|---|---|
| `"Layer (✓) Cut ( ) Deposit ( ) Fill ( )"` | `"layer"` |
| `"Layer ( ) Cut (✓) Deposit ( ) Fill ( )"` | `"cut"` |
| `"Yes (✓) No ( )"` | `True` |

This is implemented as a Python regex pass over the extracted JSON before it's written to the `01_digitised/` directory. No model inference needed.

## **v1.1 Enhancement: NuExtract3**

[NuExtract3](https://huggingface.co/numind/NuExtract3) is a 4B vision-language model built on Qwen3.5-4B, specifically fine-tuned for structured JSON extraction from documents. It is a strong candidate to replace or supplement GLM-OCR for Phase 1 context sheet extraction, particularly for:

- **Categorical field inference** — better at mapping visual content to enum-type JSON schema fields (context type, period)
- **Structured output fidelity** — trained specifically for schema-constrained extraction rather than relying on Ollama's grammar-mask approach
- **Shared base model** — shares the Qwen3.5-4B backbone with Phase 3, potentially allowing shared KV cache optimisations

**Not adopted for v1** due to:
- No Ollama support — requires transformers library (heavier dependency, no GGUF quantisation available)
- Larger VRAM footprint (~3-4 GB vs GLM-OCR's 2.2 GB)
- Not yet evaluated against real archaeological context sheets
- Integration cost exceeds benefit for initial release

**Adoption path for v1.1:** Once the pipeline is stable with GLM-OCR, evaluate NuExtract3 on a corpus of 20-50 real context sheets. If categorical accuracy improves >10%, swap Route 1 from GLM-OCR to NuExtract3. The Phase 1 architecture is model-agnostic — the swap requires changing only the Ollama call to a transformers inference call.




| **PHASE** **2** | **Spatial & Technical Reconstruction** *Translate site drawings and photographs into technical geometry and annotated visual evidence* |
| :-: | - |

*Note: Phase 2 was substantially revised following May 2026 Deep Research. The original design specified Gemma 4-E2B for visual grounding and Zero-To-CAD for sketch-to-CAD. Both were found unsuitable — see below for replacements.*

## **Overview**

Phase 2 handles the visual interpretation of plans, section drawings, and site photographs. It has two distinct sub-tasks: (2a) producing structured captions and visual grounding from site photography and section drawings, and (2b) converting hand-drawn plans into digital geometry for the archive statement.

Both sub-tasks run via **llama.cpp router mode** (`--models-max 1`), which handles sequential model loading/swapping at the C++ level using LRU eviction. No programmatic Python model loading is used.

## **2a — Visual Grounding & Photo Captioning (Two-Stage Pipeline)**

Gemma 4-E2B was found unsuitable for Phase 2 visual tasks. Its Per-Layer Embedding (PLE) architecture, while efficient for mobile deployment, lacks the spatial position embeddings needed for precise 2D/3D bounding box grounding and stratigraphic feature identification. It is replaced by a two-stage pipeline:

**Stage 1 — Bounding Box Extraction (Florence-2-large)**
| **Parameter** | **Value** |
| - | - |
| Model | microsoft/Florence-2-large |
| VRAM footprint | ~1.5 GB (FP16) |
| Function | Initial visual grounding: extract bounding box coordinates + labels for stratigraphic features, scale rods, north arrows |
| Output | Structured text with coordinate arrays and class labels |
| Why | 771M parameters, trained on FLD-5B (5.4B annotations across 126M images), natively outputs bounding boxes without complex prompt engineering |

**Stage 2 — Semantic Synthesis & Cross-Check (Qwen3-VL-4B-Instruct)**
| **Parameter** | **Value** |
| - | - |
| Model | Qwen/Qwen3-VL-4B-Instruct |
| VRAM footprint | ~2.9 GB at 4-bit GGUF |
| Context length | 262,144 tokens (scalable to 1M via YaRN) |
| Attention | Interleaved-MRoPE — enables superior 2D/3D spatial-temporal modeling |
| Function 1 — Captioning | Generate structured archaeological caption from Florence-2 grounding output |
| Function 2 — Cross-check | Ingest Phase 1 context sheet text alongside image; flag inconsistencies (e.g. "photo shows masonry but context sheet says layer") |
| Output | Per-image JSON with caption, synthesised grounding labels, and cross-check results |
| Reasoning variant | **Instruct** (not Thinking) — Thinking models have 2.5-4.5s TTFT latency and consume context on \<think\> tags, which is detrimental in constrained VRAM |

**Why not Gemma 4-E2B:** Gemma 4-E2B scores ~43.3% on GPQA vs Qwen3-VL-4B's 49.4–64.1%. Its PLE architecture lacks the spatial position encoding needed for archaeological stratigraphic grounding. Gemma 4-E2B is retained for Phase 4 compliance refinement only, where its text-focused instruction following is still valuable.

### Cross-Check Feature

The cross-check is a defining HOARD capability. Qwen3-VL-4B's 256K context window allows it to ingest both the site photograph AND the corresponding Phase 1 OCR context sheet text simultaneously. Using Retrieval-Augmented Generation principles entirely within the long context (no external vector store needed), the model can:

1. Identify features visible in the photograph (stone wall, cut line, fill deposit)
2. Scan the context sheet text in its active memory for the corresponding description
3. Flag discrepancies: "Visual evidence shows 'masonry wall fragment' but context sheet describes 'silty clay layer'"
4. Output a structured inconsistency report with confidence scores

Aggressive 8-bit KV cache quantization is required to prevent the 256K context from exceeding 6 GB VRAM during this operation.

### Photo Caption Output Schema

| // 02\_spatial/photo\_DSC0042.json \{   "source\_file": "DSC0042.jpg",   "model": "qwen3-vl-4b-instruct",   "caption": "North-facing section through contexts \[312\] and \[374\]. Scale rod visible (1m). Clear horizon break at c.0.4m depth. Darker fill \[312\] overlies paler natural \[374\].",   "grounding": \[     \{ "label": "context\_312", "bbox": \[0.1, 0.05, 0.9, 0.42\], "confidence": 0.91, "source": "florence-2" \},     \{ "label": "context\_374", "bbox": \[0.1, 0.42, 0.9, 0.95\], "confidence": 0.88, "source": "florence-2" \},     \{ "label": "scale\_rod",   "bbox": \[0.82, 0.0, 0.88, 1.0\],  "confidence": 0.97, "source": "florence-2" \}   \],   "cross\_check": \{     "matching\_contexts": \["\[312\]", "\[374\]"\],     "inconsistencies": \[\]   \} \} |
| - |


## **2b — Digital Geometry from Field Drawings**

**Zero-To-CAD-Qwen3-VL-2B** was evaluated and found unsuitable for archaeological field drawings. It was trained exclusively on 1,000,000 synthetic 3D CAD construction sequences of mechanical parts (brackets, gears, housings) and requires 8 rendered multi-view inputs at 256×256. Archaeological section drawings are single 2D orthographic projections with hachures, stippling, and symbolic conventions that the model has never seen. Applying Zero-To-CAD would produce catastrophic hallucination (interpreting a hachured slope as a mechanical chamfer).

**TRELLIS.2-4B** was also evaluated and rejected — requires minimum 24 GB VRAM for native execution.

### Primary Path: 2D SVG Vectorization

The recommended approach for the majority of archaeological drawings. Field drawings are inherently 2D spatial maps. Converting them to SVG vector graphics preserves the original linework digitally without inventing z-axis depth that does not exist in the source material.

| **Parameter** | **Value** |
| - | - |
| Approach | Prompt Qwen3-VL-4B-Instruct to output SVG path data from the grounded section drawing |
| Output | SVG file with labelled stratigraphic layers, cut lines, and annotations |
| Archive use | Included in digital archive as supplement to the original scanned drawing |
| Fallback | If SVG generation fails, the original scanned drawing is used as the report figure |

### Optional Path: Parametric 3D via Build123d

If true parametric 3D geometry is required by the archive specification, use **Build123d** instead of CadQuery. Build123d operates on the same OpenCASCADE kernel but uses explicit Python context managers (`with` blocks) rather than CadQuery's fluent method-chaining API. Language models demonstrably produce fewer syntax errors with Build123d because its structure mirrors standard Python OOP.

| **Parameter** | **Value** |
| - | - |
| Library | Build123d (OpenCASCADE kernel, same as CadQuery) |
| API paradigm | Explicit context managers (standard Python OOP) |
| LLM generation reliability | **High** — standard Python syntax, easy for attention mechanisms to track |
| Vs CadQuery reliability | CadQuery: Low (invisible topological state stack causes frequent errors) |
| Validation | AST sanitisation → ephemeral Docker/Wasm execution → STEP/STL export check |
| Self-correction | Failure traceback piped back to Qwen3-VL for automated fix pass |

### Validation Sandbox

Generated geometry code (whether SVG or Build123d) must be validated before archive inclusion:

1. **AST Parsing**: Strip imports of os, sys, subprocess, and network libraries
2. **Execution**: Run in ephemeral Docker container or Pyodide (Wasm Python) with memory limits
3. **Success**: Compiles + exports valid STEP/STL/SVG → flag as GEOMETRY\_PASS
4. **Failure**: Capture Python traceback, pipe to Qwen3-VL for automated correction pass, retry
5. **Human gate**: All geometry flagged REQUIRES\_REVIEW before archive inclusion regardless of pass/fail


## **Phase 2 VRAM Budget**

All model loading/swapping is handled by **llama.cpp router mode** (`llama-server --models-dir ./hoard_models --models-max 1`). The router uses LRU eviction at the C++ level — no Python `torch.cuda.empty_cache()` calls needed.

| **Step** | **Model** | **VRAM** | **Orchestration** |
| - | - | - | - |
| 2a(i) | Florence-2-large (FP16) | ~1.5 GB | llama.cpp router loads → processes → evicted on 2a(ii) request |
| 2a(ii) | Qwen3-VL-4B-Instruct (4-bit GGUF) | ~2.9 GB | Router swaps Florence → Qwen3-VL automatically |
| 2b (cond.) | Qwen3-VL-4B-Instruct (reused) | ~2.9 GB | Already loaded; system prompt changed for geometry task |
| **Peak** | Qwen3-VL-4B-Instruct alone | **~2.9 GB** | Comfortably within 6 GB (3.1 GB headroom) |

| **✔  TIP** | Because llama.cpp router keeps the CUDA context perpetually initialised, model switching between phases (Phase 2 → Phase 3 → Phase 4) incurs zero process-restart latency — only the weight transfer across PCIe. This is transformative for pipeline runtime vs. naive Python load/unload cycles. |
| :-: | - |




| **PHASE** **3** | **Synthesis & Narrative Drafting** *Reason through the full site dataset and produce a structured first draft* |
| :-: | - |


## **Overview**

This is the most cognitively demanding phase. The model is given the complete digitised record — all context sheet JSON, finds data, sample results, photo captions, and stratigraphic relationships — and is tasked with producing a structured Markdown draft matching the report skeleton defined by the jurisdiction template (see Section 8).

**v1 uses prompt-engineered Qwen3.5-4B** with a carefully crafted system prompt. The base model is already excellent — 262K context, dual-mode thinking/instruct, Apache 2.0 — and produces competent drafts without any fine-tuning. A domain-specific QLoRA adapter (trained on ADS grey literature corpus) remains a **v1.1 enhancement** for improved terminology precision, but is not required for the pipeline to function.

## **Model Selection**

| **Parameter** | **Value** |
| - | - |
| Base model | Qwen/Qwen3.5-4B (Apache 2.0, Gated DeltaNet + sparse MoE architecture) |
| Fine-tuning method | QLoRA via Unsloth (rank 32, alpha 64, target all linear layers) |
| VRAM footprint (inference) | ~2.8 GB base model at Q4\_K\_M GGUF + ~0.1 GB LoRA adapter |
| Context length | 262,144 tokens native (262K) |
| Thinking Mode | Enabled — dual-mode architecture: thinking mode for complex stratigraphic logic, instruct mode for formatting |
| Inference engine | llama.cpp server mode with `--lora-scaled` for adapter hot-swapping |
| Temperature | 0.3 for drafting (low creativity, high fidelity to input data) |
| Training corpus | ~50,000 ADS grey literature reports + ~20,000 tDAR reports (CC-BY / ADS terms), processed via Docling |
| Training GPU | Any GPU via QLoRA. **Free options:** Google Colab (T4 16GB — recommended; you already have a Colab workflow for cunAIform), Kaggle (30 hrs/wk P100), or local (8GB VRAM — slower but works with batch_size=1 + gradient accumulation). ~60-80 GPU-hours on 4090; longer on smaller GPUs but entirely free. |
| LoRA adapter size | ~50-100 MB (distributed separately from base model for low-bandwidth updates) |
| Output format | Structured Markdown with section headers matching jurisdiction template |
| Key advantage | ArchaeoBERT-level terminology + LLM-level reasoning; eliminates colloquial synonyms ("sandy soil" vs "loamy sand") |
| Update mechanism | New training data → new LoRA adapter download (~100 MB only, no full model re-download) |
| Training GPU (free options) | **Kaggle free** (30 hrs/wk P100/T4), **local RTX 3060 12GB** (slow but free), **Google Colab free** (T4 + resumable checkpoints) |
| Distribution | LoRA adapter hosted on Hugging Face — one person trains, everyone downloads at zero cost |
| v1 fallback | If no LoRA adapter is present, the pipeline falls back to prompt-engineered Qwen3.5-4B base model. Fine-tuning is a v1.1 enhancement, not a v1 blocker. |


| **ℹ  NOTE** | vLLM and SGLang are excellent for high-throughput server deployments but carry significant overhead (Ray cluster, CUDA graph capture) that is unnecessary and harmful on a single 6 GB consumer GPU. Use llama.cpp in server mode instead — it is specifically optimised for local single-GPU inference and handles the KV cache correctly at this memory level. |
| :-: | - |


## **Fine-Tuning Corpus & Methodology**

### ⏭️  Deferred to v1.1

Fine-tuning is not required for v1 — the prompt-engineered Qwen3.5-4B base model produces competent drafts without it. A QLoRA adapter (trained on ADS grey literature corpus) would improve terminology precision and prose register, but:

1. **It's a quality polish, not a functional requirement** — the pipeline works fine without it
2. **Training takes calendar time** — even on free GPU resources, it's a multi-week background task
3. **Better to ship v1 first**, get real user feedback, and let actual usage guide the training corpus priorities

When the time comes, the free training paths are documented below.

### Training Data Sources

| **Source** | **Volume** | **Content** | **Licensing** | **Access Method** |
| - | - | - | - | - |
| Archaeology Data Service (ADS/OASIS) | ~50,000 reports | UK grey literature — evaluations, excavations, watching briefs, building recordings | CC-BY 4.0 or ADS Terms of Use | OASIS API / batch CSV exports of signed-off reports |
| tDAR (The Digital Archaeological Record) | ~20,000 reports | US compliance reports — Section 106, NRHP evaluations, CRM | Permissive (authenticated API access) | tDAR API with authentication |
| Open Context | ~2.4M item records | Structured linked-data records with narrative annotations | Open (FAIR-compliant) | Open Context REST API |

### Corpus Pipeline

1. **PDF extraction via Docling** (IBM, MIT license) — layout-aware multimodal extraction preserving table/header structure, avoids heuristic coordinate scraping failures of pdfplumber/Camelot
2. **Geoprivacy redaction** — NER + regex masking of OS Grid References (TQ 12345 67890 → `[NGR]`), GPS coordinates, excavator names, and client PII
3. **Synthetic pair generation** — this step is the most computationally intensive part of corpus preparation. Free/zero-cost options:
   - **Self-hosted approach**: The largest model that fits on the RTX 3060 12GB (e.g. Qwen3.5-4B in think mode with careful prompt engineering) can approximate the reverse-engineering task, though quality will be lower than a frontier model
   - **Kaggle/Colab**: A 70B+ model can be run via free GPU allocations for batch processing
   - **Simpler fallback**: Skip synthetic pair generation entirely. Use a simpler instruction format where the PDF-extracted text (context sheets, finds tables) is the input and the human-written report section is the target output. This requires less preprocessing and no frontier model
   - The simplest approach is adequate for v1.0
4. **Filtering** — discard documents with >5% non-dictionary character rate (OCR corruption) or broken table structures

### Evaluation Framework (Held-out test set: 500 reports)

1. **Stratigraphic logic** — automated directed-graph verification: extracted context relationships must form a valid DAG respecting Harris Matrix laws
2. **Terminological precision** — output scanned against ROMFA scale, Munsell schema, standard sedimentological glossary
3. **Hallucination rate** — LLM-as-a-judge cross-reference of generated draft against input data; zero factual hallucination tolerance
4. **Compliance pass-through** — Phase 4 schema validation must pass with <5 placeholders

### Why Not Fine-Tune Phase 4?

Compliance templates are bureaucratic documents subject to frequent legislative revisions. Baking template structures into model weights guarantees rapid obsolescence. Phase 4 remains **prompt-engineered + RAG** (see Phase 4 section), using a lightweight vector store of the latest PDF guidelines injected at inference time. This hybrid architecture — fine-tune for enduring scientific mastery (Phase 3), RAG for transient rules-based compliance (Phase 4) — is the most resilient strategy.

## **Context Assembly Strategy**

Before calling the model, the orchestrator assembles a single context document from all Phase 1-2 outputs. This is passed as the user message alongside a system prompt containing the jurisdiction template schema.

| \# Context document assembly order (Python pseudocode) context = \[\] context.append(load\_template\_schema(jurisdiction))   \# ~500 tokens context.append(site\_metadata\_block())                \# project, grid ref, HER ref, etc. context.append(render\_context\_sheet\_summary())       \# all ctx JSON → condensed table context.append(render\_harris\_relationships())        \# stratigraphic matrix summary context.append(render\_finds\_summary())               \# finds catalogue by period/type context.append(render\_sample\_results())              \# dating, environmental, specialist context.append(render\_photo\_captions())              \# photo JSON summaries context.append(render\_previous\_text())               \# any pre-existing typed notes \# Typical total: 15,000–80,000 tokens; 262k limit handles all but the largest multi-season sites |
| - |


## **Thinking Mode — What It Does**

When Thinking Mode is active, Qwen3-4B-Thinking-2507 produces a hidden reasoning chain before generating the output draft. The orchestrator should capture and log this chain to logs/phase3\_reasoning.txt — it is extremely useful for the site director to understand how the model interpreted ambiguous stratigraphic relationships or conflicting dating evidence. The reasoning chain is not included in the draft itself.

## **Draft Structure (Output)**

The model is instructed to produce each report section as a separate Markdown code block labelled with the section ID from the jurisdiction template. This allows the orchestrator to parse individual sections for independent compliance checking in Phase 4.

| \`\`\`section:executive\_summary \#\# Executive Summary An archaeological evaluation was undertaken at... \`\`\`  \`\`\`section:methodology \#\# Methodology ... \`\`\`  \`\`\`section:results\_prehistoric \#\# Results: Prehistoric Activity ... \`\`\` |
| - |


## **Human Review Triggers — Phase 3**

The orchestrator flags sections for human review if any of the following conditions are met:

- The model's reasoning chain contains phrases indicating uncertainty (e.g. 'insufficient data', 'conflicting evidence', 'cannot determine').

- A context sheet referenced in the draft was flagged REVIEW\_REQUIRED in Phase 1.

- The draft references a context number that does not appear in the digitised record.

- Fewer than 3 dated finds or samples are available to support a stated period attribution.

- The draft proposes a phasing sequence that contradicts the Harris Matrix stratigraphic relationships.


## **Phase 3 VRAM Budget**

| **Component** | **VRAM** | **Notes** |
| - | - | - |
| Qwen3.5-4B base (Q4\_K\_M GGUF) | ~2.8 GB | Gated DeltaNet + sparse MoE; 4B effective parameters |
| LoRA adapter (r=32, all linear layers) | ~0.1 GB | Loaded alongside base via llama.cpp `--lora-scaled` |
| KV cache (65k token context) | +~1.9 GB | Total ~4.8 GB — comfortable within 6 GB |
| KV cache (85k token context) | +~2.5 GB | Total ~5.4 GB — within 6 GB, ~0.6 GB headroom |
| KV cache (262k token context) | +~3.4 GB | Total ~6.3 GB — exceeds limit; use chunk-and-merge above ~85k tokens |


| **⚠  RISK** | For very large multi-season sites with \> 500 context sheets, the assembled context may approach or exceed the GPU's available KV cache space. In this case: (1) use chunk-and-merge drafting (draft by period, then merge), or (2) offload KV cache layers to CPU RAM using llama.cpp's --n-gpu-layers flag to balance load. |
| :-: | - |




| **PHASE** **4** | **Compliance Refinement** *Ensure the draft conforms to the specific structure, terminology, and conventions of the target jurisdiction* |
| :-: | - |


## **Overview**

Phase 4 takes the structured draft from Phase 3 and runs it through a compliance pass. Unlike Phase 3, **Phase 4 is NOT fine-tuned** — compliance templates change too frequently for weight-based adaptation. Instead, it uses a **RAG-augmented prompt engineering** approach:

1. A lightweight vector store (`sentence-transformers` + `chromadb` or FAISS, CPU-based) holds the LATEST jurisdiction PDF guidelines and template mandates
2. The current template's schema and rules are retrieved at inference time and injected into the model's context
3. Gemma 4-E2B operates in a constrained editing mode: restructure, relabel, and fill missing mandatory fields — NEVER add interpretive content

This hybrid architecture ensures that if Historic England updates its CL3 standard in 2027, HOARD only needs a new PDF in the vector store — no retraining required.

## **Jurisdiction Template Engine**

The compliance engine is driven by a **dual-layer template system** — content templates (processed in Phase 4) and layout templates (processed in Phase 5). This bifurcation is critical: content changes (e.g., a new mandatory section) only update the JSON Schema; layout changes (e.g., font or margin updates) only update the docxtpl/CSS.

### Content Templates (JSON Schema)

Each jurisdiction is represented by a version-controlled directory containing a `schema.json` file defining the report's ontology. This schema validates the presence and data types of required sections and metadata fields. Phase 4 validates the draft against this schema before Phase 5 is permitted to execute.

### Layout Templates (docxtpl Word + CSS)

These govern visual presentation: margins, typography, pagination rules, title page branding, and header/footer configurations. See Phase 5 for full details.

### Template Resolution Algorithm

```
1. Exact match: templates/{jurisdiction}/{version}/
2. Regional base: templates/{region}/base/
3. Global default: templates/default/
```

### Version Management

Each template carries `valid_from` and `valid_until` dates (SemVer). When a template expires, the orchestrator injects a deprecation watermark into the draft DOCX. As of May 2026, the following templates are maintained:

- `historic_england_cl3` — v2025.3 (environmental archaeology update, Dec 2025)
- `historic_england_cl4` — v2025.3 (same environmental update)
- `netherlands_kna` — v2026.1 (KNA 5.0 Leidraad renewal, Mar 2026)
- `canada_ontario` — v2026.1 (ERO 026-0216 Stage 4 exact phrasing, Mar 2026)
- `us_ca_dpr_523` — v1995 (California DPR 523 series; planned for Phase 2 expansion)

### Community Contribution Workflow

New jurisdictions can be contributed as a package containing:
1. `schema.json` — content rules (JSON Schema)
2. `template.docx` — Word layout with Jinja2 tags
3. `style.css` — WeasyPrint PDF layout
4. `metadata.yml` — jurisdiction name, version, contributor details

## **Compliance Model Configuration**

| **Parameter** | **Value** |
| - | - |
| Model | unsloth/gemma-4-E2B-it-GGUF (Q4\_K\_M, same llama.cpp instance as Phase 2) |
| VRAM footprint | ~2.1 GB |
| Temperature | 0.1 — near-deterministic editing |
| RAG backend | `sentence-transformers/all-MiniLM-L6-v2` + chromadb (CPU, \< 1 GB RAM) |
| Retrieval strategy | Top-k (=3) guideline chunks injected into system prompt before each section edit |
| System prompt | Specifies jurisdiction schema + retrieved RAG chunks; instructs model to output ONLY the corrected section |
| Processing mode | Section-by-section (not whole draft at once) — reduces context and improves precision |
| Hallucination guard | Model is explicitly forbidden from adding factual claims not present in the Phase 3 draft |
| Update mechanism | New guidelines → add PDF to `rag_guidelines/{jurisdiction}/` → re-index vector store — no model changes |


## **Compliance Checks Performed**

- All mandatory sections present and non-empty.

- All required fields within each section are addressed (model flags missing ones with \[MISSING: field\_name\] placeholder).

- Executive summary word count within template limit.

- Prohibited terms replaced with jurisdiction-appropriate alternatives.

- Heading capitalisation style corrected.

- Figure captions reformatted to template standard.

- Section ordering matches template sequence.

- Context numbers formatted consistently (e.g., square brackets, leading zeros).


| **ℹ  NOTE** | The compliance pass does NOT perform factual review — it cannot know if a context sheet interpretation is archaeologically sound. Its job is structural and stylistic conformity only. The site director must review the draft for factual accuracy before submission. |
| :-: | - |




| **PHASE** **5** | **Assembly & Export** *Compile the refined report with figures, specialist appendices, and metadata into final publication-ready deliverables* |
| :-: | - |


## **Overview**

Phase 5 is entirely rule-based / deterministic — no LLM inference, zero hallucination risk. It bridges the gap between structured Markdown (Phase 4 output) and the three final deliverables required by commercial archaeology: an editable DOCX draft for PI review, an HTML preview for rapid checking, and a strictly compliant PDF/A-2b archival document for ADS/OASIS deposition.

The architecture is a **hybrid Markdown → python-docx + WeasyPrint pipeline**, cleanly decoupling content parsing, word processing synthesis, and archival rendering into distinct operational layers. Dependencies: `pyyaml`, `python-docx`, `weasyprint`, `rectpack`, `pillow`.

## **Pipeline Architecture**

| **Stage** | **Technology** | **Python Dep** | **Output** |
| - | - | - | - |
| Frontmatter extraction | YAML parsing | pyyaml | Global context dict (site code, HER refs, author metadata) |
| HTML preview | Pandoc | pypandoc | Semantic HTML5 + basic CSS |
| DOCX (editable draft) | python-docx heading styles + tables | python-docx | Formatted .docx with cover page, sections, appendices inline images |
| PDF/A-2b (archival) | HTML/CSS → PDF | weasyprint | ISO 32000-1 compliant, fonts subsetted, sRGB colours, Dublin Core XMP |
| Digital signatures (opt.) | PAdES injection | pyHanko | Offline PAdES-B/LTV cryptographic signatures |
| Data archive | ZIP | Python zipfile | All JSON, Markdown, assets, logs |

## **Frontmatter to Document Property Mapping**

| **YAML Field** | **DOCX Property** | **PDF/A XMP (Dublin Core)** | **Fallback** |
| - | - | - | - |
| title | Title (Built-in) | dc:title | "HOARD-Generated Archaeological Report" |
| author | Author (Built-in) | dc:creator | "HOARD Automated System" |
| site\_code | Custom: SiteCode | dc:subject | Extracted from input filename |
| her\_number | Custom: HER\_ID | dc:identifier | null |
| oasis\_id | Custom: OASIS | dc:identifier | null |
| accession\_number | Custom: Accession | dc:identifier | null |
| date | CreateDate (Built-in) | dc:date | System time at execution |

## **Specialist Appendix Generation**

One of the most complex and legally sensitive aspects of grey literature production. The strategy uses **deterministic NLG** (not LLM) for all quantitative content, reserving LLM interpretation only for qualitative synthesis.

### Tiered Approach (CIfA Toolkit for Specialist Reporting)

| **Tier** | **Content** | **Generation Method** | **Hallucination Risk** |
| - | - | - | - |
| **Type 1 (Description)** | Basic quantification: count, weight, EVE, MNI, NISP | Deterministic Jinja2 templates from pandas aggregates | **Zero** — no LLM involved |
| **Type 2 (Appraisal)** | Preservation assessment + research potential evaluation | Hybrid: deterministic metrics + LLM interpretation of significance | Low — LLM constrained by structured prompts |
| **Type 3 (Full Analysis)** | Deep interpretation integrated with site phasing | Prompt-engineered Phase 3 model with pre-aggregated statistics | Medium — human review required |

### Specialist Data Models (pandas DataFrames)

| **Specialism** | **Primary Metrics** | **Morphological Fields** | **Taphonomic** |
| - | - | - | - |
| **Pottery** | Count, Weight, EVE, MNI | Fabric, form, rim diameter, decoration, ware type | Abrasion, burning, residue |
| **Animal Bone** | NISP, MNE | Taxon, element, side, age/fusion, butchery | Gnawing, weathering, fragmentation |
| **Lithics** | Count, Weight | Raw material, technology, tool type, retouch type | Patination, edge damage, burning |
| **Environmental** | Sample vol, flot vol, seed count, charcoal wt | Species list, preservation, mineral replacement | Bioturbation, root disturbance |

### Prose Generation — Type 1 Example

```jinja2
The pottery assemblage comprised **{{ total_count }}** sherds weighing **{{ total_weight_kg }} kg**,
with an EVE of **{{ total_eve }}**. The fabric was predominantly **{{ dominant_fabric.name }}**
({{ dominant_fabric.percentage }}%), with minor {{ minor_fabrics|join(", ") }}.
```

This is mathematically guaranteed to match the appendix data tables exactly — zero hallucination risk.

## **Figure & Plate Auto-Layout**

### Photo Plates — Bin Packing (rectpack)

Artifact photographs and section photos are packed into A4/US Letter plates using the `rectpack` library (2D knapsack / bin-packing heuristic). Images are pre-scaled to consistent DPI by Phase 2. The algorithm outputs optimal (x,y) coordinates for each image within the page bounds, with configurable margins for captions.

### Harris Matrix — Graphviz (ortho layout)

Stratigraphic relationships from Phase 1 context JSON are parsed into a Directed Acyclic Graph (DAG) via the Graphviz DOT language. The `ortho` layout attribute forces orthogonal polyline edges, mirroring the conventional rectilinear structure of published Harris Matrices. Output: SVG for embedding.

### Specialist Charts — matplotlib

- **Pollen diagrams**: `matplotlib` + `psy-strat` extension for multi-axis stratigraphic representations
- **Faunal NISP charts**: bar/column charts from pandas aggregates
- **Pottery fabric chronotype graphs**: stacked bar charts by phase

### Resolution Management

| **Profile** | **DPI** | **Compression** | **Used For** |
| - | - | - | - |
| Web preview | 150 DPI | JPEG quality 60 | Quick browser check |
| Draft DOCX | 150 DPI | JPEG quality 60 | PI review |
| Archival PDF/A | 300 DPI | Lossless PNG or JPEG quality 95 | ADS/OASIS deposition |

## **PDF/A-2b Compliance**

The target archival format is **PDF/A-2b** (ISO 32000-1), selected over PDF/A-1b for its superior handling of transparent image elements and smaller file sizes. Generated via WeasyPrint single-pass rendering:

| **Requirement** | **WeasyPrint Configuration** | **Verification** |
| - | - | - |
| Variant | `pdf_variant="pdf/a-2b"` | Automatic |
| Font embedding | HarfBuzz hb-subset (embedded + subsetted) | Automatic |
| Colour space | `--srgb` flag (sRGB profile bound) | Automatic |
| Forbidden elements | JavaScript, audio, video, external links stripped pre-render | Custom pre-processor |
| XMP metadata | Dublin Core via custom HTML meta tags → `--custom-metadata` | Exiftool verification |

### Metadata Standard

Metadata explicitly aligns with **MIDAS Heritage** — the UK standard for heritage asset information. PDF XMP dictionaries contain: `dc:title`, `dc:creator`, `dc:subject` (site code + period), `dc:identifier` (HER/OASIS numbers), `dc:date` (deposition date).

### File Size Management

| **Constraint** | **Limit** | **Strategy** |
| - | - | - |
| ACHP e-filing (US) | 20 MB | Recursive DPI step-down + JPEG quality reduction if exceeded |
| ADS standard deposit | 50 MB | Self-optimising loop: step down until under limit, then verify PDF/A-2b compliance |
| OASIS upload | ~30 MB typical | Standard profile (300 DPI → 150 DPI if needed) |

## **Digital Signatures (Optional)**

PAdES (PDF Advanced Electronic Signatures) via `pyHanko` for jurisdictions requiring cryptographic authentication. Supports:
- **PAdES-B**: Baseline signature (visible or invisible)
- **PAdES-LTV**: Long Term Validation (includes revocation data for future verification)
- Local cryptographic keys only — no external validation services required

## **Performance & Scale**

| **Metric** | **50-page report** | **200-page report (e.g. HS2/Crossrail)** |
| - | - | - |
| WeasyPrint RAM | ~0.8 GB | ~2.6 GB |
| Mitigation | Default | HTML minification + disk caching + chapter-level parallel generation via docxcompose |
| Generation time (DOCX) | ~30s | ~2 min (parallel) |
| Generation time (PDF/A) | ~45s | ~3 min |
| Output file size (PDF) | ~8-15 MB | ~30-60 MB (before DPI step-down) |

## **Deliverables**

| **Output** | **Format** | **Tool** | **Purpose** |
| - | - | - | - |
| Editable draft | DOCX | python-docx | Principal Investigator review and editing |
| Archival report | PDF/A-2b | weasyprint | ADS/OASIS permanent deposition |
| Signed report (opt.) | PDF + PAdES | pyHanko | Regulatory submission (US SHPO, planning authorities) |
| Data archive | ZIP | Python zipfile | All intermediate data for reproducibility |
| Submission package | ZIP + metadata CSV | Custom | OASIS-ready bundle with enforced filename conventions |



# **Command-Line Interface Design**

The pipeline is invoked via a single entry-point script. All configuration is handled via a project config file or CLI flags. The interface is designed to be usable by a non-developer site director.


| \# Initialise a new project erd init --name 'Stoneyfield Farm 2026' --jurisdiction historic\_england\_cl3  \# Run the full pipeline erd run --input ./field\_records/ --project stoneyfield\_2026  \# Run a single phase (useful for re-running after manual corrections) erd run --project stoneyfield\_2026 --phase 3  \# Run from phase 3 onward (e.g. after editing digitised JSON) erd run --project stoneyfield\_2026 --from-phase 3  \# Open the review dashboard (flags items needing human input) erd review --project stoneyfield\_2026  \# Export final report erd export --project stoneyfield\_2026 --format docx,pdf  \# List available jurisdiction templates erd templates list |
| - |


## **Review Dashboard**

The erd review command opens a simple terminal-based (or optional browser-based) review interface. It presents each flagged item — a low-confidence OCR field, a missing mandatory section, a geometry review trigger — one at a time and allows the user to: accept the AI value, type a correction, or mark as 'to revisit'. Confirmed values are written back to the relevant JSON file and the pipeline state is updated. The user can then re-run from the relevant phase.



# **Error Handling & Fallback Strategy**

| **Error Condition** | **Detection Point** | **Behaviour** |
| - | - | - |
| Input file corrupt / unreadable | Phase 0 triage | Skip file, log warning, continue; halt if mandatory file missing |
| OCR confidence below threshold | Phase 1 model output | Flag field REVIEW\_REQUIRED; use best guess as placeholder |
| CadQuery execution failure | Phase 2 sandbox | Flag GEOMETRY\_FAIL; skip geometry for that drawing; report proceeds without it |
| Gemma grounding confidence \< 0.6 | Phase 2 output | Flag photo as LOW\_CONFIDENCE; caption still included but marked |
| Qwen context exceeds KV cache | Phase 3 pre-flight | Switch to chunk-and-merge drafting automatically; log warning |
| Phase 3 draft missing mandatory section | Phase 4 compliance check | Insert \[MISSING: section\_id\] placeholder; flag for human completion |
| Prohibited term not removable in context | Phase 4 compliance | Flag for human review rather than force-replace |
| WeasyPrint PDF/A compliance failure | Phase 5 | Fall back to PDF (non-archival) + log compliance warnings; retain HTML + DOCX |
| WeasyPrint OOM on large report | Phase 5 | Auto-enable disk caching + chapter-level parallel generation; if still OOM, split into volume I/II |
| docxtpl template Jinja2 syntax error | Phase 5 | Log template error with line number; fall back to generic template |
| rectpack bin-packing failure | Phase 5 | Skip plate auto-layout; embed figures sequentially at full-page width |
| pyHanko signature key missing | Phase 5 | Skip signing; produce unsigned PDF; log notification |
| VRAM OOM at any phase | CUDA exception | Catch exception; log; reduce batch size by 50% and retry; if still fails, switch to CPU |



# **Testing Strategy**

## **Unit Tests**

- Phase 0: manifest generation correctness; quality flag logic on synthetic images of known blur/skew.

- Phase 1: OCR output schema validation; checkbox boolean correctness on synthetic forms with known answers.

- Phase 2: CadQuery script executability rate on test drawing set; caption JSON schema validity.

- Phase 3: Section label extraction correctness; context reference completeness (all contexts in data appear in draft).

- Phase 4: Mandatory field presence after compliance pass; prohibited term absence.

- Phase 5: DOCX export opens without error; PDF generates correctly; ZIP completeness.


## **Integration Test Dataset**

A reference dataset of 3 fully processed past excavations (with known-good published reports) should be assembled for integration testing. The pipeline output is evaluated against the published report on: context sheet capture rate, period identification accuracy, and prohibited term rate. These metrics are reported in the test log.


## **Acceptance Criteria**

| **Metric** | **Target** |
| - | - |
| Context sheet field capture rate (vs manual) | \> 90% of fields correctly extracted |
| Period identification match (vs published report) | \> 85% agreement |
| Mandatory section completeness (post Phase 4) | 100% (placeholders acceptable) |
| Prohibited term rate in final output | 0% |
| VRAM peak across all phases | \< 5.5 GB (leaving 0.5 GB OS headroom) |
| Full pipeline runtime (typical 50-context evaluation) | \< 25 minutes on target hardware |



# **Known Limitations & Risks**

| **Limitation** | **Impact** | **Mitigation** |
| - | - | - |
| Fine-tuned Qwen3.5-4B may overfit to UK grey lit corpus | Medium — US/European phrasing may be less fluent | Training corpus includes tDAR (US) and Open Context (global) data; domain randomisation during synthetic pair generation |
| Geoprivacy breach via model memorisation | Critical — model could memorise site coordinates from training data | Multi-layered redaction (regex + NER) on corpus; adversarial probing post-training; input spatial data masked at inference |
| PDF/A WeasyPrint memory for 200+ page reports | Medium — ~2.6 GB RAM | HTML minification + SSD disk caching + chapter-level parallel generation |
| K-V cache OOM on very large sites (500+ contexts) | Medium — may exceed 6 GB VRAM | Chunk-and-merge drafting (process by period, then assemble); KV cache offload to CPU via --n-gpu-layers |
| Chandra OCR 2 accuracy on pre-1800 manuscripts | Medium — degraded scripts may underperform | Alternative pipeline path using specialised HTR fine-tunes (trocr-medieval-base, historical-swe) for legacy archives |
| Non-English context sheets | Medium — HTR model may underperform | Language detection in Phase 0; alternative extraction models for French, German, Italian |
| Specialist finds (numismatics, archaeometallurgy) | Medium — Phase 3 model may lack specialist knowledge | Flag for specialist review; system prompt lists specialist categories as human-gated |
| Jurisdiction template expiry | Low — standards change periodically | Template versioning with validity epochs; deprecation watermark on expired templates |



# **Full Dependency List**

| **Package / Model** | **Version / Source** | **Purpose** | **Licence** |
| - | - | - | - |
| Python | 3.12+ | Orchestrator runtime | PSF |
| llama.cpp (server) | Latest | Qwen, Gemma inference + LoRA adapter hot-swapping | MIT |
| **Phase 1 — Digitisation** | | | |
| | | | |
| GLM-OCR | Ollama (zai-org/GLM-OCR) | Handwritten context sheet extraction — Multi-Token Prediction | MIT / Apache 2.0 |
| Granite-Docling-258M | HuggingFace (ibm-granite/granite-docling-258M) | Layout-aware table parsing — replaces MinerU | Apache 2.0 |
| Docling | Latest pip (docling-project) | Document conversion framework — PDF/DOCX/TXT/HTML parsing | MIT |
| Qwen3-VL-4B | Ollama (qwen3-vl:4b) | Fallback for degraded documents | Apache 2.0 |
| opencv-python | Latest pip | CPU image pre-processing (CLAHE, deskew, adaptive threshold) | Apache 2.0 |
| pydantic | Latest pip | Structured output schema enforcement | MIT |
| **Phase 2 — Spatial** | | | |
| Florence-2-large | HuggingFace (microsoft/Florence-2-large) | Visual grounding / bounding box extraction | MIT |
| Qwen3-VL-4B-Instruct | HuggingFace (Qwen/Qwen3-VL-4B-Instruct) | Photo captioning + cross-check (262K context) | Apache 2.0 |
| Build123d | Latest pip | Optional parametric 3D geometry | Apache 2.0 |
| **Phase 3 — Synthesis (fine-tuned)** | | | |
| Qwen3.5-4B (base) | HuggingFace (Qwen/Qwen3.5-4B) | Base model for QLoRA fine-tuning | Apache 2.0 |
| LoRA adapter (Phase 3) | Distributed as .gguf adapter (~100 MB) | Domain-adapted archaeological prose weights | Apache 2.0 |
| Unsloth | Latest pip | QLoRA fine-tuning framework (training only) | Apache 2.0 |
| **Phase 4 — Compliance (RAG)** | | | |
| Gemma 4-E2B | HuggingFace (google/gemma-4-E2B) | Section-by-section compliance editing | Apache 2.0 |
| chromadb | Latest pip | Lightweight vector store for guideline RAG | Apache 2.0 |
| sentence-transformers | 3.x | Embedding for RAG retrieval + ARK header mapping (CPU) | Apache 2.0 |
| **Phase 5 — Assembly & Export** | | | |
| python-docx | Latest pip | DOCX generation with heading styles, tables, images | MIT |
| weasyprint | 68.1+ | Markdown→HTML→PDF/A-2b archival rendering | BSD |
| rectpack | Latest pip | 2D bin-packing for photo/artefact plates | MIT |
| Pillow / Wand | Latest pip | Image dimension queries + normalisation | HPND / ImageMagick |
| pyHanko | Latest pip | Optional offline PAdES digital signatures (v1.1) | MIT |
| docxcompose | Latest pip | Optional multi-chapter DOCX merging (v1.1) | MIT |
| markdown | Latest pip | Markdown→HTML conversion for PDF rendering | BSD |
| **Shared / Infrastructure** | | | |
| OpenCV | 4.x | Quality triage (Phase 0) | Apache 2.0 |
| pandas | 2.x | CSV/XLSX parsing, specialist data aggregation | BSD |
| PyYAML | Latest pip | Jurisdiction template parsing | MIT |
| pytest | Latest pip | Test suite | MIT |



# **Open Questions for v2.1**

- Should the review dashboard be terminal-only (rich/textual) or offer an optional lightweight web UI (FastAPI + HTMX)? The web UI option is more accessible for non-technical site directors but adds a dependency.

- What is the minimum hardware specification for the CPU-only fallback path? An M-series Mac (unified memory) handles the full pipeline well. A CPU-only x86 path is possible but Phase 3 inference time will be 10-20x longer.

- ~~Should the pipeline support ARK system as a direct data input?~~ ✅ **Implemented.** ARK import module (`src/erd/ark/`) supports CSV/JSON exports with semantic header mapping. Phases 0 and 1 are bypassed automatically.

- Qwen3.5-4B in Thinking Mode produces a reasoning chain of 1,000–3,000 tokens before the draft. Should this be presented to the site director as a 'confidence log', or silently discarded after logging? User research needed.

- ~~Phase 3 fine-tuning strategy~~ — ✅ **Researched.** QLoRA on Qwen3.5-4B via Unsloth; 60-80 GPU-hours on RTX 4090; training corpus = ADS + tDAR + Open Context.

- ~~Phase 5 document generation architecture~~ — ✅ **Researched.** Hybrid docxtpl (DOCX) + WeasyPrint (PDF/A-2b) + rectpack/Graphviz (figures) + pyHanko (signatures).

- ~~**Fine-tuning GPU concern**~~ — The research note about cloud GPU cost ($30-40) was based on rented RTX 4090 pricing. **This cost is avoidable through several free routes:**

   1. **Kaggle free tier** — 30 hrs/week of P100 16GB or T4 GPU, zero cost. QLoRA on Qwen3.5-4B completes within 2-3 weeks of free quota. This is the primary recommendation.
   2. **Local RTX 3060 12GB** — The target inference GPU can also train, just 3-5x slower (200-400 hours instead of 60-80). Zero cost. Leave it running over a weekend or two. Unsloth's Triton kernel optimisations make this feasible.
   3. **Google Colab free** — T4 GPU (~15 GB usable VRAM). 2-hour session timeout but training state can be saved and resumed. Free.
   4. **Hugging Face community sharing** — Once one person has run the training (via any of the above zero-cost routes), the resulting ~100 MB LoRA adapter can be uploaded to Hugging Face for every HOARD user to download directly. The training cost is a ONE-TIME burden, not per-user. This is the model HOARD should adopt: the developer runs training once via Kaggle/Colab/local, distributes the adapter freely, and each user downloads the small file with no GPU-time cost.

   **For v1, fine-tuning is optional.** The base Qwen3.5-4B with a well-crafted system prompt produces excellent drafts. Fine-tuning is a v1.1 quality enhancement, not a v1 blocker. The pipeline works either way — the Phase 3 orchestrator simply loads the GGUF base model if no LoRA adapter is present, and loads base+adapter if one is found.

