# HOARD — Deep Research Prompts (Batch 3)
### Covering implementation gaps for GPU-dependent Phases 1–4

**Prepared:** 2026-05-20  
**Follows:** `docs/deep-research-prompt.md` (Batch 1: Q1–Q4) and `docs/deep-research-prompt-phase2.md` (Batch 2: Q2a–Q2d)

---

## Design document correction — action required before Phase 2 coding begins

`HOARD_Technical_Design_v2.md` was updated on 13 May 2026 to reflect Batch 1 research, but Phase 2 still lists:

> "Primary Model(s): Zero-To-CAD + Gemma 4-E2B"

The Batch 2 research report explicitly ruled both of these out:
- **Zero-To-CAD:** trained on 3D mechanical multi-views, will catastrophically hallucinate on 2D archaeological sketches. Do not use.
- **Gemma 4-E2B for Phase 2 captioning:** replaced by Qwen3-VL-4B-Instruct + Florence-2-large (two-stage grounding pipeline).

The correct Phase 2 specification is:
- 2a Photo captioning + visual grounding: **Florence-2-large (771M)** for initial bounding box grounding → **Qwen3-VL-4B-Instruct** (~2.9 GB at Q4_K_M) for semantic synthesis + cross-check against context sheet text
- 2b Sketch geometry: **SVG vectorization** (primary); **Build123d** Python scripts (if parametric geometry required) — NOT CadQuery, NOT Zero-To-CAD
- Runtime: **llama.cpp router mode** (`--models-max 1`) for all GPU-dependent phases

Update the design doc to reflect these decisions before Phase 2 coding begins.

---

## Prompt H1 — Phase 1 Python Implementation: Chandra OCR 2, MinerU, PaddleOCR

> I am implementing Phase 1 of the HOARD pipeline — a fully local archaeological document digitisation system targeting 6 GB VRAM. Phase 1 has already been researched and the following models have been selected:
>
> - **PaddleOCR-VL-1.5** (0.9B) — distortion correction / de-warping pre-processor
> - **MinerU2.5-Pro-2604-1.2B** — table and structured data extraction
> - **datalab-to/chandra-ocr-2** (4B) — holistic layout, handwriting, and checkbox extraction
>
> These three models run **sequentially** within a 6 GB VRAM budget. The pipeline is a Python CLI tool (`erd` command). No R, no rpy2 — pure Python.
>
> I need to know exactly how to load, call, and correctly unload each model in Python.
>
> **Please investigate each model in detail:**
>
> ### Chandra OCR 2 (`datalab-to/chandra-ocr-2`)
>
> - Is Chandra OCR 2 available as a standard HuggingFace `transformers` model (i.e., loadable via `AutoModelForVision2Seq` or `AutoModel`), or does it require a custom library?
> - Is it available in GGUF format for llama.cpp, or only as HuggingFace weights?
> - What is the correct Python call pattern? Provide a complete, runnable Python function that:
>   1. Loads the model from HuggingFace or GGUF
>   2. Accepts a PIL Image or file path as input
>   3. Runs inference and returns structured Markdown or JSON output
>   4. Cleanly unloads the model and clears CUDA cache after use
> - What is the exact output format — does it return raw Markdown, HTML, or a structured JSON with bounding boxes and text blocks?
> - Are there any known issues with calling it from Python on Linux with CUDA 12.x?
>
> ### MinerU2.5-Pro-2604-1.2B (`opendatalab/MinerU2.5-Pro-2604-1.2B`)
>
> - Is MinerU2.5-Pro callable as a standalone Python library, or is it only available as a CLI tool or Docker image?
> - If a Python library: what is the correct import and call pattern? Provide a complete Python function that:
>   1. Loads the model
>   2. Accepts an image (PIL or path) containing a table
>   3. Returns extracted table data as a dict or DataFrame
>   4. Unloads the model cleanly
> - If only a CLI tool: how should the HOARD pipeline call it (subprocess? Docker?)
> - Are there known dependency conflicts with other packages in the Phase 1 pipeline?
>
> ### PaddleOCR-VL-1.5 (distortion correction)
>
> - Is PaddleOCR-VL-1.5 available via pip as `paddleocr` or via a different package?
> - What Python version and CUDA version is required?
> - Provide a complete Python function that:
>   1. Loads PaddleOCR-VL-1.5 in distortion-correction mode
>   2. Accepts a file path (JPG/PNG/PDF)
>   3. Returns a de-warped, de-skewed PIL Image
>   4. Releases GPU memory after processing
>
> ### VRAM clearing pattern
>
> - What is the correct Python pattern to completely clear VRAM between sequential model loads on CUDA, ensuring no fragmentation? (e.g., `del model`, `torch.cuda.empty_cache()`, `gc.collect()`, or something else?)
> - Is there a risk that torch's memory allocator retains cached blocks even after `empty_cache()` that would cause OOM on the next model load?
>
> ### Sequential loading manager
>
> - Provide a Python `PhaseOneManager` context manager class that handles the sequential loading and VRAM-clearing lifecycle for all three Phase 1 models, with logging of VRAM usage at each stage.
>
> Please provide working Python code examples, HuggingFace model card URLs, PyPI package names, and any known gotchas specific to these models on Ubuntu 24.04 + CUDA 12.x.

---

## Prompt H2 — llama.cpp Router Mode: Python CLI Integration for HOARD

> I am integrating llama.cpp's server router mode into a Python CLI tool called `erd` (the HOARD pipeline). Research has confirmed that the router mode (`--models-max 1`, LRU eviction) is the correct architecture for sequentially loading 4B VLMs within a 6 GB VRAM budget. I now need implementation details for integrating this into a Python CLI tool.
>
> **The HOARD pipeline architecture:**
> - Invoked via `erd run --project <id>` from the terminal
> - Each phase is a Python module that the CLI orchestrator calls in sequence
> - All GPU-dependent phases (1–4) will communicate with the llama.cpp server via its OpenAI-compatible API
> - The pipeline must work even if the user doesn't have llama.cpp pre-installed (or installed in a non-standard location)
>
> **Please investigate and provide:**
>
> ### llama.cpp installation and discovery
>
> - What is the recommended way to install llama.cpp for a Python project on Ubuntu 24 with CUDA? (pip install llama-cpp-python? Direct binary? Conda? Other?)
> - How should the HOARD CLI discover the `llama-server` binary — PATH lookup, bundled binary, or user-configured path in a config file?
> - What Python package wraps the llama.cpp server API most cleanly for making OpenAI-compatible calls? (`openai` Python client? `httpx`? `llama-cpp-python`?)
>
> ### Server startup and shutdown
>
> - Provide a Python `LlamaCppServer` class that:
>   1. Locates the `llama-server` binary
>   2. Starts it as a subprocess with router mode: `--models-dir ./hoard_models --models-max 1 --host 127.0.0.1 --port 8765`
>   3. Waits for the server to be ready (health check)
>   4. Shuts down cleanly when the pipeline completes (or crashes)
>   5. Handles the case where a server is already running (reuse vs. restart)
>
> ### Model directory structure
>
> - What format must the models be in for the router to discover them? (`.gguf` files in a flat directory? Named subdirectories?)
> - How should HOARD structure its `hoard_models/` directory?
> - How does the router assign model names for API calls — is it derived from the filename, or set via a config?
>
> ### Calling a specific model via the API
>
> - Provide a Python function that sends an inference request to the llama.cpp router specifying which model to use:
>   ```python
>   def call_llama_model(model_name: str, messages: list[dict], image_path: str | None = None) -> str:
>       ...
>   ```
> - How does the router handle model switching — does the caller need to wait for the swap, or does it happen transparently?
> - What is the correct API parameter for specifying the model name in the request?
>
> ### Vision models (multimodal)
>
> - Qwen3-VL-4B-Instruct and Chandra OCR 2 are both vision-language models that accept image inputs. Does llama.cpp's router mode support multimodal (image + text) requests via its OpenAI-compatible API?
> - If yes: what is the correct message format for sending an image alongside text?
> - If no: what fallback approach works for multimodal inference within the llama.cpp ecosystem?
>
> ### GGUF model download
>
> - For each model HOARD uses, what is the recommended GGUF quantization to download, and where (HuggingFace repo + filename)?
>   - Chandra OCR 2 (Q4_K_M preferred)
>   - Qwen3-VL-4B-Instruct (Q4_K_M)
>   - Qwen3-4B-Thinking-2507 (Q4_K_M)
>   - Gemma 4-E2B (Q4_K_M)
>   - Florence-2-large (does GGUF exist? if not, what's the alternative?)
>
> Please provide all Python code, CLI command examples, and links to relevant llama.cpp documentation.

---

## Prompt H3 — Phase 3 Prompt Engineering for Archaeological Grey Literature Drafting

> I am implementing Phase 3 of the HOARD pipeline. The model is **Qwen3-4B-Thinking-2507** (Q4_K_M, ~2.6 GB VRAM) running via llama.cpp server. Phase 3 accepts the Phase 2 outputs (context records, finds data, photo descriptions, spatial notes) and must produce a near-publication-ready Markdown draft of an archaeological grey literature report.
>
> **The context for a typical site:** A Phase 3 input will contain 50–500 digitised context records, each with: context number, type, description, interpretation, period, dimensions, and stratigraphic relationships. Plus finds catalogue entries, environmental sample records, and photo descriptions.
>
> **Please investigate:**
>
> ### System prompt architecture for grey literature drafting
>
> - What is the optimal system prompt structure for instructing a 4B SLM to produce a well-structured, formally written, Markdown grey literature report from an archaeological dataset?
> - The output must follow a specific section structure defined by the jurisdiction template (e.g., Executive Summary → Site Description → Methodology → Results → Stratigraphic Summary → Discussion → Conclusion → Bibliography format). How should the template structure be encoded in the system prompt?
> - How should the model be instructed to: (a) maintain formal academic register, (b) cite context numbers correctly (e.g., "Context 001 was a circular cut..."), (c) interpret stratigraphic relationships correctly (e.g., if A cuts B, then A is later than B)?
> - Should the "thinking" mode be forced on for all sections, or only for the Stratigraphic Summary and Discussion sections where reasoning depth matters most?
>
> ### Chunk-and-merge strategy for large sites (>500 contexts)
>
> - The model can support ~65,000–85,000 tokens at Q4_K_M with 6 GB VRAM. A large commercial excavation with 500+ contexts may exceed this limit. What is the correct chunk-and-merge strategy for producing a coherent report across multiple inference calls?
> - Specifically: how do you split the dataset across chunks without losing cross-chunk stratigraphic context (e.g., a context in chunk 2 cuts a context only mentioned in chunk 1)?
> - How do you merge the section drafts from multiple chunks into a coherent whole — does a final "merge pass" with a shorter prompt work, or is a different approach needed?
> - What context information (e.g., a summary of previous chunks) must be carried forward into each subsequent chunk?
>
> ### Prompt caching with llama.cpp
>
> - HOARD may make multiple sequential inference calls against the same static dataset (e.g., drafting different report sections separately). How does llama.cpp's KV cache work for prompt caching — does it cache the KV states of common prefixes automatically, or must you use a specific API parameter?
> - What prefix length is needed to benefit from caching — is there a minimum?
> - Provide a concrete example of how to structure the HOARD Phase 3 prompts to maximise prompt caching benefits (e.g., static system prompt → static context data → variable section instruction).
>
> ### Harris Matrix interpretation
>
> - The HOARD pipeline generates a Harris Matrix (stratigraphic sequence diagram) during Phase 5. Phase 3 needs to correctly interpret stratigraphic relationships from the context sheet data to produce accurate synthesis.
> - What prompt format best helps a 4B SLM reason correctly about stratigraphic superposition? (e.g., should relationships be expressed as a list of tuples, a matrix, or natural language?)
> - What are the most common stratigraphic reasoning errors made by SLMs on archaeological data, and how can the system prompt guard against them?
>
> ### Phase 3 output format
>
> - Should Phase 3 output a single Markdown document, or structured JSON with sections as keys and content as values?
> - What schema allows Phase 4 compliance refinement to efficiently locate and correct individual sections?
>
> Please provide complete example system prompts, prompt templates, and code snippets for the chunk-and-merge implementation.

---

## Prompt H4 — Phase 4 Compliance Checking: Converting YAML Templates to VLM Prompts

> I am implementing Phase 4 of the HOARD pipeline — compliance refinement. The model is **Gemma 4-E2B** (Q4_K_M, ~2.1 GB VRAM) running via llama.cpp server. Phase 4 takes the Phase 3 Markdown draft and restructures it to comply with a specific jurisdiction template defined as a YAML file.
>
> HOARD has 14 jurisdiction YAML templates, each defining:
> - **mandatory_sections**: sections that must be present (names and order)
> - **prohibited_terms**: terms/phrases that must not appear (jurisdiction-specific jargon)
> - **heading_style**: required heading capitalisation and format
> - **word_limits**: optional min/max word counts per section
> - **exact_phrases**: strings that must appear verbatim (e.g., Ontario's Stage 4 recommendation language)
>
> **Please investigate:**
>
> ### Compliance checking strategy
>
> - What is the most effective approach for using a 4B VLM to check compliance of a multi-page Markdown document against a set of YAML-defined rules?
> - Should compliance be checked section-by-section (one inference call per section) or in a single pass over the full document? What are the tradeoffs for a 6 GB VRAM constraint?
> - Provide a complete system prompt template that: (a) encodes the jurisdiction's rules, (b) instructs the model to check the provided section, (c) outputs a structured list of violations in JSON.
>
> ### Rule encoding approaches
>
> - **Mandatory sections:** How do you prompt the model to verify all required sections are present and in the correct order?
> - **Prohibited terms:** A purely programmatic `str.contains()` check can catch known prohibited terms without using the VLM at all. Is there any reason to use the VLM for this check, or should it be handled as a pre-processing rule?
> - **Exact phrases (Ontario Stage 4 language):** How do you instruct the VLM to insert a mandated verbatim phrase into the draft if it is missing, without changing surrounding text?
> - **Heading style checks:** Should heading normalisation (capitalisation, hierarchy) be handled by the VLM or by a post-processing regex?
>
> ### Hybrid approach: rule-based + VLM
>
> - The research report recommends a two-stage approach: programmatic checks first (fast, deterministic), then VLM for anything that requires semantic understanding. What tasks belong in each stage?
> - Provide an architecture for a `ComplianceEngine` class that:
>   1. Runs programmatic checks (section presence, prohibited terms, heading format, word counts)
>   2. Calls Gemma 4-E2B only for semantic checks (e.g., "does this executive summary accurately represent the site findings described in the results section?")
>   3. Returns a structured `ComplianceReport` with violation severity (blocking vs. advisory)
>
> ### Template YAML updates needed
>
> Based on the Batch 1 research findings, three jurisdictions have confirmed standard changes that require template updates:
>
> **England (Historic England MoRPHE CL3/CL4):**
> - Environmental Archaeology guidance updated December 2025
> - Waterlogged Wood guidance updated December 2025
> - Managing Archaeology in London (GLAAS) updated February 2026
>
> **Netherlands (KNA 5.0):**
> - KNA Leidraden for Coring and Trial Trenching renewed March 26, 2026
> - Shift from monolithic to modular report structure
>
> **Canada — Ontario (MCM Standards and Guidelines):**
> - ERO 026-0216 (March 6, 2026): exact verbatim Stage 4 recommendation language mandated
> - New 50m buffer requirement for partial clearance documentation
> - New site update form requirement after Stage 2 inspection
>
> For each of the three jurisdictions: what specific fields in the YAML template must be added, changed, or removed? Provide the exact before/after YAML diff for each.
>
> ### Confidence gating
>
> - Phase 4 should trigger a human review flag if the VLM's compliance confidence is below a threshold. How should confidence be measured for a compliance check task — is perplexity a valid signal, or is explicit JSON output with confidence scores the right approach?
>
> Please provide example YAML template structure, complete `ComplianceEngine` class skeleton, and example Phase 4 prompts.

---

## Prompt H5 — Integration Test Datasets and Report Quality Evaluation

> I am building the HOARD pipeline, a local AI tool that generates archaeological grey literature reports from field data. I need to:
>
> 1. Assemble an integration test dataset of 3 real excavations with both raw field data (input) and published grey literature reports (expected output), so that I can validate the full pipeline end-to-end.
> 2. Define automated quality metrics for evaluating the generated reports against the ground truth.
>
> **Please investigate:**
>
> ### Open archaeological datasets with both raw data and published reports
>
> - Are there any publicly available archaeological excavation datasets that include both:
>   (a) Raw field data (context sheets, finds catalogues, or structured databases), AND
>   (b) A published grey literature report derived from that data
>   — such that both inputs and expected output are accessible?
> - Specifically search for:
>   - UK: Archaeology Data Service (ADS, archaeologydataservice.org.uk) — do any deposits include raw context-level data alongside the published report?
>   - UK: Open Context (opencontext.org) — does it include raw context sheet data?
>   - US: tDAR (tdar.org) and Open Context US deposits
>   - Australia: AIATSIS or State Heritage Authority open data portals
>   - Open access excavation publications with supplementary raw datasets (Journal of Open Archaeology Data, Internet Archaeology)
> - Are there any test datasets specifically distributed with OCR or document processing tools for archaeological documents (e.g., datasets associated with HTRflow, Transkribus, or similar)?
>
> ### Synthetic test data generation
>
> - If no suitable open datasets exist, what is the recommended approach for generating synthetic but realistic test data? Are there any tools for generating synthetic archaeological context sheets and finds catalogues?
> - Are there templates or examples of blank but realistic context recording forms for the major jurisdictions (Historic England CL3, Cadw, Section 106) that could be used to create test data?
>
> ### Automated quality metrics for generated grey literature
>
> The generated report must be evaluated for:
> 1. **Content accuracy** — does the narrative correctly represent the input data?
> 2. **Compliance** — does the report follow the jurisdiction template?
> 3. **Writing quality** — is it formally written and free of hallucination?
>
> For each dimension, what automated metrics are appropriate?
> - For content accuracy: ROUGE-L, BERTScore, or something else? What are the limitations of ROUGE-L for this task?
> - For compliance: which checks can be rule-based (section presence, word counts, prohibited terms) vs. requiring semantic evaluation?
> - For hallucination detection: are there lightweight local models that detect hallucinated archaeological facts (e.g., a stated context relationship that contradicts the input data)?
> - Are there any published evaluation frameworks for AI-generated scientific or technical documents that would apply here?
>
> ### Practical test dataset assembly plan
>
> - Recommend 3 specific excavation datasets from the sources above (with URLs and access instructions) that would form a good integration test suite: one simple (small, well-documented site), one medium complexity, one large/complex.
> - For each: what preprocessing would be needed to convert the data into HOARD's input format?
>
> Please provide direct URLs, dataset names, licences, and any known access requirements (account, data agreement).

---

## Prompt H6 — HOARD Publication and Community Strategy

> I am building HOARD — an open-source (MIT) Python tool that converts archaeological field data into grey literature reports using local AI models. Once the pipeline is functional and validated, I intend to publish it to the academic community to give it credibility, community adoption, and a citable DOI.
>
> HOARD is distinct from most AI tools in that:
> - It targets a niche professional audience (commercial archaeologists, CRM firms, heritage consultants)
> - It runs fully offline (no cloud API calls, no data leaves the machine)
> - It addresses a genuine workflow problem in the heritage sector
> - It is free and MIT-licensed
>
> **Please investigate:**
>
> ### Academic journals for digital archaeology software tools
>
> - What peer-reviewed journals publish software tool papers in digital archaeology or computational heritage? For each journal, provide:
>   - Name, publisher, URL
>   - Specific article type for software/tool papers
>   - Word limits and format requirements
>   - Open access status and APC cost
>   - Approximate time to decision
>   - Impact factor or CiteScore
> - Specifically investigate:
>   - **Journal of Computer Applications in Archaeology (JCAA)** — does it publish software tool papers?
>   - **Internet Archaeology** — does it accept software tools?
>   - **Journal of Open Archaeology Data (JOAD)** — is it appropriate for tools as well as data?
>   - **Archaeological Prospection** — for tools with geospatial components
>   - **Journal of Open Source Software (JOSS)** — is HOARD eligible? What are the requirements?
>   - **Heritage Science** (Springer) — does it accept computational tool papers?
> - For the most suitable 2-3 options: find 2–3 exemplary tool papers from 2020–2026 with DOIs.
>
> ### JOSS eligibility assessment
>
> - HOARD is a Python CLI tool (pip-installable, MIT, CI tested, documented). Does it meet JOSS criteria?
> - What is the JOSS submission process specifically for a command-line AI pipeline tool?
> - What would a reviewer likely flag as weaknesses for a JOSS submission of this tool?
>
> ### Community channels for heritage sector software
>
> - What are the primary professional communities and channels where commercial archaeologists and heritage consultants discover new tools?
>   - CIfA (Chartered Institute for Archaeologists)
>   - BAJR (British Archaeological Jobs Resource)
>   - Heritage Gateway, ADS, or similar aggregators
>   - Social: LinkedIn groups, archaeology subreddits, email lists
> - Are there conferences where HOARD would be well-received? (CAA — Computer Applications in Archaeology; EAA — European Association of Archaeologists; SHA — Society for Historical Archaeology?)
> - Is there an open-source archaeology software ecosystem or directory where HOARD should be listed?
>
> ### Pilot partners
>
> - What types of organisations would make good pilot partners for HOARD?
> - Are there known CRM firms, university departments, or heritage NGOs that publicly engage with digital archaeology tools?
> - Are there grant programs (ARC, AHRC, Heritage Lottery Fund, or similar) that fund open-source heritage tools?
>
> ### Preprint strategy
>
> - Is EarthArXiv appropriate for a digital archaeology tool paper, or is there a better preprint server (SocArXiv, arXiv cs.AI, OSF Preprints)?
> - What is the standard preprint practice in the digital archaeology community?
>
> Please provide journal submission URLs, example tool paper DOIs, conference submission deadlines for 2026–2027, and community channel links.

---

*HOARD Deep Research Batch 3 — v1.0*  
*Prompts H1–H6 cover Phase 1–4 implementation gaps and post-launch strategy.*  
*Run after completing Batch 1 (Q1–Q4) and Batch 2 (Phase 2) research reports.*
