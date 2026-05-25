---
mode: subagent
---

<!-- SPDX-License-Identifier: MIT -->
<!-- SPDX-FileCopyrightText: 2025-2026 Marcus Quinn -->
# TODO

Project task tracking with time estimates, dependencies, and TOON-enhanced parsing.

## Backlog (still valid)

- [ ] t015 Implement chunk-and-merge fallback for large sites (>500 contexts) @hoard #phase3 ~2h risk:med logged:2026-05-11
- [ ] t024 Assemble integration test dataset (3 past excavations with known reports) @hoard #testing ~3h risk:low logged:2026-05-11
- [ ] t030 Benchmark full pipeline runtime against 6 GB VRAM target @hoard #testing ~2h risk:low logged:2026-05-11

## Superseded (replaced during development)

- [-] t001 Evaluate & select TrOCR variant for handwritten text recognition @hoard #phase1 superseded-by:GLM-OCR ~2h logged:2026-05-11
- [-] t002 Integrate HTRflow page segmenter with TrOCR pipeline @hoard #phase1 superseded-by:GLM-OCR ~3h logged:2026-05-11
- [-] t003 Set up Chandra OCR 2 (4-bit GGUF) for form/checkbox extraction @hoard #phase1 superseded-by:GLM-OCR ~2h logged:2026-05-11
- [-] t004 Set up MinerU2.5-Pro for complex table parsing @hoard #phase1 superseded-by:Granite-Docling-258M ~2h logged:2026-05-11
- [-] t005 Set up PaddleOCR-VL-1.5 for distortion correction pre-processor @hoard #phase1 superseded-by:OpenCV ~1h logged:2026-05-11
- [-] t008 Set up Gemma 4-E2B (Q4_K_M) for photo captioning & visual grounding @hoard #phase2 superseded-by:Qwen3-VL-8B/GLM-OCR ~2h logged:2026-05-11
- [-] t009 Set up Zero-To-CAD (ADSKAILab/Zero-To-CAD-Qwen3-VL-2B) for sketch-to-CAD @hoard #phase2 superseded-by:SVG-Qwen3-VL ~2h logged:2026-05-11
- [-] t012 Set up llama.cpp server mode for Qwen3.5-4B inference @hoard #phase3 superseded-by:Ollama ~2h logged:2026-05-11

## Done

- [x] t006 Implement Phase 1 model routing logic (type + quality → model dispatch) ~3h actual:3h logged:2026-05-11 completed:2026-05-25
- [x] t010 Implement Phase 2 orchestration ~3h actual:3h logged:2026-05-11 completed:2026-05-25
- [x] t013 Implement Phase 3 context assembly (manifest → structured prompt) ~3h actual:3h logged:2026-05-11 completed:2026-05-25
- [x] t014 Implement Thinking Mode reasoning capture + logging ~1h actual:1h logged:2026-05-11 completed:2026-05-25
- [x] t016 Implement Phase 3 human review triggers ~2h actual:2h logged:2026-05-11 completed:2026-05-25
- [x] t018 Implement Phase 4 compliance model runner (Gemma 4-E2B, section-by-section) ~2h actual:2h logged:2026-05-11 completed:2026-05-25
- [x] t019 Implement compliance checks: mandatory sections, prohibited terms, heading style ~3h actual:3h logged:2026-05-11 completed:2026-05-25
- [x] t021 Terminal review dashboard (Rich TUI, accept/edit/defer) ~4h actual:4h logged:2026-05-11 completed:2026-05-13
- [x] t022 Flag review workflow (accept/correct/defer per item) ~3h actual:3h logged:2026-05-11 completed:2026-05-13
- [x] t023 Review dashboard tests (12 tests, 305 lines) ~2h actual:2h logged:2026-05-11 completed:2026-05-13
- [x] t025 Harris Matrix SVG generation (pure-Python, no graphviz) ~2h actual:2h logged:2026-05-11 completed:2026-05-13
- [x] t026 Add ARK system direct data input (bypass Phase 1 OCR for digital-first sites) ~4h actual:4h logged:2026-05-11 completed:2026-05-25
- [x] t027 PyPI publish workflow (GitHub Actions release -> PyPI) ~2h actual:1h logged:2026-05-11 completed:2026-05-13
- [x] t028 User guide (CLI reference + pipeline walkthrough, 591 lines) ~3h actual:3h logged:2026-05-11 completed:2026-05-13
- [x] t029 CONTRIBUTING.md with development setup guide ~1h actual:1h logged:2026-05-13 completed:2026-05-13
- [x] t031 Phase 0: Ingestion & Triage (rule-based, no GPU) ~8h actual:8h logged:2026-05-09 completed:2026-05-09
- [x] t032 Phase 5: Assembly & Export (rule-based, no GPU) ~6h actual:6h logged:2026-05-09 completed:2026-05-09
- [x] t033 Template engine with 14 jurisdiction templates ~4h actual:4h logged:2026-05-09 completed:2026-05-09
- [x] t034 GitHub Actions CI workflow (lint + test + type-check) ~1h actual:1h logged:2026-05-11 completed:2026-05-11
- [x] t035 GitHub repo migration + remote setup ~1h actual:1h logged:2026-05-11 completed:2026-05-11
- [x] t036 Phase 1: GLM-OCR + Docling + Qwen3-VL fallback ~6h actual:6h logged:2026-05-25 completed:2026-05-25
- [x] t037 Phase 2: Qwen3-VL-8B/GLM-OCR spatial reconstruction ~4h actual:4h logged:2026-05-25 completed:2026-05-25
- [x] t038 Phase 3: Qwen3.5-4B synthesis & drafting ~4h actual:4h logged:2026-05-25 completed:2026-05-25
- [x] t039 Phase 4: Gemma 4-E2B compliance refinement ~3h actual:3h logged:2026-05-25 completed:2026-05-25
- [x] t040 Phase 5: python-docx DOCX + WeasyPrint PDF/A-2b + rectpack photo plates ~4h actual:4h logged:2026-05-25 completed:2026-05-25
- [x] t041 Checkbox post-processing for GLM-OCR output ~30m actual:30m logged:2026-05-25 completed:2026-05-25
- [x] t042 SVG geometry from field section drawings ~2h actual:2h logged:2026-05-25 completed:2026-05-25
- [x] t043 End-to-end pipeline test with mock data ~2h actual:2h logged:2026-05-25 completed:2026-05-25
- [x] t007 Write Phase 1 unit tests (synthetic forms, known answers) ~2h actual:2h logged:2026-05-11 completed:2026-05-25
- [x] t011 Write Phase 2 unit tests ~2h actual:2h logged:2026-05-11 completed:2026-05-25
- [x] t017 Write Phase 3 unit tests ~2h actual:2h logged:2026-05-11 completed:2026-05-25
- [x] t020 Write Phase 4 unit tests ~2h actual:2h logged:2026-05-11 completed:2026-05-25

## Dependencies

- t007 blocked-by t006 (Done)
- t011 blocked-by t010 (Done)
- t015 blocked-by t013 (Done)
- t017 blocked-by t013 (Done)
- t019 blocked-by t018 (Done)
- t020 blocked-by t019 (Done)
- t024 blocked-by t007 (Done)
- t024 blocked-by t011 (Done)
- t024 blocked-by t017 (Done)
- t024 blocked-by t020 (Done)