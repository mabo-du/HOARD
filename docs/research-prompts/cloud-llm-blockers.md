# HOARD — Deep Research Prompt: Cloud LLM Support, Blockers & Extraction Strategy

## Project Context (for the AI researcher)

**HOARD** (Heritage Observation And Report Drafter) is a multi-stage AI pipeline that converts archaeological field data — handwritten context sheets, finds catalogues, site photographs, section drawings, and sample results — into a near-publication-ready grey literature report conforming to the relevant heritage authority standard.

The pipeline was originally designed for **fully local operation on consumer GPUs** (NVIDIA RTX 3070 Laptop, 8 GB VRAM, Ryzen 5800H, 32 GB RAM). All inference runs via Ollama. Zero API calls, no data leaves the machine.

### Shift: Cloud LLM Support

The user's current position: **local-only is too restrictive.** Archaeologists are not always at the dig site. They may be in a café, at home, at a university, or in a museum — without access to a GPU. HOARD should support cloud LLM APIs alongside local Ollama, with the user choosing per session (or per phase).

Phases and current model assignments:

| Phase | Name | Current (Local) | GPU? |
|-------|------|-----------------|------|
| 0 | Ingestion & Triage | Python/PyMuPDF, file-type detection | No |
| **1** | **Multi-Modal Digitisation** | **GLM-OCR (Ollama)** + schema validation | **Yes** |
| 2 | Spatial Reconstruction | Qwen3-VL-8B (Ollama) — photo captioning | Yes |
| 3 | Synthesis & Drafting | huihui_ai/qwen3.5-abliterated:4B (Ollama) | Yes |
| 4 | Compliance Refinement | tripolskypetr/gemma4-uncensored-aggressive (Ollama) | Yes |
| 5 | Assembly & Export | python-docx, WeasyPrint, pyHanko, TEI-XML | No |

### Blockers (from the session history)

1. **NuExtract3 not available on Ollama** — no GGUF quant published. Was identified as ideal for structured field extraction from OCR output, but cannot run without deploying vLLM or other infrastructure.
2. **ADS (Archaeology Data Service) grey lit report download** — ADS blocks automated tools (403 on report URLs). Cannot source real PDFs for E2E testing without a manual browser download workflow.
3. **StratiGraph GitLab push required SSH** — resolved (switched to HTTPS with credential helper). Not a blocker, but notes that GitLab SSH key management is fragile across repos.

### What Already Exists

- **Full pipeline** working end-to-end with Ollama models on Pinn Brook test dataset (50 context sheet PNGs)
- **~330 tests passing** across Phases 0–5 + StratiGraph integration
- **Schema contract** for Phase 1 output JSON (defined and validated)
- **StratiGraph HOARD JSON import** built and integrated
- **Existing deep research prompts** covering Phase 1 (model selection), Phase 2 (spatial reconstruction), and general pipeline optimisation (see `docs/deep-research-prompt*.md`)
- **`docs/nuextract3-evaluation.md`** — evaluation of NuExtract3 specifically
- **`docs/florence2-compatibility.md`** — Florence-2 for Phase 2 photo captioning

---

## Research Sections

### 1. Cloud LLM Provider Architecture

Investigate the architectural options for adding cloud API support alongside local Ollama.

**Key questions:**
- How should the abstraction layer work? A `ModelProvider` interface with `LocalOllamaProvider` and `CloudAPIProvider` implementations?
- Which cloud providers should be supported (priority order)?
  - OpenAI (GPT-4o, GPT-4o-mini) — vision + structured output
  - Anthropic (Claude 3.5 Sonnet, Claude 3 Opus) — vision + structured output
  - Google (Gemini 2.5 Pro/Flash) — vision + structured output
  - AWS Bedrock — for enterprise/government archaeological units
  - Azure OpenAI — for UK/EU government clients
- What fallback logic makes sense? (If cloud API fails → local model, or if cloud rate-limited → queue and retry)
- How to handle multimodal/vision for cloud? Different providers have different image handling (OpenAI base64, Anthropic base64, Google inline data or GCS URI)
- How does structured output/schema enforcement differ across providers?
  - OpenAI `response_format` / `json_schema`
  - Anthropic `tool_use` with `input_schema`
  - Google `response_mime_type` + `response_schema`
  - Gemini API `responseSchema`
- What about streaming? Phases 3 and 4 benefit from streaming for progressive output display.

**Deliverables:**
- Provider comparison table (pricing per 1K tokens, image pricing, context windows, structured output quality, rate limits)
- Cost estimate: what does it cost to run each phase via each provider for a typical 50-context-sheet site?
- Recommended architecture: class hierarchy, config schema (YAML/TOML), environment variable conventions
- Privacy notes: which phase data is most sensitive (site locations, landowner names → Phase 1 forms contain these)

### 2. Phase 1 Cloud Alternatives to GLM-OCR

GLM-OCR works locally but is slow and sometimes misses square-bracket context numbers. Investigate whether cloud vision models are better for Phase 1 structured form extraction.

**Key questions:**
- How well does GPT-4o extract handwritten context numbers, checkbox states, and stratigraphic matrices from scanned context sheets?
- How does Claude 3.5 Sonnet compare for this task?
- Gemini 2.5 Pro/Flash — Google's OCR heritage (Document AI) — could this be best-in-class for form extraction?
- Does structured output (`response_format` / `tool_use` / `response_schema`) give significantly better reliability than unstructured prompting for Phase 1 JSON output?
- Is there a hybrid approach: cloud for OCR/vision, local for synthesis? (Phases 3–4 are less visually demanding and run fine on 4B models locally)
- What about using Google Document AI or Azure Document Intelligence (form recogniser) as an alternative *service* rather than a general LLM?

**Deliverables:**
- Provider-by-capability matrix (handwriting OCR, checkbox detection, matrix diagram extraction, table parsing, structured JSON output)
- Recommended provider for Phase 1 primary extraction
- Cost per context sheet for each provider
- Hybrid architecture recommendation (which phases go cloud, which stay local)

### 3. NuExtract3 Alternatives & Structured Extraction Strategy

NuExtract3 (`numind/NuExtract3`) was identified as ideal for schema-constrained structured extraction from Phase 1 OCR text, but it is unavailable on Ollama (no GGUF). Three paths forward.

**Key questions:**

**Path A: Deploy NuExtract3 via vLLM**
- What VRAM does vLLM serving NuExtract3 require (FP16, 4-bit, 8-bit)?
- Can it share GPU with other pipeline phases or needs dedicated allocation?
- What is the startup overhead of vLLM vs. Ollama?
- Is there an Ollama-compatible alternative quantisation? (ExLlamaV2, llama.cpp, etc.)

**Path B: Alternative structured extraction models on Ollama**
- Are there GGUF-quantised structured extraction models?
- Can GLM-OCR itself be prompted to output structured JSON directly (skip the NuExtract3 step)?
- `GLiNER` / `GLiREL` for structured field extraction? (Small model, fast, but less powerful)
- Can Qwen3-VL-8B (already running locally) handle structured output alongside vision? (Multimodal model with function calling?)
- Any new small models (≤4B params, GGUF available) purpose-built for information extraction?

**Path C: Prompt-based extraction with the synthesis model**
- Can Phase 3 (qwen3.5-abliterated:4B) handle the structured extraction task as a pre-processing step within its context window?
- Would a small fine-tune (LoRA on Qwen2.5-3B or similar) give better structured extraction than prompting?
- What about using the cloud API *just* for extraction while keeping phases 3–4 local?

**Deliverables:**
- Decision matrix: vLLM vs alternative model vs prompt-based vs cloud-only extraction
- VRAM estimates for each approach
- Integration effort estimate (code changes required)
- Recommended path with fallback strategy

### 4. Archaeology Data Service — Automated Grey Lit Access

ADS blocks automated downloads (403 on PDF URLs). Users must manually find and download grey lit reports via browser. This is a blocker for automated E2E testing with real-world data.

**Key questions:**
- What legal/technical alternatives exist for sourcing open-access archaeological reports?
  - OAS (Online Access to the Index of archaeological investigations / Grey Literature Library) — does it have an API?
  - CORE aggregator (core.ac.uk) — does it index archaeological grey lit?
  - OpenAlex — as a source for archaeological thesis/report DOIs?
  - Local HER (Historic Environment Record) APIs — do any offer public downloads?
- For ADS specifically: what is their robots.txt / API policy? Is there a proper API key system for academic users?
- What about the Archaeology Data Service's own OAI-PMH endpoint?
  - ADS OAI-PMH base URL: `https://archaeologydataservice.ac.uk/oai-pmh/`
  - Could we harvest metadata and offer a browser-opens-a-tab workflow?
- What is the legal status of downloading grey lit reports for local processing? (These are published documents, not restricted data — the 403 may be bot protection, not content restriction)
- For the Gallows Hill E2E test plan specifically: is there an already-open PDF on ADS that can be linked to and downloaded straightforwardly?
- Are there other open repositories of archaeological grey literature?
  - OpenGrey (discontinued?)
  - DANS EASY / NARCIS (Netherlands)
  - HAL (France)
  - Zenodo — archaeology communities?
  - local authority HER portals with public access

**Deliverables:**
- Identification of OAI-PMH endpoints and any REST APIs for grey lit discovery
- Recommended approach: automated metadata harvest + browser-open-download workflow for PDF bodies
- List of 3–5 open-access grey lit reports that can be downloaded without authentication (URLs)
- Legality note: automated access vs. fair use for research data extraction

### 5. Cost Analysis: Local GPU vs. Cloud API

Help the user decide when to use local vs. cloud, based on real cost data.

**Key questions:**
- Electricity cost of running local RTX 3070 (laptop) for one full pipeline run (~3–4 hours)?
  - RTX 3070 laptop TDP: ~80–130W under load
  - CPU + system: ~50W
  - Local electricity rate (UK, ~£0.25/kWh)
- Cloud API cost per full pipeline run for each provider (Phase 1–4, one provider):
  - Token counts per phase (estimate from current runs)
  - Image token costs (PDF page as image)
- Break-even point: at what volume does a cloud API subscription become cheaper than running local hardware?
  - If the user processes 1 site/month vs 10 sites/month
  - If the user already has the GPU (sunk cost) vs needs to buy one
- What about latent hardware costs? (GPU wear, thermal cycles, electricity at peak vs off-peak)
- Cloud cost saving from caching/retrying? (Local models never return the same output twice — cloud APIs have deterministic structured output settings)

**Deliverables:**
- Cost table: per-phase + total for local (electricity) vs. each cloud provider
- Recommendation: which phases to run where (cost-optimal)
- Break-even analysis at different volumes

### 6. Phase 2 & 3 Cloud Alternatives for Visual/Spatial Tasks

The existing Phase 2 uses Qwen3-VL-8B locally for photo captioning. Phase 3 uses qwen3.5-abliterated:4B for synthesis. Research cloud alternatives.

**Key questions:**
- What cloud multimodal models excel at archaeological photo captioning? (site shots, section photos, finds photos)
- Can GPT-4o or Claude describe stratigraphy from a section photo? (Colour changes, inclusion types, boundary clarity)
- For synthesis (Phase 3): which cloud model handles 50K+ token contexts best for weaving together context sheet data into a narrative?
  - Gemini 2.5 Pro (1M+ context)
  - Claude 3.5 Sonnet (200K)
  - GPT-4o (128K)
- Are there archaeology-specific fine-tuned models on HuggingFace for report generation?
- What about RAG with vector store for Phase 3? Could a retrieval approach supplement the context-limited local model?

**Deliverables:**
- Cloud model recommendations for Phase 2 and Phase 3
- Context window comparison and impact on synthesis quality
- Cost per photo / per report

### 7. Open-Access Archaeological Dataset Landscape

Beyond ADS, what open datasets exist for HOARD research and testing?

**Key questions:**
- Open-access archaeological datasets on HuggingFace?
- Zenodo archaeology communities — any with downloadable grey lit?
- National Heritage List for England (NHLE) API — does it offer downloadable reports?
- OAS grey lit library — direct URL patterns?
- What about museum/open data GIS datasets for UK archaeology?
- Are there any OCR-annotated archaeological form datasets? (Could be used for fine-tuning or benchmarking)

**Deliverables:**
- Curated list of open-access sources with URLs and access methods
- Estimate of how many documents each source provides
- Any licensing restrictions
