# **Architectural Transition and Optimization of the HOARD Archaeological Inference Pipeline**

The Heritage Observation And Report Drafter (HOARD) represents a critical advancement in the digitization, interpretation, and synthesis of archaeological field data. Historically reliant on localized processing via consumer-grade GPUs—specifically targeting architectures akin to the NVIDIA RTX 3070 mobile GPU with 8 GB of VRAM—the pipeline was engineered to ensure absolute data sovereignty and to eliminate variable Application Programming Interface (API) costs. However, this strict localization introduces substantial operational friction. Archaeological practitioners frequently operate in environments devoid of high-performance computing hardware, such as remote excavation sites, transit scenarios, or academic settings relying on standard enterprise laptops.  
The proposed architectural shift transitions HOARD from a strictly local application into a highly dynamic, hybrid infrastructure. This evolution necessitates the integration of cloud-based Large Language Models (LLMs) and specialized vision APIs alongside the existing Ollama-based local execution environment. This report exhaustively details the architectural modifications required to abstract model providers, evaluates cloud alternatives for multimodal extraction and narrative synthesis, resolves specific deployment blockers regarding specialized models and external data acquisition, and constructs a comprehensive economic model comparing local execution with cloud inference. The primary objective is to establish a resilient architecture that dynamically routes computational workloads based on hardware availability, fiscal constraints, and the specific cognitive demands of each archaeological data processing phase.

## **1\. Cloud Provider Architecture and Integration Framework**

Integrating cloud LLMs into a locally optimized pipeline necessitates a robust, fault-tolerant abstraction layer capable of standardizing inputs, outputs, and fallback protocols across highly disparate vendor ecosystems. The architecture must seamlessly handle the transition between locally hosted quantized models and enterprise-grade cloud endpoints without exposing the underlying API idiosyncrasies to the core HOARD pipeline logic.

### **The Abstraction Layer Design**

The system requires a polymorphic ModelProvider interface, establishing a unified contract for all generation and extraction requests. This interface must define standard asynchronous methods, notably extract\_structured\_data, describe\_spatial\_imagery, and generate\_narrative\_stream. The implementation hierarchy branches into a LocalOllamaProvider and multiple cloud-specific implementations, prioritizing OpenAIProvider, AnthropicProvider, and GoogleGeminiProvider based on their distinct multimodal capabilities.  
To decouple the pipeline from hardcoded vendor logic, the system must utilize a configuration-driven factory pattern. This pattern reads from a central YAML or TOML configuration file, which dictates the preferred provider per pipeline phase, subsequently overriding local execution when cloud infrastructure is enabled. An optimal YAML configuration structure would define environmental variable bindings (e.g., OPENAI\_API\_KEY, ANTHROPIC\_API\_KEY) and phase-specific routing rules, such as assigning Phase 1 extraction to Azure while routing Phase 3 synthesis to a local Qwen model.  
Furthermore, a circuit-breaker and fallback pattern is essential for enterprise reliability. The logic dictates that if a cloud provider experiences rate-limiting—such as an HTTP 429 Too Many Requests error—the pipeline queues the request employing an exponential backoff strategy.1 If the cloud failure persists beyond a predefined retry threshold, or if a network disconnection occurs, the system must seamlessly fail over to the LocalOllamaProvider. This guarantees that a resource-intensive pipeline run, which may have already processed dozens of context sheets, is not aborted mid-synthesis.

### **Provider Comparison and Architectural Capabilities**

The cloud ecosystem offers diverse capabilities, pricing models, and security guarantees that must be weighed against HOARD's specific operational requirements across its five primary phases.

| Provider / Model | Context Window | Input Cost ($/1M Tokens) | Output Cost ($/1M Tokens) | Vision Support | Native Structured Output Enforcement | Rate Limit Tiers (Entry) |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| OpenAI GPT-4o-mini | 128,000 | $0.150 | $0.600 | Yes | response\_format (JSON Schema) 2 | High (Usage based) |
| Anthropic Claude 3.5 Sonnet | 200,000 | $3.000 | $15.000 | Yes | tool\_use (Input Schema) 4 | Tiered based on pre-funding |
| Google Gemini 2.5 Pro | 1,000,000 | $1.250 | $10.000 | Yes | responseSchema 3 | 500 RPD (Free) / Usage (Paid) 6 |
| Google Gemini 2.5 Flash | 1,000,000 | $0.300 | $2.500 | Yes | responseSchema 3 | 500 RPD (Free) / Usage (Paid) 6 |
| Google Gemini 2.5 Flash-Lite | 1,000,000 | $0.100 | $0.400 | Yes | responseSchema 6 | Shared with Flash limit 6 |
| DeepSeek V3.2 | 64,000 | $0.280 | $0.420 | No | Standard JSON generation 7 | High availability |

#### **Resolving Multimodal Input Discrepancies**

A significant architectural hurdle is the disparate treatment of image payloads across cloud providers. For Phase 1 (digitization of handwritten context sheets) and Phase 2 (spatial reconstruction from trench and section photographs), image transmission formats vary significantly. OpenAI and Anthropic require images to be base64 encoded directly within the message payload, which can inflate local memory usage during request preparation.1 Conversely, Google's Gemini API accepts inline base64 data but heavily optimizes for images passed via Google Cloud Storage (GCS) URIs when dealing with bulk document processing.8 The ModelProvider abstraction must contain a serialization module that translates HOARD's internal image representation (e.g., standard PIL Image objects or local file paths) into the specific network payload required by the active provider, abstracting this complexity away from the core pipeline logic.

#### **Schema Enforcement and Structured Output Variations**

Phase 1 relies entirely on strict adherence to a predefined JSON schema representing the archaeological context sheet contract. The translation of this schema into API parameters exposes provider-specific quirks that the abstraction layer must normalize. OpenAI utilizes the response\_format parameter, providing the strongest server-side guarantees for exact schema adherence.3 Anthropic achieves schema enforcement by defining a pseudo-tool via tool\_use and its input\_schema. The pipeline must explicitly prompt the Claude model to "call the tool" and then parse the arguments returned as the structured JSON object.3  
Google Gemini utilizes responseSchema; however, Gemini's validation engine possesses strict, undocumented quirks. For example, it requires explicit type definitions for empty arrays, actively rejecting standard Pydantic-generated schemas like {"type": "array", "items": {}} in favor of explicitly typed items.1 The HOARD abstraction layer must seamlessly mutate standard JSON schemas before transmission to Google endpoints to prevent immediate API rejections.

#### **Streaming Implementations for Progressive Display**

For Phase 3 (Synthesis and Drafting) and Phase 4 (Compliance Refinement), the narrative generation can span thousands of tokens as it weaves individual context data into a cohesive site report. Streaming is vital for the user experience, preventing the interface from appearing frozen during long generations. The abstraction layer must expose asynchronous generators using Python's AsyncGenerator typing, allowing the user interface or terminal to print chunks progressively. While all major cloud Software Development Kits (SDKs) support asynchronous streaming, the abstraction must homogenize the distinct chunk objects returned by OpenAI, Anthropic, and Google into a single, standardized HOARDStreamToken class.

#### **Privacy and Data Sovereignty Configurations**

Archaeological field data frequently contains highly sensitive metadata. This includes precise spatial coordinates of vulnerable heritage assets subject to illicit nighthawking, private landowner names, and potentially sensitive osteological human remains records. Phase 1 processing of primary context sheets is the most sensitive stage, as the raw forms contain unredacted spatial data.  
For enterprise or government archaeological units, utilizing public API endpoints (such as standard OpenAI or Google AI Studio) may violate data processing agreements or national heritage policies.9 In these scenarios, Microsoft Azure OpenAI Service or AWS Bedrock represent the mandatory cloud paths. Azure OpenAI provides dedicated compliance boundaries (e.g., FedRAMP High equivalent) and strictly guarantees that customer data is not utilized for underlying model training.9 The HOARD configuration schema must include a data\_residency\_mode toggle. When enabled, this setting restricts routing strictly to Azure/AWS endpoints or forces local Ollama execution for specific data fields, ensuring that coordinates and ownership data never traverse public inference endpoints.

## **2\. Phase 1 Cloud Alternatives to GLM-OCR**

The current localized architecture employs GLM-OCR via Ollama for Phase 1 structured extraction. While highly secure regarding data privacy, it struggles with the idiosyncratic nature of handwritten archaeological forms. Specifically, it frequently misses bracketed context numbers indicating physical relationships (e.g., cuts (105)) and struggles to definitively interpret muddy or faintly ticked checkboxes representing inclusion frequencies or boundary clarities. Cloud alternatives present a profound opportunity to dramatically increase extraction fidelity.

### **Vision-Language Models (VLMs) vs. Specialized Document AI**

The analysis requires a direct comparison between generalist multimodal LLMs (GPT-4o, Claude 3.5 Sonnet, Gemini 2.5) against specialized Optical Character Recognition (OCR) services, specifically Azure Document Intelligence and Google Enterprise Document OCR.  
Generalist VLMs are highly adaptable and possess deep semantic understanding. GPT-4o and Claude 3.5 Sonnet excel at interpreting the broader context of a messy archaeological form. If an archaeologist scribbles a soil description haphazardly across multiple designated fields, a VLM can synthesize the user's intent and map the text to the correct JSON key based on its understanding of stratigraphy. However, VLMs suffer from acute spatial blindness regarding small geometric shapes. They frequently hallucinate the state of selection marks, interpreting a smudge of site dirt as a checked box for "Diffuse Boundary".9  
Conversely, specialized Document AI services are deterministic computer vision systems optimized for exact spatial layout preservation and form field extraction.11 Azure Document Intelligence features prebuilt models and custom extraction capabilities that utilize Microsoft's proprietary OCR to extract printed and handwritten text with exceptional precision.12 Crucially, Azure explicitly isolates selection marks (checkboxes and radio buttons), returning distinct confidence scores for their specific states (selected or unselected).13  
Google Enterprise Document OCR offers similar specialized layout parsing and handwriting recognition.15 However, Google's documentation explicitly notes that checkbox detection relies heavily on the physical dimensions of the mark, recommending a minimum size of 12mm x 12mm (0.47 inches) for accurate extraction.16 This physical constraint is highly problematic, as standard A4 archaeological context sheets often feature densely packed, millimeter-scale checkboxes to maximize space for field notes. Azure's algorithmic approach to selection marks generally yields higher accuracy on these constrained forms.

| Capability Feature | OpenAI GPT-4o | Anthropic Claude 3.5 Sonnet | Google Gemini 2.5 Pro | Azure Document Intelligence | Google Document AI |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Handwriting OCR | High (Semantic) | High (Semantic) | High (Semantic) | Very High (Deterministic) 12 | High (Deterministic) 15 |
| Checkbox Detection | Poor (Hallucinates) | Poor (Hallucinates) | Poor (Hallucinates) | Excellent (Confidence Scores) 14 | Moderate (Size dependent) 16 |
| Stratigraphic Matrix Parsing | Moderate | High | Moderate | Low (Requires custom model) 17 | Low |
| Layout Preservation | Low | Low | Low | Very High 12 | High 15 |
| Structured JSON Output | Native (response\_format) 3 | Native (tool\_use) 3 | Native (responseSchema) 3 | Native API Response 11 | Native API Response |
| Estimated Cost per Page | \~$0.005 | \~$0.020 | \~$0.008 | $0.010 (Prebuilt) 10 | Variable by tier |

### **Hybrid Architectural Recommendation for Phase 1**

Relying solely on a generative VLM for structured extraction of a heavily formatted page yields high semantic accuracy but unacceptably poor spatial and checkbox accuracy. Conversely, relying solely on a Document AI service yields perfect spatial extraction but poor handling of free-text spillover and complex stratigraphic matrix diagrams.  
The most robust architectural recommendation is a composite cloud approach for Phase 1:

1. **Primary Spatial Extraction:** Route the scanned context sheet through Azure Document Intelligence (utilizing the Layout Model) to capture all handwritten text, paragraph bounding boxes, and selection mark states deterministically.11  
2. **Semantic Synthesis and Mapping:** Pass the resulting raw, verbose JSON and layout coordinates from Azure directly into a highly cost-efficient cloud LLM, such as Gemini 2.5 Flash-Lite (priced at an exceptionally low $0.10 per million input tokens).6 The LLM's prompt instructs it to map the deterministic OCR output into HOARD's standardized schema contract.

This hybrid methodology allows the LLM to resolve spillovers and correct localized OCR misinterpretations using its semantic understanding of archaeological terminology, while ensuring that critical Boolean states—such as whether a context is a cut or a deposit—are interpreted based on the geometric reality determined by Azure, completely bypassing the VLM hallucination problem.

## **3\. NuExtract3 Alternatives and Structured Extraction Strategy**

The initial local architecture identified numind/NuExtract3 as the theoretically optimal model for forcing strict schema compliance on OCR text. NuExtract3 is a 4-billion parameter Vision-Language Model based on the Qwen3.5-4B architecture, fine-tuned specifically via reinforcement learning for structured document extraction.19 A critical blocker recorded in previous sessions stated that NuExtract3 was unavailable in GGUF format for Ollama execution, seemingly necessitating complex vLLM deployment.

### **Re-evaluating NuExtract3 Availability and Deployment Paths**

Recent repository data confirms that the assumption regarding NuExtract3's format availability is outdated. Multiple quantization formats, including GGUF and Apple MLX formats, have been published by the community and the creators.20 Specifically, the numind/NuExtract3-GGUF repository contains models natively compatible with llama.cpp.20 Despite this, deploying it seamlessly via Ollama remains suboptimal due to Ollama's highly specific chat template engine, which frequently misaligns with NuExtract3's unique extraction-specific tokens and its dual "reasoning" (thinking) and "non-reasoning" inference modes.20 Therefore, three distinct paths must be evaluated for local structured extraction.  
**Path A: Deployment via vLLM** Serving NuExtract3 via vLLM provides an OpenAI-compatible API layer running entirely locally. Running a 4B parameter model in native FP16 (bfloat16) precision requires approximately 18-20 GB of VRAM when accounting for weights and a moderately sized Key-Value (KV) cache.23 This vastly exceeds the 8 GB VRAM limit of the target consumer hardware (NVIDIA RTX 3070 Laptop).23 However, utilizing vLLM's PagedAttention architecture and serving an INT4 or INT8 quantized version drastically alters the mathematical constraints. An INT4 quantized 4B model occupies roughly 2.5 GB for weights.23 Allocating an additional 4 GB for the KV cache permits processing of substantial document lengths (up to the model's 131,072 token maximum, which can be dynamically scaled down via the \--max-model-len parameter to prevent Out-Of-Memory errors).20  
The primary drawback of Path A is startup overhead. vLLM is considerably heavier than Ollama, requiring dedicated port binding and rigid VRAM pre-allocation.25 It cannot dynamically share the 8 GB VRAM pool seamlessly with other concurrent Ollama processes without strict memory utilization capping (e.g., setting \--gpu-memory-utilization 0.8).24 This introduces significant architectural complexity for a pipeline meant to run smoothly on a single consumer GPU.  
**Path B: Alternative Structured Extraction Models on Local Hardware** Given the discovery of the GGUF formats 20, bypassing Ollama and executing the model directly via a lightweight llama.cpp Python binding is highly viable. This eliminates the vLLM server overhead and bypasses Ollama's problematic template engine 22, allowing explicit passing of the JSON template and target document directly to the W8A8 or W4A16 quantized NuExtract3 model.20  
Alternatively, the pipeline could leverage GLiNER or GLiREL. While exceptionally fast and requiring negligible VRAM, these models are designed for flat Named Entity Recognition (NER) and struggle profoundly with the deeply nested JSON schemas and Boolean logic required for archaeological context sheets.  
Another option is repurposing Qwen3-VL-8B, which is already loaded into memory for Phase 2\. While Qwen3-VL possesses multimodal function calling, 8B generalist models exhibit higher rates of schema deviation compared to NuExtract3, which was explicitly trained via reinforcement learning for exact JSON template adherence.19  
**Path C: Prompt-Based Extraction with the Synthesis Model**  
If deploying a dedicated extraction model proves too taxing for VRAM management, the task must be shifted to the existing Phase 3 synthesis model (qwen3.5-abliterated:4B). This model possesses similar parameter counts to NuExtract3 but lacks the specialized extraction tokens. Implementing a strict constrained generation grammar—utilizing the Outlines library or llama.cpp's native JSON schema grammar enforcement—can mathematically coerce the Qwen model into extracting the OCR output reliably. However, this approach yields higher latency and lower semantic accuracy, as the model's attention mechanisms are not optimized for dense layout parsing.

### **Extraction Strategy Decision Matrix**

| Strategy Path | VRAM Requirement (Est.) | Schema Adherence Reliability | Integration Effort | Hardware Compatibility (RTX 3070 8GB) |
| :---- | :---- | :---- | :---- | :---- |
| Path A: vLLM \+ NuExtract3 (INT4) | 6.5 GB (Fixed allocation) 23 | Very High 19 | High (Requires managing concurrent servers) | Moderate (Causes resource contention with Ollama) |
| **Path B: llama.cpp \+ NuExtract3 GGUF** | **4.5 GB (Dynamic)** 20 | **Very High** 19 | **Moderate (Requires custom Python bindings)** | **Excellent** |
| Path B: Qwen3-VL-8B (Reuse) | 7.5 GB | Moderate (Hallucination risk) | Low (Already integrated) | Good |
| Path C: Phase 3 Prompting | 4.0 GB | Low (Requires strict grammar constraints) | Low | Excellent |

The optimal strategy dictates adopting **Path B** for localized operation, utilizing the numind/NuExtract3-GGUF model in INT4 or INT8 precision executed directly via llama.cpp Python bindings. This restricts VRAM usage to a manageable 4-5 GB, ensuring the RTX 3070 can process the image and extract the data without out-of-memory faults, while circumventing Ollama's chat template limitations. For cloud-enabled sessions, this local extraction step is bypassed entirely, seamlessly offloaded to the hybrid Azure/Gemini pipeline outlined in Section 2\.

## **4\. Automated Acquisition of Grey Literature and Overcoming ADS Blockers**

Testing the end-to-end synthesis capabilities of HOARD—specifically its ability to draft compliant, nuanced archaeological narratives—necessitates vast corpora of completed, professional grey literature to serve as ground truth and few-shot RAG examples. The Archaeology Data Service (ADS) hosts tens of thousands of these reports. However, the ADS actively enforces HTTP 403 Forbidden responses against automated web scraping and headless browsers attempting to access the raw PDF URLs directly.26 This bot-mitigation strategy represents a critical blocker for automated End-to-End (E2E) testing pipelines.

### **Metadata Harvesting via OAI-PMH**

While the PDF payload URLs are protected by Web Application Firewalls (WAF), the metadata required to locate, categorize, and index these reports is fully open and accessible via standardized archival protocols. The ADS maintains an active Open Archives Initiative Protocol for Metadata Harvesting (OAI-PMH) target at the base URL https://archaeologydataservice.ac.uk/oai-pmh/.30  
This endpoint exposes repository data using unqualified Dublin Core elements and native AMCR XML formats.31 Furthermore, the ADS pushes metadata to the DataCite API, utilizing the Data Centre symbol BL.ADS, which allows querying via the global DataCite infrastructure.30  
To bypass the automated download restrictions without violating the terms of service or triggering IP bans, the HOARD architecture must implement a two-stage hybrid acquisition strategy:

1. **Automated Discovery and Indexing:** A Python service within HOARD queries the OAI-PMH endpoint using specific protocol verbs (e.g., ListRecords with metadataPrefix=oai\_dc) or interfaces with the DataCite REST API. The script filters records containing specific archaeological subject schemes (e.g., subjectScheme="FISH Archaeological Objects (England)") and extracts the corresponding title, author, date, and Digital Object Identifier (DOI).32  
2. **Browser-Assisted Workflow:** The pipeline dynamically generates a local HTML dashboard presenting the parsed metadata and the DOI resolution links. The human operator clicks the links during an active, authenticated browser session, manually downloading the PDFs into the designated HOARD ingestion directory.

### **Alternative Open-Access Platforms**

Relying solely on the ADS introduces a single point of failure for training data acquisition. The wider landscape of open-access archaeological literature provides alternative repositories with distinct API accessibility profiles:

* **Hyper Article en Ligne (HAL):** The French national repository demonstrates an "Exemplary Readiness Level" for data and literature deposition and maintains a rigorous open-access mandate.33 HAL provides unrestricted API access to European archaeological grey literature and academic theses, making it an excellent secondary source for structural examples.  
* **Zenodo Communities:** Zenodo hosts specific archaeological communities (e.g., the Grey Literature Library and independent project dumps) offering direct API access to file payloads without the stringent bot protection implemented by national heritage archives.33  
* **ARIADNE Portal:** A massive aggregator of European archaeological datasets. The ARIADNE Knowledge Base provides a public SPARQL endpoint enabling complex semantic queries across integrated data from national repositories.30 While it aggregates metadata perfectly, it often redirects back to the original host (like the ADS) for the actual file, necessitating the browser-assisted workflow mentioned above.35  
* **OpenAlex:** An index of global scholarly metadata. While massive, research indicates that OpenAlex suffers from significant gaps regarding archaeological monographs, edited volumes, and specifically grey literature, making it sub-optimal for primary report acquisition compared to domain-specific repositories.37  
* **Local HER APIs (HBSMR):** Many local Historic Environment Records utilize the HBSMR software platform.41 Certain implementations offer public Web/API gateways, providing localized access to event and monument data, though PDF report availability varies strictly by local authority policy.

### **Specific E2E Testing Data: The Gallows Hill Case**

The user session notes specifically mentioned the "Gallows Hill" site for E2E testing. While automated scraping of the ADS is blocked, specific planning and infrastructure domains host open-access PDFs of Gallows Hill archaeological evaluations that can be downloaded programmatically without triggering 403 errors. Relevant open-access reports for this site include:

1. **Headland Archaeology Trial Trenching Report:** Available via the National Infrastructure Planning portal (https://nsip-documents.planninginspectorate.gov.uk/published-documents/EN020024-000145-5.3.7E...).42  
2. **Cultural Heritage Baseline Report (Warwick):** Available via the same infrastructure portal (https://nsip-documents.planninginspectorate.gov.uk/published-documents/EN020026-000290-6.3.2.3.A...).43  
3. **Drax PEIR Volume 3 Appendices:** Containing National Grid heritage assessments for the Gallows Hill location (https://www.drax.com/wp-content/uploads/2019/12/Drax-PEIR-Volume-3-Appendices.pdf).44

These URLs provide immediate, unauthenticated access to high-quality grey literature perfectly suited for validating the HOARD Phase 3 synthesis engine without engaging the ADS browser workflow.

### **Legality of Automated Access**

From a legal perspective, downloading published grey literature for local processing and data extraction falls firmly under data mining exemptions for non-commercial research in many jurisdictions, including UK fair dealing laws. The HTTP 403 response from the ADS is a technical Web Application Firewall (WAF) configuration designed to protect server bandwidth and prevent denial-of-service, not a copyright restriction on the content itself, which is often licensed under Creative Commons (e.g., CC-BY 4.0).29 Therefore, the browser-assisted download workflow ensures full legal compliance while respecting the host's technical infrastructure limits.

## **5\. Economic Feasibility and Cost Analysis**

The viability of migrating HOARD to a hybrid architecture relies on clearly defining the economic threshold where the electricity and hardware depreciation costs of local processing intersect with the operational expenditure of cloud API utilization.

### **Latent Local Costs and Hardware Depreciation**

Operating an NVIDIA RTX 3070 mobile GPU alongside an AMD Ryzen 5800H processor under maximum sustained load during deep inference draws approximately 130W for the GPU and 50W for the CPU and motherboard overhead, totaling an estimated 180W continuous draw.  
A standard 50-context-sheet archaeological site entails extensive multimodal extraction, spatial analysis, and iterative narrative synthesis. Executing this pipeline end-to-end locally on the specified hardware requires approximately 3.5 hours of constant processing to manage the generative throughput of 4B and 8B models.

* **Energy Consumption:** 180W \* 3.5 hours \= 0.63 kWh.  
* **Electricity Cost:** At a standard UK energy tariff of roughly £0.25 ($0.32 USD) per kWh, the direct electricity cost per pipeline run is **$0.20 USD**.  
* **Latent Hardware Costs:** Sustained maximal thermal cycling rapidly degrades thermal paste, fan bearings, and silicon on mobile workstations. Assuming a gaming laptop lifespan of 3,000 heavy processing hours before catastrophic component failure, and a replacement cost of $1,500, hardware depreciation adds an estimated $1.75 per run. Therefore, the true local operational cost approaches **$1.95 per site**.

### **Cloud API Operational Expenditure**

A 50-context-sheet site typically generates a cumulative input context of approximately 250,000 text tokens (system prompts, JSON schemas, historical context) and 50 high-resolution images across all phases. The generative synthesis requires roughly 30,000 output tokens.  
The cloud ecosystem offers profound cost-saving mechanisms through context caching. Anthropic offers explicit prompt caching (Read costs drop from $3.00/M to $0.30/M tokens) 45, while Google Gemini offers context caching that can reduce input costs by up to 90% for repeated document analysis.6 Because HOARD repeatedly passes the same system instructions and site background to the model during Phase 3 recursive drafting, these caching mechanisms drastically reduce the effective input cost.

| Cost Component | Scenario A: Budget (Gemini Flash-Lite) | Scenario B: Premium (Claude 3.5 Sonnet) | Scenario C: Hybrid (Azure Doc AI \+ Sonnet) | Local Execution (Depreciation Adjusted) |
| :---- | :---- | :---- | :---- | :---- |
| Phase 1: Text/Image Input | 250K tokens @ $0.10/M \= $0.025 6 | 250K tokens @ $3.00/M \= $0.75 45 | 50 pages @ $10/1000 \= $0.50 10 | $0.00 |
| Phase 3: Text Output | 30K tokens @ $0.40/M \= $0.012 6 | 30K tokens @ $15.00/M \= $0.45 4 | 30K tokens @ $15.00/M \= $0.45 4 | $0.00 |
| Image Processing | \~$0.010 | \~$0.150 | N/A (Handled by Azure) | $0.00 |
| Electricity / Wear | $0.00 | $0.00 | $0.00 | $1.95 (0.63 kWh \+ hardware wear) |
| **Total Cost Per Site** | **$0.047** | **$1.350** | **$0.950** | **$1.950** |

### **Break-Even Analysis and Volume Recommendations**

The mathematical realities indicate that utilizing ultra-efficient cloud endpoints like Gemini 2.5 Flash-Lite is fundamentally cheaper ($0.047) than the raw electricity required to power the local GPU ($0.20) for the equivalent timeframe.6  
Even deploying a highly capable, premium hybrid configuration—utilizing Azure for perfect Phase 1 extraction and Claude 3.5 Sonnet for Phase 3 synthesis—at $0.95 per site is economically superior to the true depreciation-adjusted cost of operating a gaming laptop at maximum thermal limits ($1.95).  
For an independent archaeologist processing one site per month, the financial differences are negligible, and the choice depends entirely on data privacy preferences. However, for a commercial archaeological unit processing high volumes (e.g., \>10 sites per month), the cloud architecture not only eliminates hardware bottlenecks and hardware replacement cycles but drastically reduces processing time from 3.5 hours to under 10 minutes due to the massive parallelization of API calls. The compounding labor savings completely eclipse the minimal API expenditure.

## **6\. Phase 2 and 3 Cloud Alternatives for Spatial Reconstruction and Synthesis**

Phases 2 and 3 demand the highest cognitive and contextual reasoning within the HOARD pipeline. Phase 2 requires interpreting highly complex visual data—identifying soil matrices, boundaries, and Munsell color variations from field photography. Phase 3 requires holding the entirety of the extracted data in memory to draft a coherent, publication-ready narrative without introducing contradictions.

### **Phase 2: Visual and Spatial Reconstruction**

Locally, Phase 2 relies on Qwen3-VL-8B. While competent, 8B models struggle with the subtle, low-contrast visual boundaries typical of archaeological section drawings and trench photos. The transition to cloud APIs offers transformative capabilities for this specific task.  
Claude 3.5 Sonnet is universally recognized as Anthropic's strongest vision model, demonstrating superior capability in analyzing complex spatial layouts and visual textures.46 For Phase 2, the architecture should dynamically route image captioning and stratigraphic interpretation to Claude 3.5 Sonnet. The model possesses the visual acuity to accurately parse the clarity of stratigraphy—distinguishing, for example, a diffuse, gradual boundary caused by bioturbation from a sharp truncation cut caused by a Roman ditch. By enriching the spatial matrix data with highly accurate visual descriptions before synthesis, the overall quality of the report increases exponentially.

### **Phase 3: High-Context Synthesis via RAG**

The localized Phase 3 architecture employs qwen3.5-abliterated:4B, which fundamentally caps the effective context window around 32,000 tokens before VRAM exhaustion occurs or the model's attention mechanisms lose focus. A typical archaeological site easily exceeds this token limit, requiring the pipeline to chunk data and summarize recursively. This recursive summarization inevitably leads to information loss, particularly regarding cross-trench relationships and overarching site chronologies.  
Cloud models entirely bypass this limitation. Google's Gemini 2.5 Pro and Flash models offer an unprecedented 1,000,000+ token context window.5 Claude 3.5 Sonnet supports 200,000 tokens 4, and GPT-4o supports 128,000.2 This immense capacity allows the HOARD pipeline to inject the entirety of the site's context sheets, finds catalogues, and environmental sample results into a single prompt payload. The model can then synthesize the overarching site narrative with complete, uncompressed access to all primary data points, eliminating the need for complex chunking logic.  
Furthermore, synthesizing publication-ready reports requires profound typological and chronological reasoning. The system must implement Retrieval-Augmented Generation (RAG) to ground the LLM's typological assertions.48 By integrating a vector store containing regional archaeological frameworks and existing grey literature, Phase 3 can query reference texts during synthesis. Research demonstrates that multimodal RAG systems specifically engineered for provenance analysis significantly improve chronological and cultural attributions.49 By embedding paragraphs of reference texts and retrieving them based on semantic similarity to the current context sheet being drafted, the system mitigates the risk of hallucination. It forces the model to cite retrieved stylistic parallels—such as comparing an extracted pottery description to known Romano-British typologies—ensuring that the pipeline generates historical inferences aligned with established regional knowledge rather than relying solely on the LLM's generalized parametric memory.48

## **7\. Open-Access Archaeological Dataset Landscape**

To rigorously benchmark the hybrid HOARD pipeline, fine-tune local quantized models, and populate the RAG vector stores utilized in Phase 3, the architecture must interface with expansive, open-access archaeological datasets. Beyond the metadata harvesting of the ADS detailed in Section 4, the global landscape provides critical resources across various modalities that can be programmatically accessed.

### **The Hugging Face Ecosystem**

The machine learning community is increasingly organizing heritage data into accessible, standardized formats suitable for computational analysis and AI training. These datasets provide the exact modalities required to test HOARD's visual and reasoning engines:

* **Archaeo-CLIP:** A massive visual dataset encompassing 45,256 captioned archaeological artifact images, compiled from Open Context.51 This dataset is imperative for fine-tuning local multimodal models (such as Qwen3-VL-8B) to better recognize artifact typologies, differentiating intricate historical ceramics or lithics with higher accuracy.  
* **Palaeochannels (MAPS):** A multitemporal multispectral dataset containing geospatial imagery and annotations, directly applicable for testing spatial analysis logic and landscape contextualization.52  
* **CoT Reasoning The Ancient Past:** This dataset focuses on Chain-of-Thought (CoT) reasoning behind historical interpretations.53 It provides structured examples of how historical conclusions are drawn from raw evidence, serving as ideal few-shot prompt examples for the Phase 3 synthesis engine to enforce logical, rigorous historical drafting.  
* **Egyptian Hieroglyphic Layout Analysis (HLA):** Containing precise polygonal segmentation masks for complex historical texts 54, this dataset can be utilized to benchmark the pipeline's geometric and spatial recognition boundaries, pushing the limits of the Azure and VLM extraction architectures.

### **Governmental and Institutional APIs**

Accessing structured, authoritative spatial and typological data is critical for validating the geographical assertions made during synthesis and providing accurate background context for the site reports.

* **National Heritage List for England (NHLE):** Historic England maintains a comprehensive, open spatial database of all nationally protected sites, accessible via an open API and ArcGIS FeatureServer endpoints.55 The HOARD pipeline can query this endpoint to automatically cross-reference the excavation site's geographic coordinates with known nearby scheduled monuments, automatically enriching the "Archaeological Background" section of the final drafted report without manual intervention.  
* **Open Context API:** This platform publishes deeply structured field notes, excavation data, and geographic information.58 Supported by robust open-source technologies (PostgreSQL, Apache Solr) 59, Open Context exposes a powerful RESTful querying interface. HOARD can leverage this API to retrieve highly specific datasets—such as filtering for osteological bone analyses dating between specific chronological bounds 60—to test the pipeline's ability to interpret and synthesize complex tabular data and radiometric dating parameters.

| Dataset / Source | Modality | Primary Use Case for HOARD | Access Method | Licensing / Status |
| :---- | :---- | :---- | :---- | :---- |
| **Archaeo-CLIP** 51 | Captioned Images (45k+) | Fine-tuning Phase 2 spatial/artifact models | Hugging Face Datasets | GPL-3.0 / Open Access |
| **CoT Ancient Past** 53 | Text (Reasoning) | Few-shot prompting for Phase 3 synthesis | Hugging Face Datasets | Open Access |
| **NHLE (Historic England)** 55 | Spatial (Points/Polygons) | Automated background section generation | ArcGIS REST API | Open Government Licence |
| **Open Context** 58 | Structured Data / Text | Testing tabular extraction and RAG | REST API / Solr | Creative Commons |
| **Zenodo Grey Lit** 34 | PDF Reports | End-to-end synthesis benchmarking | Zenodo API | Variable (Mostly CC) |
| **HAL (France)** 33 | PDF Reports / Theses | European structural examples | HAL API | Open Access |

By seamlessly integrating these external data structures into the HOARD ecosystem—utilizing them for benchmarking, fine-tuning, and active RAG retrieval—the pipeline completes its transition from an isolated, hardware-bound parsing engine into a globally connected, spatially aware archaeological synthesis platform. This architectural evolution ensures that HOARD not only digitizes raw field data but actively contextualizes it within the broader landscape of human heritage, delivering reports that meet the rigorous academic and compliance standards demanded by the modern archaeological sector.

#### **Works cited**

1. LLM API Differences That Break Your Code: Anthropic vs OpenAI vs Google \- FutureSearch, accessed June 2, 2026, [https://futuresearch.ai/blog/llm-provider-quirks/](https://futuresearch.ai/blog/llm-provider-quirks/)  
2. GPT 4o mini API Pricing 2026 \- Costs, Performance & Providers \- Price Per Token, accessed June 2, 2026, [https://pricepertoken.com/pricing-page/model/openai-gpt-4o-mini](https://pricepertoken.com/pricing-page/model/openai-gpt-4o-mini)  
3. Structured Output Comparison across popular LLM providers — OpenAI, Gemini, Anthropic, Mistral and AWS Bedrock | by Rost Glukhov | Medium, accessed June 2, 2026, [https://medium.com/@rosgluk/structured-output-comparison-across-popular-llm-providers-openai-gemini-anthropic-mistral-and-1a5d42fa612a](https://medium.com/@rosgluk/structured-output-comparison-across-popular-llm-providers-openai-gemini-anthropic-mistral-and-1a5d42fa612a)  
4. Introducing Claude 3.5 Sonnet \- Anthropic, accessed June 2, 2026, [https://www.anthropic.com/news/claude-3-5-sonnet](https://www.anthropic.com/news/claude-3-5-sonnet)  
5. Models overview \- Claude API Docs, accessed June 2, 2026, [https://platform.claude.com/docs/en/about-claude/models/overview](https://platform.claude.com/docs/en/about-claude/models/overview)  
6. Gemini API Pricing Calculator & Cost Guide (May 2026\) \- CostGoat, accessed June 2, 2026, [https://costgoat.com/pricing/gemini-api](https://costgoat.com/pricing/gemini-api)  
7. LLM API Comparison 2026: Pricing, Speed, Features | Every Provider \- Morph, accessed June 2, 2026, [https://www.morphllm.com/llm-api](https://www.morphllm.com/llm-api)  
8. OpenAI compatibility | Gemini API \- Google AI for Developers, accessed June 2, 2026, [https://ai.google.dev/gemini-api/docs/openai](https://ai.google.dev/gemini-api/docs/openai)  
9. Reducto vs. Google Cloud Document AI: Accuracy on Real‑World Edge Cases, accessed June 2, 2026, [https://llms.reducto.ai/reducto-vs-google-document-ai](https://llms.reducto.ai/reducto-vs-google-document-ai)  
10. Pricing \- Azure Document Intelligence in Foundry Tools, accessed June 2, 2026, [https://azure.microsoft.com/en-gb/pricing/details/document-intelligence/](https://azure.microsoft.com/en-gb/pricing/details/document-intelligence/)  
11. AI Document Extraction on Azure \- Options, Comparison & Recommendations for Invoice/Contract Processing \- Reddit, accessed June 2, 2026, [https://www.reddit.com/r/AZURE/comments/1pq490v/ai\_document\_extraction\_on\_azure\_options/](https://www.reddit.com/r/AZURE/comments/1pq490v/ai_document_extraction_on_azure_options/)  
12. Document layout analysis \- Document Intelligence \- Foundry Tools | Microsoft Learn, accessed June 2, 2026, [https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/layout?view=doc-intel-4.0.0](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/layout?view=doc-intel-4.0.0)  
13. What is Best Practice for Azure Document Intelligence Recognizing Hand-written Number Ones \[closed\] \- Stack Overflow, accessed June 2, 2026, [https://stackoverflow.com/questions/79234758/what-is-best-practice-for-azure-document-intelligence-recognizing-hand-written-n](https://stackoverflow.com/questions/79234758/what-is-best-practice-for-azure-document-intelligence-recognizing-hand-written-n)  
14. Document intelligence selection Mark method for radio buttons \- Microsoft Q\&A, accessed June 2, 2026, [https://learn.microsoft.com/en-us/answers/questions/5834532/document-intelligence-selection-mark-method-for-ra](https://learn.microsoft.com/en-us/answers/questions/5834532/document-intelligence-selection-mark-method-for-ra)  
15. Enterprise Document OCR | Document AI \- Google Cloud Documentation, accessed June 2, 2026, [https://docs.cloud.google.com/document-ai/docs/enterprise-document-ocr](https://docs.cloud.google.com/document-ai/docs/enterprise-document-ocr)  
16. \[Document AI\] Checkbox/Form Design \- AI Solutions \- Google Developer forums, accessed June 2, 2026, [https://discuss.google.dev/t/document-ai-checkbox-form-design/162439](https://discuss.google.dev/t/document-ai-checkbox-form-design/162439)  
17. Azure AI Document Intelligence for RAG use cases | by Anurag Chatterjee \- Medium, accessed June 2, 2026, [https://tech-depth-and-breadth.medium.com/azure-ai-document-intelligence-for-rag-use-cases-4e242b0ba7de](https://tech-depth-and-breadth.medium.com/azure-ai-document-intelligence-for-rag-use-cases-4e242b0ba7de)  
18. Azure Document Intelligence in Foundry Tools pricing, accessed June 2, 2026, [https://azure.microsoft.com/en-us/pricing/details/document-intelligence/](https://azure.microsoft.com/en-us/pricing/details/document-intelligence/)  
19. Blog \- NuMind, accessed June 2, 2026, [https://numind.ai/blog](https://numind.ai/blog)  
20. numind/NuExtract3 · Hugging Face, accessed June 2, 2026, [https://huggingface.co/numind/NuExtract3](https://huggingface.co/numind/NuExtract3)  
21. NuExtract3 released: open-weight 4B VLM for Markdown, OCR and structured extraction (self-hostable) \[P\] : r/MachineLearning \- Reddit, accessed June 2, 2026, [https://www.reddit.com/r/MachineLearning/comments/1tkejqr/nuextract3\_released\_openweight\_4b\_vlm\_for/](https://www.reddit.com/r/MachineLearning/comments/1tkejqr/nuextract3_released_openweight_4b_vlm_for/)  
22. NuExtract3 released: open-weight 4B VLM for Markdown, OCR and structured extraction (self-hostable) : r/LocalLLaMA \- Reddit, accessed June 2, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1tn8utn/nuextract3\_released\_openweight\_4b\_vlm\_for/](https://www.reddit.com/r/LocalLLaMA/comments/1tn8utn/nuextract3_released_openweight_4b_vlm_for/)  
23. GPU Memory Requirements for LLMs: VRAM Calculator | Spheron Blog, accessed June 2, 2026, [https://www.spheron.network/blog/gpu-memory-requirements-llm/](https://www.spheron.network/blog/gpu-memory-requirements-llm/)  
24. numind/NuExtract-1.5 · Hosting NuExtract on VLLM inference Engine \- Hugging Face, accessed June 2, 2026, [https://huggingface.co/numind/NuExtract-1.5/discussions/16](https://huggingface.co/numind/NuExtract-1.5/discussions/16)  
25. Engine Arguments \- vLLM Documentation, accessed June 2, 2026, [https://docs.vllm.ai/en/v0.6.1/models/engine\_args.html](https://docs.vllm.ai/en/v0.6.1/models/engine_args.html)  
26. PMC OAI-PMH API \- NIH, accessed June 2, 2026, [https://pmc.ncbi.nlm.nih.gov/tools/oai/](https://pmc.ncbi.nlm.nih.gov/tools/oai/)  
27. Proceedings of the Society of Antiquaries of Scotland: Contents for Volume 33 \- Archaeology Data Service, accessed June 2, 2026, [https://archaeologydataservice.ac.uk/archives/view/psas/contents.cfm?vol=33](https://archaeologydataservice.ac.uk/archives/view/psas/contents.cfm?vol=33)  
28. GPO Newgate Street 1975-79; the Roman levels \- Archaeology Data Service, accessed June 2, 2026, [https://archaeologydataservice.ac.uk/library/browse/details.xhtml?recordId=3189851](https://archaeologydataservice.ac.uk/library/browse/details.xhtml?recordId=3189851)  
29. Notes on the family of Amundeville \- Archaeology Data Service, accessed June 2, 2026, [https://archaeologydataservice.ac.uk/library/browse/details.xhtml?recordId=3211962](https://archaeologydataservice.ac.uk/library/browse/details.xhtml?recordId=3211962)  
30. Metadata services \- Archaeology Data Service, accessed June 2, 2026, [https://archaeologydataservice.ac.uk/about/policies/metadata/metadata-services/](https://archaeologydataservice.ac.uk/about/policies/metadata/metadata-services/)  
31. OAI-PMH API – AMCR API \- GitHub Pages, accessed June 2, 2026, [https://arup-cas.github.io/aiscr-api-home/oai-pmh/](https://arup-cas.github.io/aiscr-api-home/oai-pmh/)  
32. OAI-PMH Schema Documentation \- DataCite Support, accessed June 2, 2026, [https://support.datacite.org/docs/oai-pmh-schema-documentation](https://support.datacite.org/docs/oai-pmh-schema-documentation)  
33. Update of the Study on the readiness of research data and literature repositories to facilitate compliance with the Open Science \- Zenodo, accessed June 2, 2026, [https://zenodo.org/records/13919643/files/Update%20of%20ERC%20Study%20on%20repositories%20-%20final%20report.pdf?download=1](https://zenodo.org/records/13919643/files/Update%20of%20ERC%20Study%20on%20repositories%20-%20final%20report.pdf?download=1)  
34. Search Grey Literature Strategies Project Archive \- Zenodo, accessed June 2, 2026, [https://zenodo.org/communities/greylitstrategies/](https://zenodo.org/communities/greylitstrategies/)  
35. Support for Ariadne portal and/or ADS · Issue \#34 · clarin-eric/DOGlib \- GitHub, accessed June 2, 2026, [https://github.com/clarin-eric/DOGlib/issues/34](https://github.com/clarin-eric/DOGlib/issues/34)  
36. The ARIADNEplus Knowledge Base: a Linked Open Data set for archaeological research \- CNR-IRIS, accessed June 2, 2026, [https://iris.cnr.it/retrieve/eb1ddaa7-cde8-4a12-9402-87e4237633a0/paper16.pdf](https://iris.cnr.it/retrieve/eb1ddaa7-cde8-4a12-9402-87e4237633a0/paper16.pdf)  
37. Replication report for Marwick (2025) “Is archaeology a science?”, including new data from OpenAlex \- Peer Community Journal, accessed June 2, 2026, [https://peercommunityjournal.org/item/10.24072/pcjournal.710.pdf](https://peercommunityjournal.org/item/10.24072/pcjournal.710.pdf)  
38. Replication report for Marwick (2025) “Is archaeology a science?”, including new data from OpenAlex \- Peer Community Journal, accessed June 2, 2026, [https://peercommunityjournal.org/articles/10.24072/pcjournal.710/](https://peercommunityjournal.org/articles/10.24072/pcjournal.710/)  
39. Replication report for Marwick (2025) “Is archaeology a science?”, including new data from OpenAlex \- GitHub Pages, accessed June 2, 2026, [https://aqueff.github.io/replication\_Marwick2025\_OpenAlex/](https://aqueff.github.io/replication_Marwick2025_OpenAlex/)  
40. Scholarly metadata pertaining to monographs and grey literature \- Zack Batist, accessed June 2, 2026, [https://zackbatist.info/posts/2025-08-18-open-scholarly-metadata/](https://zackbatist.info/posts/2025-08-18-open-scholarly-metadata/)  
41. HBSMR Historic Environment \- Exegesis Spatial Data Management (an Idox company), accessed June 2, 2026, [https://www.esdm.co.uk/hbsmr-historic-environment](https://www.esdm.co.uk/hbsmr-historic-environment)  
42. Yorkshire Green Energy Enablement (GREEN) Project \- Planning Inspectorate, accessed June 2, 2026, [https://nsip-documents.planninginspectorate.gov.uk/published-documents/EN020024-000145-5.3.7E%20Appendix%207E%20Trial%20Trenching%20at%20Overton%20Substation%20and%20Monk%20Fryston%20Substation.pdf](https://nsip-documents.planninginspectorate.gov.uk/published-documents/EN020024-000145-5.3.7E%20Appendix%207E%20Trial%20Trenching%20at%20Overton%20Substation%20and%20Monk%20Fryston%20Substation.pdf)  
43. Sea Link \- Planning Inspectorate, accessed June 2, 2026, [https://nsip-documents.planninginspectorate.gov.uk/published-documents/EN020026-000290-6.3.2.3.A%20ES%20Appendix%202.3.A%20Cultural%20Heritage%20Baseline%20Report.pdf](https://nsip-documents.planninginspectorate.gov.uk/published-documents/EN020026-000290-6.3.2.3.A%20ES%20Appendix%202.3.A%20Cultural%20Heritage%20Baseline%20Report.pdf)  
44. DRAX REPOWER PROJECT, accessed June 2, 2026, [https://www.drax.com/wp-content/uploads/2019/12/Drax-PEIR-Volume-3-Appendices.pdf](https://www.drax.com/wp-content/uploads/2019/12/Drax-PEIR-Volume-3-Appendices.pdf)  
45. Pricing \- Claude API Docs, accessed June 2, 2026, [https://platform.claude.com/docs/en/about-claude/pricing](https://platform.claude.com/docs/en/about-claude/pricing)  
46. Anthropic's Claude 3.5 Sonnet model now available in Amazon Bedrock: Even more intelligence than Claude 3 Opus at one-fifth the cost | AWS News Blog, accessed June 2, 2026, [https://aws.amazon.com/blogs/aws/anthropics-claude-3-5-sonnet-model-now-available-in-amazon-bedrock-the-most-intelligent-claude-model-yet/](https://aws.amazon.com/blogs/aws/anthropics-claude-3-5-sonnet-model-now-available-in-amazon-bedrock-the-most-intelligent-claude-model-yet/)  
47. GPT-4o-mini \- API Pricing & Benchmarks | OpenRouter, accessed June 2, 2026, [https://openrouter.ai/openai/gpt-4o-mini](https://openrouter.ai/openai/gpt-4o-mini)  
48. The State of Retrieval-Augmented Generation (RAG) in 2025 and Beyond \- Aya Data, accessed June 2, 2026, [https://www.ayadata.ai/the-state-of-retrieval-augmented-generation-rag-in-2025-and-beyond/](https://www.ayadata.ai/the-state-of-retrieval-augmented-generation-rag-in-2025-and-beyond/)  
49. Provenance Analysis of Archaeological Artifacts via Multimodal RAG Systems \- arXiv, accessed June 2, 2026, [https://arxiv.org/html/2509.20769v1](https://arxiv.org/html/2509.20769v1)  
50. Provenance Analysis of Archaeological Artifacts via Multimodal RAG Systems \- arXiv, accessed June 2, 2026, [https://arxiv.org/abs/2509.20769](https://arxiv.org/abs/2509.20769)  
51. opencontext/archaeo-clip \- Hugging Face, accessed June 2, 2026, [https://huggingface.co/opencontext/archaeo-clip](https://huggingface.co/opencontext/archaeo-clip)  
52. CCHT-IIT/Palaeochannels · Datasets at Hugging Face, accessed June 2, 2026, [https://huggingface.co/datasets/CCHT-IIT/Palaeochannels](https://huggingface.co/datasets/CCHT-IIT/Palaeochannels)  
53. mattwesney/CoT\_Reasoning\_The\_Ancient\_Past · Datasets at Hugging Face, accessed June 2, 2026, [https://huggingface.co/datasets/mattwesney/CoT\_Reasoning\_The\_Ancient\_Past](https://huggingface.co/datasets/mattwesney/CoT_Reasoning_The_Ancient_Past)  
54. AhmedElTaher/Egyptian\_Hieroglyphic\_Layout\_Analysis\_HLA · Datasets at Hugging Face, accessed June 2, 2026, [https://huggingface.co/datasets/AhmedElTaher/Egyptian\_Hieroglyphic\_Layout\_Analysis\_HLA](https://huggingface.co/datasets/AhmedElTaher/Egyptian_Hieroglyphic_Layout_Analysis_HLA)  
55. World Heritage Sites | Catchment Based Approach Data Hub, accessed June 2, 2026, [https://data.catchmentbasedapproach.org/datasets/historicengland::national-heritage-list-for-england-nhle/about?layer=10](https://data.catchmentbasedapproach.org/datasets/historicengland::national-heritage-list-for-england-nhle/about?layer=10)  
56. National Heritage List for England (NHLE) \- API Catalogue, accessed June 2, 2026, [https://www.api.gov.uk/he/national-heritage-list-for-england-nhle/](https://www.api.gov.uk/he/national-heritage-list-for-england-nhle/)  
57. National Heritage List for England (NHLE) \- Historic England Open Data Hub, accessed June 2, 2026, [https://opendata-historicengland.hub.arcgis.com/maps/767f279327a24845bf47dfe5eae9862b](https://opendata-historicengland.hub.arcgis.com/maps/767f279327a24845bf47dfe5eae9862b)  
58. Open Context: Publisher of Research Data, accessed June 2, 2026, [https://opencontext.org/](https://opencontext.org/)  
59. About \- Technology \- Open Context, accessed June 2, 2026, [https://opencontext.org/about/technology](https://opencontext.org/about/technology)  
60. About \- Web Services and APIs \- Open Context, accessed June 2, 2026, [https://opencontext.org/about/services](https://opencontext.org/about/services)