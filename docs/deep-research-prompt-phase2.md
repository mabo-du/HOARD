# HOARD — Deep Research Prompt: Phase 2 Spatial Reconstruction

## Project Context (for the AI researcher)

**HOARD** (Heritage Observation And Report Drafter) is a fully local, multi-stage AI pipeline that converts archaeological field data into near-publication-ready grey literature reports. The pipeline targets **6 GB VRAM consumer GPUs** (e.g. NVIDIA RTX 3060 12 GB, RTX 4060 8 GB). It runs entirely on-device with zero API calls.

Phase 2 handles **spatial reconstruction** — translating site photographs, section drawings, and plans into structured visual evidence and parametric geometry. It has two sub-tasks:

### 2a — Photo Captioning & Visual Grounding
Archaeological site photographs need structured captions describing what is visible, spatial relationships, and scale references. Additionally, the model must perform visual grounding — identifying and labelling stratigraphic features (context boundaries, cuts, fills), scale rods, and north arrows in section drawings and plans.

### 2b — Sketch-to-CAD Geometry
Field section drawings and plans (hand-drawn on permatrace or gridded paper) need to be converted into parametric CAD geometry (CadQuery Python scripts) for inclusion in the digital archive.

### Current Model Selections (from design doc, unverified)

| Sub-task | Current Design | VRAM (est.) |
|----------|---------------|-------------|
| 2a: Photo captioning + visual grounding | `unsloth/gemma-4-E2B-it-GGUF` (4B, Q4_K_M) | ~2.1 GB |
| 2b: Sketch-to-CAD | `ADSKAILab/Zero-To-CAD-Qwen3-VL-2B` (2B) | ~1.6 GB |
| **Total peak** | Sequential (not simultaneous) | **~2.1 GB** |

### What's Already Been Researched (from prior Deep Research report)

The earlier report confirmed:
- Phase 1: Chandra OCR 2 replaces TrOCR+HTRflow. MinerU2.5-Pro-2604-1.2B for tables. PaddleOCR-VL-1.5 for distortion correction.
- Phase 3: Qwen3-4B-Thinking-2507 for synthesis/drafting (262K context, ~2.6 GB at Q4_K_M).
- Phase 4: Gemma 4-E2B for compliance refinement.
- General: Speculative decoding wastes VRAM; prompt caching recommended.

Phase 2 was **not investigated** in that report.

---

## Research Questions

### Q2a: Photo Capturing & Visual Grounding for Archaeology

**Photo captioning:**
- Is `unsloth/gemma-4-E2B-it-GGUF` still the best open-weight VLM for generating structured archaeological photo captions within 6 GB VRAM?
- Are there newer smaller VLMs (2B–7B) released since January 2026 that outperform Gemma 4-E2B on dense image description tasks?
- How does `Qwen3-VL-4B` (if it exists) or `Qwen2.5-VL-4B` compare for this use case?
- What about `microsoft/Florence-2` (0.2B/0.7B) for lighter-weight captioning? Could a two-stage approach (Florence-2 for draft caption + Qwen3-4B for refinement) fit in 6 GB?

**Visual grounding (feature labelling in drawings):**
- Can Gemma 4-E2B accurately identify and label stratigraphic features (context boundaries, cuts, fills) in section drawings?
- Are there specialised models for archaeological/scientific drawing understanding?
- What about YOLO26 for bounding box detection + a VLM for label assignment?
- How does the grounded output need to look? Bounding box coordinates + label + confidence score per feature.

**Cross-check with context sheet data:**
- An important HOARD feature: the captioning model should compare its visual interpretation against the context sheet descriptions and flag inconsistencies (e.g., photo shows a stone wall but context sheet says "layer"). Can any current VLM do this reliably in a single pass?

### Q2b: Sketch-to-CAD Geometry

- Is `ADSKAILab/Zero-To-CAD-Qwen3-VL-2B` still the leading open-weight model for converting hand-drawn sketches to parametric CAD?
- Are there newer alternatives (released 2025–2026) that are better at handling schematic archaeological section drawings? These differ from engineering sketches — they often lack precise measurements, use symbolic conventions (hachures for cuts, stippling for fills), and are drawn at inconsistent scales.
- Could a non-CAD approach work better for archaeology — e.g., output SVG vector graphics instead of CadQuery Python scripts?
- What about `TRELLIS.2-4B` (on the user's curated model list) — is this relevant for 3D reconstruction from drawings?

**Validation/sandboxing:**
- The design doc specifies running generated CadQuery in a sandbox to catch execution errors. Is there a better validation approach?
- What's the current state of CadQuery compatibility with Python 3.11+?
- Are there lighter-weight alternatives to CadQuery for parametric geometry that would be easier to sandbox?

### Q2c: VRAM and Sequential Loading for Phase 2

- Both Phase 2 models (Gemma 4-E2B at ~2.1 GB and Zero-To-CAD at ~1.6 GB) load sequentially. Combined with Phase 3's Qwen3-4B at ~2.6 GB and Phase 4's Gemma again at ~2.1 GB — is there a smarter loading strategy?
- Could the same Gemma 4-E2B instance be kept loaded across Phase 2 and Phase 4 (with different system prompts) to avoid reloading?
- What's the overhead of switching between models in llama.cpp server mode vs. loading/unloading programmatically?

### Q2d: Benchmarks and Evaluation

- Are there any benchmarks specifically for archaeological or heritage image understanding?
- What metrics should HOARD use to evaluate Phase 2 output quality (caption accuracy, grounding precision, geometry executability)?
- Is there a published dataset of archaeological site photographs with ground-truth captions and feature annotations?

---

## Output Preferences

Please provide:
- Specific HuggingFace model URLs
- Version numbers and release dates
- Approximate VRAM usage figures where known
- Your confidence level for each recommendation (high/medium/low)
- Any GitHub repos or papers for significant findings
