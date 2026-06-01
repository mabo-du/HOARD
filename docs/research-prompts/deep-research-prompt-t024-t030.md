# HOARD — Deep Research Prompt: Integration Test Dataset & VRAM Benchmarking

## Project Context (for the AI researcher)

**HOARD** (Heritage Observation And Report Drafter) is a fully local, multi-stage AI pipeline that converts archaeological field data into near-publication-ready grey literature reports. The pipeline targets 6-8 GB VRAM consumer GPUs (RTX 3060 12GB, RTX 3070 Laptop 8GB). All five phases are now implemented and tested with synthetic mock data.

## Research Question 1: Sourcing 3 Integration Test Datasets

We need 3 real archaeological excavation datasets, each containing raw field data AND the corresponding published grey literature report. These will be used to validate that the HOARD pipeline produces archaeologically sound output against known-good human-authored reports.

### Requirements per dataset

Each dataset should include:

**Input (raw field records):**
- Scanned context sheets (handwritten or typed forms with stratigraphic units, descriptions, interpretations)
- Finds catalogue or register
- Site photographs (at least 2-3 showing features/contexts in situ)
- At least 1 section drawing or plan (hand-drawn or CAD)
- Total: ideally 20-50 contexts for meaningful pipeline testing

**Output (known-good report):**
- The published grey literature report (PDF) covering the same excavation
- Preferably conforms to a known jurisdiction standard (Historic England CL3, Section 106, etc.)

### Dataset sourcing priorities

| Source | Repository | What to Look For | Access |
|--------|-----------|-----------------|--------|
| ADS (Archaeology Data Service) | `archaeologydataservice.ac.uk/archsearch/` | UK evaluations/excavations with full digital archives — context sheets, matrices, photos | Open / CC-BY |
| tDAR (The Digital Archaeological Record) | `core.tdar.org` | US CRM compliance reports — Section 106, NRHP evaluations | Registration required |
| Open Context | `opencontext.org` | Structured linked-data records, often with narrative annotations | Open |
| DANS (Data Archiving and Networked Services) | `easy.dans.knaw.nl` | Dutch archaeological datasets — KNA-compliant | Open |

### Specific research questions

1. **Are there any well-known benchmark datasets in computational archaeology?** The field often tests against known corpora — is there a "standard test suite" of 3-5 excavations with paired raw data + published reports?

2. **What's the best strategy for finding matched input/output pairs?** Many repositories have PDFs of final reports but NOT the raw context sheets. Conversely, digital archives have context sheets but the PDF report is behind a paywall or in a separate repository. Which specific excavations have BOTH?

3. **Are there curated datasets on Hugging Face?** Search for:
   - Any datasets tagged `archaeology`, `heritage`, `excavation`, `grey literature`
   - Any from institutions like Historic England, Archaeology Data Service, tDAR
   - Any domain-specific benchmarks for archaeological NLP/vision tasks

4. **Licensing constraints**: The datasets must be usable in an open-source pipeline. CC-BY, CC0, or ADS Terms of Use (which allow reuse for research) are acceptable. Avoid paywalled/commercial-only datasets.

5. **What's the minimum viable dataset?** If full matched datasets are hard to find, are there partial datasets that could work? E.g., context sheets from one excavation + a published report from a different but similar site?

### Output format

Please provide for each dataset:
- Source repository URL
- Excavation/site name and ID
- What files/records are available (context sheets, finds, photos, report PDF)
- Licensing terms
- Direct download links or access instructions
- Number of contexts and approximate scope
- Whether the published report is available alongside

---

## Research Question 2: VRAM Benchmark Methodology

We need a reproducible method to benchmark HOARD's peak VRAM usage across all pipeline phases on consumer hardware with 8 GB VRAM.

### Hardware

- **GPU**: NVIDIA RTX 3070 Laptop GPU (8 GB VRAM)
- **CPU**: AMD Ryzen 5800H
- **RAM**: 32 GB DDR4
- **OS**: Ubuntu 26.04 LTS
- **Inference**: Ollama (localhost:11434)
- **Models (all Ollama)**: GLM-OCR 2.2GB, Qwen3-VL-8B 6.1GB, Qwen3.5-4B 2.8GB, Gemma 4-E2B 3.0GB

### Research Questions

1. **What's the authoritative tool for VRAM monitoring on Linux?**
   - `nvidia-smi` — how to poll programmatically (Python subprocess or nvidia-ml-py)?
   - Are there Python libraries specifically designed for GPU memory profiling during ML inference?
   - What about `nvitop`, `gpustat`, or `py3nvml`?

2. **Is there a standardised benchmarking framework for Ollama inference?**
   - How does Ollama's `eval_count` and `eval_duration` map to VRAM usage?
   - Can Ollama's API return memory stats? (Check `/api/ps` or similar endpoints)
   - Are there existing benchmarks for Qwen3.5-4B, Qwen3-VL-8B, GLM-OCR, and Gemma 4-E2B on constrained hardware?

3. **What metrics should we track?**
   - Peak VRAM (maximum observed during phase)
   - Sustained VRAM (during active inference)
   - Model load time (cold start vs warm cache)
   - Inference time per image/context
   - KV cache growth with context length
   - GPU temperature / power draw (optional — for mobile/thermal throttling awareness)

4. **How do we measure per-phase vs cumulative?**
   - Sequential measurement: run each phase independently, record peak VRAM
   - Cumulative measurement: run phases back-to-back, record total peak
   - Idle baseline: VRAM usage with no models loaded
   - Are there known benchmarks for similar multi-model pipelines?

5. **What's a realistic test workload?**
   - Synthetic data of varying sizes (10, 50, 100, 500 contexts)
   - How does VRAM scale with context count?
   - Does image resolution affect VL model VRAM usage?

6. **Tooling recommendations** — please provide:
   - Specific Python libraries and code snippets for programmatic VRAM monitoring
   - Shell one-liners for ad-hoc monitoring during runs
   - Any existing benchmark scripts or testing frameworks that could be adapted
   - Output format recommendations (CSV? JSON? Grafana dashboard?)

---

## Output Preferences

Please provide:
- Specific URLs to datasets, repositories, and tools
- Code snippets where relevant (Python, shell)
- Confidence level (high/medium/low) for each recommendation
- Any caveats about licensing, data quality, or hardware limitations
- Format findings as clearly numbered answers matching the Q1/Q2 structure above
