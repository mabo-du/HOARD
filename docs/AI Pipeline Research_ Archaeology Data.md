# **HOARD Pipeline Architecture and Heritage Compliance: 2026 Advanced Research Report**

## **Architectural Overview and Edge-Compute Constraints**

The development of the Heritage Observation And Report Drafter (HOARD) pipeline represents a profound engineering challenge at the intersection of cultural heritage management and edge-compute artificial intelligence. Operating strictly within a 6 GB VRAM local ecosystem—typical of consumer-grade hardware such as the NVIDIA RTX 3060 (12 GB) or RTX 4060 (8 GB) where system overhead consumes residual memory—demands severe architectural discipline. The pipeline must ingest highly idiosyncratic, noisy multimodal archaeological data, encompassing soil-stained handwritten context sheets, disparate finds catalogues, and variable spatial drawings, and autonomously reason over this corpus to draft a jurisdictionally compliant grey literature report.

As of 2026, the paradigm of document digitization and semantic synthesis has shifted decisively away from cascaded, task-specific neural networks toward unified, highly optimized Vision-Language Models (VLMs) and Small Language Models (SLMs). This analysis provides an exhaustive evaluation of digital archaeological recording structures, the contemporary open-weights model landscape for optical character recognition and semantic drafting within rigid VRAM boundaries, and the evolving regulatory frameworks of global heritage authorities that dictate final report compliance.

## **Interoperability and Digital Recording Frameworks: ARK and FAIMS Data Topologies**

The ingestion and triage phase of the HOARD pipeline relies entirely on the structural predictability of incoming digital field data. While HOARD utilizes a generic CSV and JSON import module, interfacing with industry-standard recording systems like the Archaeological Recording Kit (ARK) and Field Acquired Information Management Systems (FAIMS) requires accommodating deeply divergent database topologies. An analysis of real-world export structures dictates the engineering required for semantic interoperability.

### **ARK (Archaeological Recording Kit) Data Structures and Malleability**

ARK remains a foundational, open-source, web-based toolkit utilized extensively across European commercial and academic archaeology. The primary iterations in active circulation include v1.0, v3, and v4.1 Built upon a classic LAMP (Linux, Apache, MySQL, PHP) stack, ARK utilizes Web 2.0 paradigms to facilitate data sharing and mapping.1 A critical challenge in developing a static, hard-coded ingestion module for ARK is its fundamental architectural philosophy: ARK is designed to be infinitely malleable. It operates on a highly normalized Entity-Attribute-Value (EAV) model intertwined with a dynamic subform architecture.2

Consequently, ARK does not possess a singular, static schema with universally fixed column names for archaeological entities such as contexts, finds, or environmental samples.2 Instead, the system utilizes "main pages," "subforms," and central configuration files (specifically mod\_abk\_settings.php) to dynamically construct bespoke field schemas tailored to the exact requirements of a specific archaeological unit or excavation project.2 When practitioners generate CSV, JSON, XML, or RDF exports from ARK, the column headers are procedurally generated based on the string values stored within the user-defined field\_settings tables.2

Despite this inherent structural fluidity, empirical analysis of real-world ARK export datasets reveals consistent structural commonalities and nomenclatural patterns. Export datasets frequently utilize concatenated strings, aliased module prefixes, or standardized abbreviations.

| Archaeological Entity | Typical ARK Export Column Headers (v3 / v4) | Data Type Expectation |
| :---- | :---- | :---- |
| **Context Registers** | cxt\_id, cxt\_type (e.g., cut, deposit, masonry), cxt\_description, munsell\_color, strat\_above, strat\_below, site\_code, excavator\_initials. | Alphanumeric string, integer (matrices). |
| **Finds Catalogues** | sf\_id (small find), cxt\_ref (context reference), material\_class, typology, weight\_g, count, conservation\_status, period. | Integer, categorical string, float. |
| **Sample Registers** | sample\_id, cxt\_ref, sample\_type (environmental, C14, metallurgical), flot\_vol\_L, residue\_vol\_L, processing\_status. | Integer, categorical string, float. |
| **Photo / Drawing Logs** | media\_id, facing\_direction, scale\_used, subject\_desc, author, date\_captured. | Categorical string, standard date format. |

Given the absence of a universally published static schema and the reliance on transclusion of ARK subforms, the HOARD ingestion engine must not rely on exact string-matching algorithms for column headers.2 It is recommended that HOARD implements an initial semantic mapping layer during Phase 0\. This layer should utilize a lightweight, CPU-bound embedding model to execute cosine similarity matching between the idiosyncratic ARK export headers and HOARD's unified internal ontology.

### **FAIMS 3.0 (Fieldmark) Schema Dynamics and NoSQL Emulation**

FAIMS 3.0, recently rebranded as Fieldmark, represents the apex of modern offline, spatially-aware archaeological data collection systems.4 Supported heavily by the Australian Research Data Commons (ARDC), FAIMS operates on a cross-platform architecture that synchronizes robust offline field data with CouchDB NoSQL server-side datastores.6

Unlike traditional flat-file or purely relational databases common in older geographic information systems (GIS), FAIMS employs a sophisticated Domain-Key Normal Form (DKNF) relational schema designed to perfectly mimic NoSQL key-value stores.7 This architecture permits profound customization of archaeological data models without breaking backend interoperability.7 The FAIMS 3.0 core data structure is virtually represented by four interacting tables:

1. **ArchEntity:** Operates as the primary identifier and metadata anchor for any recorded archaeological element.  
2. **AEntValue:** Contains the specific, granular values associated with the entity.  
3. **AttributeKey:** Defines the specific properties, questions, or metric requirements prompted within the electronic field notebook.  
4. **Vocabulary:** Stores the controlled terminology, drop-down list contents, and standardized glossaries utilized during mobile data capture.7

FAIMS explicitly addresses the historical issue of semantic interoperability (where syntactically similar data possesses ambiguous meaning) by actively mapping its internal project concepts to overarching international ontologies, such as CIDOC-CRM, at the precise moment of data creation.7 Because this ontology mapping occurs in the background, JSON exports from FAIMS 3.0 provide extraordinarily rich, nested hierarchical structures.7

For the HOARD pipeline, the recommended data interchange format when interacting with FAIMS 3.0 must strictly be its native structured JSON API export.6 Attempting to flatten this highly normalized, DKNF NoSQL structure into a traditional CSV format risks severe relational data loss and would force the HOARD Phase 0 module to execute highly complex, error-prone local table joining operations that undermine the pipeline's efficiency.6

While older systems are present, and platforms like OASIS serve as endpoint repositories rather than field collection tools, engineering HOARD to ingest dynamic ARK subform schemas via semantic mapping and FAIMS 3.0 native JSON via hierarchical parsing will capture the vast majority of modern commercial archaeological data flow.

## **Phase 1 Optical and Structural Digitization: State-of-the-Art Landscape (2025-2026)**

Phase 1 of the HOARD pipeline is tasked with extracting high-fidelity machine-readable text, interpreting complex geometric layouts, and parsing dense tabular data from archaeological field sheets. These documents present extreme computer vision challenges: they feature high-noise backgrounds (soil and water staining), diverse historical and modern cursive handwriting, variable illumination, and non-standardized grid layouts containing hand-drawn sketches alongside text. Evaluating the 2026 open-weights model landscape reveals a definitive architectural shift away from isolated, task-specific Convolutional Neural Networks (CNNs) toward unified, multimodal Vision-Language Models (VLMs).

### **Handwritten Text Recognition (HTR): The Shift to Multimodal Architectures**

Historically, Microsoft's trocr-base-handwritten and its larger variants represented the zenith of open-weights handwriting transcription. TrOCR utilized a pure transformer architecture, pairing a Vision Transformer (ViT) encoder with a RoBERTa decoder, and served as the baseline for numerous cultural heritage fine-tunes.8 In specialized historical contexts, such as the digitization of 16th-century Latin manuscripts, augmentation-trained TrOCR ensembles achieved Character Error Rates (CER) as low as 1.60%.10

However, empirical benchmark data spanning 2025 and early 2026 unequivocally demonstrates that specialized HTR models like TrOCR have been entirely superseded by frontier VLMs.11 Models such as DTrOCR achieved a 2.38% CER on the standard IAM benchmark, whereas modern VLMs (including proprietary models like GPT-4o and open-weights variants) regularly achieve CERs below 1.5%.11 More critically for the HOARD pipeline, TrOCR is fundamentally brittle when presented with full-page, unsegmented layouts; it structurally requires pre-segmented, perfectly cropped line images to function accurately, necessitating an entirely separate and resource-heavy segmentation pipeline.13

For the HOARD pipeline in 2026, the definitive recommendation for comprehensive document digitization is datalab-to/chandra-ocr-2.15 Released in March 2026, Chandra OCR 2 is a 4 billion parameter VLM explicitly engineered for complex, layout-aware document extraction.17

Chandra OCR 2 fundamentally alters the extraction paradigm by outputting directly to structured Markdown, HTML, and JSON while intrinsically preserving strict spatial and layout information.15 It exhibits exceptional robustness against degraded historical scripts and varying handwriting styles.15 Crucially for archaeological context sheets, it accurately reconstructs checkbox topologies within forms, eliminating the need for specialized object detection models dedicated solely to checkbox states.15

In benchmark testing, Chandra OCR 2 currently leads the open-weights sector with an 85.9% overall score on the rigorous olmOCR benchmark, systematically outperforming larger models like Gemini 2.5 Flash and earlier iterations of dedicated OCR engines.16 Furthermore, its multilingual capacity extends to 90+ languages, achieving a 77.8% average on top language benchmarks, providing robust utility for international heritage applications.16

Regarding the rigid VRAM constraints, a 4B parameter model loaded in standard FP16 precision requires approximately 8 GB of VRAM, exceeding HOARD's limits.20 However, Chandra OCR 2 is fully compatible with 4-bit quantization (such as GGUF or AWQ formats). When quantized to 4-bit, the model's memory footprint is reduced to approximately 2.8 GB, comfortably fitting within the 6 GB VRAM budget while preserving sufficient memory overhead for image tensor processing and context generation.20

### **Document Layout Analysis and Page Segmentation**

The legacy HOARD design document specified HTRflow for page segmentation. This methodology is now obsolete. The industry trajectory toward end-to-end processing renders isolated segmentation models largely redundant unless highly specific geometry extraction is required.

Should isolated bounding-box generation be necessary, the introduction of YOLO26 in 2026 offers a compelling edge-compute alternative. Utilizing an end-to-end architecture that completely eliminates Non-Maximum Suppression (NMS) post-processing, YOLO26 provides highly accelerated bounding box generation.21 Implementing the novel MuSGD optimizer—a hybrid of SGD and Muon inspired by LLM training—YOLO26 models (particularly the nano or small variants) require under 200 MB of VRAM and operate with extreme latency reductions, running up to 43% faster on CPUs than previous generations.21

However, because Chandra OCR 2 possesses native, highly sophisticated layout awareness (capable of generating over 15 distinct block types with precise bounding coordinates directly in its output), dedicating separate VRAM to a YOLO layout model is architecturally redundant for standard archaeological forms.18 A dedicated segmentation model is only recommended if the pipeline must isolate intricate, non-textual archaeological section drawings, matrix diagrams, or stratigraphy sketches before passing the cropped images to a specialized CAD/vectorization model in Phase 2\.

### **High-Fidelity Tabular Data Parsing**

Archaeological finds catalogues, environmental sample registers, and osteological assessments frequently feature dense, multi-column tabular data. Subtle grid misalignments, borderless columns, or merged cells can entirely destroy data integrity during extraction. The absolute state-of-the-art for this specific task within constrained environments is opendatalab/MinerU2.5-Pro-2604-1.2B.22

Released in April 2026, the MinerU2.5-Pro iteration represents a triumph of data engineering over architectural scaling. It utilizes a highly optimized training pipeline without altering the foundational 1.2 billion parameter architecture of the earlier 2509 variant.23 The developers implemented a "coarse-to-fine" two-stage parsing methodology to resolve inherent structural hallucinations common in VLM table extraction:

1. **Global Layout Analysis:** The model first assesses a heavily downsampled iteration of the document page to establish a macro-structural map of the table geometries.25  
2. **Local Content Recognition:** It subsequently crops native-resolution segments to execute targeted content extraction within the identified table bounds. This elegant approach actively mitigates the quadratic ![][image1] attention mechanism complexity penalty associated with feeding high-resolution image inputs directly into transformer architectures, drastically reducing computational overhead.25

Furthermore, the 2604-Pro iteration was trained using Diversity-and-Difficulty-Aware Sampling, expanding training data to 65.5M samples, and utilized a "Judge-and-Refine" pipeline featuring render-then-verify iterative correction to eliminate structural collapse in complex grids.23 As a result, MinerU2.5-Pro achieved an unprecedented 95.69 overall score on the highly rigorous OmniDocBench v1.6 evaluation.22 It specifically dominates Table Parsing metrics, improving Table TEDS scores by \+5.54 and outperforming massive frontier models with over 200x more parameters.22 At a mere 1.2B parameters, MinerU2.5-Pro occupies roughly 2.4 GB of VRAM in FP16/BF16, making it an extraordinarily potent, lightweight engine for HOARD's catalogue processing.

### **Geometric Distortion Correction**

Archaeological field photography of context sheets is invariably captured under adverse conditions, resulting in severe perspective skew, page curl, and physical warping. PaddleOCR-VL-1.5, a highly efficient 0.9B parameter vision-language model, remains the preeminent lightweight standard for document de-warping and geometric correction.27 It is explicitly trained to target five real-world degradation vectors: severe warping, scanning noise, screen photography moiré patterns, extreme illumination variance, and aggressive skew.27 Utilizing approximately 1.8 GB of VRAM in FP16, it serves as the mandatory preprocessing stage before passing imagery to Chandra or MinerU.

### **Phase 1 VRAM Budget and Sequential Orchestration**

The hard limit of a 6 GB VRAM consumer GPU imposes rigid mathematical boundaries on the Phase 1 pipeline. The aggregate parameter count of the required models (0.9B for PaddleOCR \+ 1.2B for MinerU \+ 4.0B for Chandra \= \~6.1B parameters) equates to over 12 GB of VRAM if loaded simultaneously in FP16 precision. Therefore, the models must be orchestrated strictly sequentially.

The pipeline must execute aggressive memory clearing—utilizing routines analogous to PyTorch's torch.cuda.empty\_cache() and active garbage collection—between the execution of each sub-phase to prevent memory fragmentation and Out-Of-Memory (OOM) failures.

**Proposed Sequential Loading Matrix for 6 GB VRAM Constraints:**

| Sub-Phase | Operation / Task | Recommended Model | Quantization | Est. VRAM Footprint | Post-Execution Action |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **1A** | Geometry & Distortion Correction | PaddleOCR-VL-1.5 | FP16 / BF16 | \~1.8 GB | Purge weights, clear CUDA cache. Retain corrected image arrays in RAM. |
| **1B** | Dense Tabular Extraction (Finds/Samples) | MinerU2.5-Pro-2604-1.2B | FP16 / BF16 | \~2.4 GB | Extract tables to structured Markdown/JSON. Purge weights, clear cache. |
| **1C** | Layout, Handwriting, Checkboxes & Forms | datalab-to/chandra-ocr-2 | 4-bit (GGUF/AWQ) | \~2.8 GB | Process complex layouts and handwritten narrative fields. Purge weights. |

By enforcing this strict sequential loading paradigm, the peak absolute VRAM utilization during any individual Phase 1 operation never exceeds 3.5 GB (accounting for base weights, inference context, and intrinsic CUDA overhead). This methodology leaves a comfortable 2.5 GB buffer, entirely immunizing the 6 GB consumer hardware against OOM threshold breaches.

## **Phase 3 Synthesis and Drafting: SLMs in Constrained Environments**

Phase 3 of the HOARD pipeline represents the cognitive core of the system. The designated Language Model must ingest massive contextual arrays—often comprising hundreds of digitized context records, tabular finds entries, stratigraphic relationships, and photographic descriptions—and execute deep logical reasoning to generate a structurally compliant, highly coherent Markdown grey literature draft.

### **Evaluating Model Parameters and Quantization Dynamics**

Operating within a 6 GB VRAM boundary requires precise parameterization. VRAM must accommodate the quantized model weights, the dynamic Key-Value (KV) cache generated during inference, and baseline operational overhead.

Deploying a 7B parameter class model (e.g., Llama-3-8B or Mistral variants) in this environment is mathematically prohibitive for long-context tasks. Even heavily quantized to 3-bit (e.g., Q3\_K\_M), a 7B model occupies approximately 3.3 GB of VRAM. Attempting to process a comprehensive site dataset of 30,000 to 50,000 tokens generates a colossal KV cache. In standard multi-head attention transformer architectures, this KV cache would consume an additional 2.5 GB to 4.0 GB of VRAM, instantly exceeding the 6 GB limit and triggering catastrophic system failure or defaulting to unacceptably slow CPU offloading.

Conversely, 3B to 4B parameter class models represent the optimal nexus of capability and efficiency. A 4B parameter model quantized to 4-bit (e.g., Q4\_K\_M) occupies approximately 2.4 GB to 2.6 GB of VRAM.28 This footprint preserves roughly 3.4 GB of residual VRAM strictly dedicated to the KV cache and context processing. Modern 4B models universally utilize Grouped Query Attention (GQA), an architectural innovation that drastically reduces the size of the KV cache by allowing multiple query heads to share a single key-value head.29

### **State-of-the-Art 4B Reasoning Models (2025-2026)**

The landscape of Small Language Models (SLMs) has undergone radical capability enhancements via sophisticated teacher-distillation techniques, high-quality synthetic training datasets, and advanced post-training Reinforcement Learning from Human Feedback (RLHF) regimens.30 Three primary candidates dominate the 2026 open-weights sector:

1. **Qwen/Qwen3-4B-Instruct-2507 and Variants:** The Qwen3 series remains the definitive zenith of the 4B parameter class. Natively supporting an extraordinary 262,144-token context window, it excels in complex instruction following and strict structural formatting.29 A profound recent evolution is the introduction of Qwen3-4B-Thinking-2507. This variant integrates a "thinking mode" that forces extended, multi-step chain-of-thought processing before generating a final output.29 For archaeological synthesis—where the model must correctly interpret complex stratigraphic superpositions (Harris Matrices) and correlate disparate artifact typologies across multiple trenches—the Thinking variant demonstrates massive benchmark gains (e.g., AIME25 improvements from 65.6 to 81.3, and GPQA improvements from 55.9 to 65.8) over the standard instruct model.29  
2. **microsoft/Phi-4-mini-instruct:** Operating at 3.8B parameters and supporting a 128k context window, Phi-4-mini is engineered on dense, high-quality synthetic data, yielding exceptional mathematical and abstract logic capabilities.28 However, independent evaluations indicate that while highly performant in isolated logic tasks, it occasionally struggles with maintaining consistent structural adherence in multi-page document generation and complex JSON/Markdown formatting compared to the Qwen3 architecture.34  
3. **google/gemma-3-4b-it:** Released with multi-modal capabilities and a 128k context limit, Gemma 3 4B provides robust vision-text integration.28 Yet, it is computationally denser in its attention mechanisms, often resulting in higher KV cache footprints and slightly lower performance in raw long-horizon reasoning tasks compared to Qwen3.28

**Definitive Recommendation:** The optimal selection for Phase 3 document drafting is **Qwen/Qwen3-4B-Thinking-2507** (utilizing the standard Instruct variant only if generation latency must be strictly prioritized over reasoning depth). The model's integration of a 262k context window alongside a 1:4 Grouped Query Attention ratio (32 Query heads, 8 KV heads) allows for highly efficient, massive context scaling.29

While specific academic or heritage-focused fine-tunes in the 4B range are absent from the current HuggingFace repository, Qwen3's base capability in technical document generation and Markdown structuring renders domain-specific fine-tuning unnecessary for initial deployment.

### **Context Length Feasibility and Optimization Mechanics**

**Context Window Mathematical Projection:**

Utilizing a 4-bit Q4\_K\_M quantization of Qwen3-4B requires \~2.6 GB VRAM. Assuming an absolute ceiling of 6.0 GB, approximately 3.4 GB of VRAM remains dedicated to the KV cache. Because Qwen3 utilizes GQA, the memory requirement per token is vastly diminished compared to standard multi-head attention. Empirical projections indicate that a 6 GB consumer GPU running llama.cpp or a comparable highly optimized inference engine can comfortably support a contiguous context window of **65,000 to 85,000 tokens** before encountering Out-Of-Memory errors. This capacity is exceptionally large, providing sufficient headroom to ingest the entirety of digitized context sheets, specialist catalogues, and field notes for a standard to medium-sized commercial archaeological evaluation simultaneously.

**Inference Optimization Strategies:**

To maximize the utility of the 6 GB environment, specific inference configurations are vital:

* **Prompt Caching (KV Caching):** Because the HOARD pipeline likely processes iterative drafts or requires multiple sequential inference calls against the same static dataset (e.g., querying the ingested context data multiple times to draft different report sections), caching the pre-computed KV states of the base prompt will drastically reduce Time-To-First-Token (TTFT) and eliminate redundant computational overhead on subsequent passes.  
* **Speculative Decoding Rejection:** While theoretically capable of accelerating text generation, employing speculative decoding in a rigid 6 GB environment is highly discouraged. Speculative decoding requires simultaneously loading a smaller "draft" model (e.g., a 0.5B model) alongside the target 4B model. The draft model's weights and its independent KV cache consume vital VRAM, severely diminishing the maximum available context window for the primary archaeological dataset. Within edge-compute boundaries, maximizing context length must take absolute precedence over generation speed.

## **Phase 4 Compliance Refinement: Jurisdiction Standards Updates (2025-2026)**

Phase 4 of the HOARD pipeline serves as the regulatory enforcer. It restructures the generated Markdown text to conform to the strict stylistic conventions, mandated terminologies, and sectional hierarchies demanded by specific national and regional heritage authorities. Maintaining these templates requires continuous monitoring of international policy shifts. A comprehensive audit of regulatory platforms across 12 major jurisdictions for the period of 2025–2026 reveals critical, highly specific updates in England, the Netherlands, and Ontario, Canada.

### **Jurisdictional Policy Revisions and Pipeline Implications**

#### **1\. England: Historic England (MoRPHE and Guidelines)**

Historic England has focused its 2025 and 2026 guidance updates heavily on climate adaptation, decarbonization, and environmental preservation methodologies.36

* **Updates:** A newly revised "Environmental Archaeology" guidance framework was formally published on 20 December 2025\.36 This revision alters the expected reporting conventions surrounding the recovery, sampling strategies, and post-excavation assessment of palaeoenvironmental and archaeobotanical evidence. Concurrently, updated guidance on "Managing Archaeology in London" was published on 18 February 2026, directly impacting the Greater London Archaeology Advisory Service (GLAAS) reporting standards.36 Furthermore, protocols regarding "Waterlogged Wood" were revised in December 2025\.36  
* **Pipeline Implication:** HOARD's England (CL3 Evaluation/CL4 Excavation) templates must be amended to incorporate expanded mandatory headings for environmental sampling strategies. The compliance engine must integrate updated nomenclature reflecting the December 2025 environmental guidance, specifically flagging archaic terminology regarding waterlogged artifact conservation.

#### **2\. Netherlands: KNA 5.0 (Kwaliteitsnorm Nederlandse Archeologie)**

The Dutch archaeological sector is currently executing a profound regulatory shift with the development and incremental deployment of KNA 5.0.37

* **Updates:** The KNA 5.0 restructuring is designed to modernize the rigid, linear protocols of earlier iterations (such as BRL SIKB 4000\) into a highly flexible, modular digital system.37 While the core system architecture was targeted for finalization by late 2024, specific modular guidelines have continued to evolve into 2026\. Crucially, on 26 March 2026, the *KNA Leidraden voor Karterend Booronderzoek en Proefsleuvenonderzoek* (Guidelines for Coring and Trial Trenching) were officially renewed and published.37  
* **Pipeline Implication:** The HOARD templates for Dutch trial trenching (*proefsleuvenonderzoek*) and coring must be rigorously audited against the March 2026 Leidraad. The overarching transition to KNA 5.0 emphasizes a modular reporting approach, requiring HOARD to employ dynamic structuring of the report document rather than relying on a fixed, monolithic hierarchical template.

#### **3\. Canada: Ontario (MCM Standards and Guidelines)**

The Ministry of Citizenship and Multiculturalism (MCM) in Ontario proposed highly specific, targeted alterations to the 2011 *Standards and Guidelines for Consultant Archaeologists* in early 2026, framed within the broader Heritage Framework Transformation initiative.38 The draft standards were posted to the Environmental Registry of Ontario (ERO 026-0216) on March 6, 2026, for a 30-day consultation period.39

* **Updates:**  
  * **Limited Assessments:** Introduction of entirely new Stage 1 and Stage 2 requirements that explicitly standardize how "limited assessments" (the assessment of only a specific portion of a larger property) are conducted, mapped, and reported.40  
  * **Partial Clearance & Buffers:** A newly mandated 50-meter buffer must be explicitly applied, documented, and justified around archaeological sites during partial clearance processes to permit adjacent development.40  
  * **Mandated Recommendations Phrasing:** Revisions to Section 7.9.4 now strictly prescribe the *exact specific language* that Licensed Consultant Archaeologists (LCAs) must utilize when drafting recommendations for the protection of archaeological sites progressing to Stage 4 mitigation.41  
  * **Site Update Forms:** A new administrative standard dictates that an official site update form must be submitted to the Ministry following any Stage 2 inspection, regardless of whether a previously known site was successfully relocated during the fieldwork.41  
* **Pipeline Implication:** HOARD's Phase 4 compliance logic for Ontario must be updated to forcefully enforce the new exact-phrase text strings for Stage 4 recommendations. Any deviation from the prescribed ERO text must trigger a high-priority compliance failure. Furthermore, the logic must flag spatial reporting checks if partial clearance documentation fails to explicitly define a 50m site buffer.

#### **4\. Australia: Burra Charter (ICOMOS)**

* **Updates:** The fundamental Burra Charter, governing cultural heritage management in Australia, was last formally updated in 2013, with substantial 40th-anniversary evaluations occurring in 2019\.42 While Australia ICOMOS published various volumes of the *Historic Environment* journal exploring resilience and indigenous concerns through 2023–2025, there is no evidence of a foundational regulatory revision to the core Practice Notes or the Charter itself during the 2025–2026 window.43 The 2013 framework remains the active compliance standard.

### **Comprehensive Jurisdiction Status Matrix (2025–2026)**

| Jurisdiction | Authority / Standard | Status (2025–2026) | Specific Modifications & Requirements | Confidence |
| :---- | :---- | :---- | :---- | :---- |
| **England** | Historic England (MoRPHE / GLAAS) | **Updated** | Revisions to *Environmental Archaeology* (Dec 2025), *Waterlogged Wood* (Dec 2025), and *Managing Archaeology in London* (Feb 2026). Requires targeted nomenclature and structural updates for environmental sampling. | High |
| **Netherlands** | SIKB (KNA 5.0) | **Updated** | *KNA Leidraden* for Coring and Trenching formally renewed (March 26, 2026). Demands a shift toward modular reporting structures rather than static templates. | High |
| **Canada (Ontario)** | MCM (Standards & Guidelines) | **Updated** | ERO draft 026-0216 (March 6, 2026\) mandates exact specific phrasing for Stage 4 recommendations, dictates strict 50m partial clearance buffers, and introduces new rules for Limited Assessments. | High |
| **Australia** | Burra Charter (ICOMOS) | No change confirmed | Practice notes and the core charter remain strictly governed by the 2013 revisions and 2019 frameworks. | High |
| **Scotland** | Historic Environment Scotland (DSR) | No change confirmed | No major standard revisions or updates to Data Structure Reports detected in the current policy dataset. | Medium |
| **Wales** | Cadw / RCAHMW | No change confirmed | No major standard revisions detected in the current policy dataset. | Medium |
| **Ireland** | National Monuments Service | No change confirmed | No major standard revisions to Section 26 reporting requirements detected in the current policy dataset. | Medium |
| **France** | INRAP / Code du Patrimoine | No change confirmed | No major regulatory revisions detected in the current policy dataset. | Medium |
| **Germany** | Landesdenkmalpflege | No change confirmed | No major Lander-specific standard revisions detected in the current policy dataset. | Medium |
| **United States** | Section 106 / ACHP / NPS | No change confirmed | No major standard revisions to NRHP eligibility reporting detected in the current policy dataset. | Medium |
| **New Zealand** | Heritage NZ Pouhere Taonga | No change confirmed | No major standard revisions detected in the current policy dataset. | Medium |
| **South Africa** | SAHRA (NHRA) | No change confirmed | No major amendments to the National Heritage Resources Act reporting requirements detected. | Medium |

## **Strategic Directives and Engineering Mandates**

The architectural formulation of the HOARD pipeline within a rigid 6 GB VRAM local, edge-compute environment is not only theoretically viable but practically achievable utilizing the sophisticated 2026 open-weights model landscape. Success relies entirely on aggressive sequential memory orchestration and the abandonment of monolithic, heavy-parameter legacy networks in favor of specialized, highly-engineered architectures.

Phase 0 ingestion logic must abandon static column-mapping paradigms due to the dynamic, highly normalized nature of modern field recording systems. The reliance on ARK's EAV subforms and FAIMS 3.0's DKNF JSON APIs requires implementing a lightweight semantic embedding layer to autonomously map bespoke field column structures to HOARD's unified internal ontology.

Phase 1 multimodal digitization must entirely phase out legacy models like TrOCR and HTRflow. The pipeline should sequentially orchestrate PaddleOCR-VL-1.5 for geometric distortion correction, MinerU2.5-Pro-2604-1.2B for high-fidelity tabular data extraction, and the 4B parameter Chandra OCR 2 model (via 4-bit GGUF/AWQ quantization) for holistic layout awareness, handwriting transcription, and checkbox interpretation. This sequential execution, punctuated by aggressive VRAM purging, ensures peak memory loads never exceed 3.5 GB, immunizing the system against OOM failures.

Phase 3 semantic drafting operates at the absolute mathematical limits of a consumer GPU. Deploying the 4-bit quantized Qwen3-4B-Thinking-2507 leverages Grouped Query Attention to preserve up to 3.4 GB of VRAM exclusively for the KV cache. This affords an operational context window of roughly 65,000 to 85,000 tokens, representing the optimal nexus of deep logical reasoning and volume data ingestion required for archaeological synthesis. The implementation of speculative decoding must be avoided to protect this vital context space.

Finally, Phase 4 structural compliance must be immediately patched to reflect the early 2026 shifts in global heritage policy. The pipeline must accommodate Historic England's revised environmental protocols, the Netherlands' KNA 5.0 modular coring updates, and the highly specific, string-matching semantic requirements introduced by Ontario's Ministry of Citizenship and Multiculturalism regarding partial clearances and mandated recommendation phrasing. Executing this meticulous orchestration ensures HOARD maintains its zero-API, local-first mandate without sacrificing state-of-the-art archaeological interpretation or jurisdictional validity.

#### **Works cited**

1. archaeological documentation as a service. archaeological information systems in the cloud era: the bradypus case-study, accessed May 13, 2026, [https://www.archcalc.cnr.it/indice/PDF33.2/07\_Bogdani.pdf](https://www.archcalc.cnr.it/indice/PDF33.2/07_Bogdani.pdf)  
2. The Archaeological Recording Kit: An open source solution to project recording | PDF \- Slideshare, accessed May 13, 2026, [https://www.slideshare.net/slideshow/the-archaeological-recording-kit-an-open-source-solution-to-project-recording/12271405](https://www.slideshare.net/slideshow/the-archaeological-recording-kit-an-open-source-solution-to-project-recording/12271405)  
3. ARK, accessed May 13, 2026, [https://ark.lparchaeology.com/](https://ark.lparchaeology.com/)  
4. About the FAIMS 3.0 Project, accessed May 13, 2026, [https://faims.edu.au/about/](https://faims.edu.au/about/)  
5. Fieldmark™ Electronic Field Notebooks | ARDC \- Australian Research Data Commons, accessed May 13, 2026, [https://ardc.edu.au/project/faims-3-0/](https://ardc.edu.au/project/faims-3-0/)  
6. FAIMS 3 ELABORATION REPORT \- LaTeX Typesetting, accessed May 13, 2026, [https://www.latextypesetting.com/examples/faims\_report/elaboration\_report.pdf](https://www.latextypesetting.com/examples/faims_report/elaboration_report.pdf)  
7. Arbitrary Offline Data Capture on All of Your Androids: The FAIMS Mobile Platform \- OSF, accessed May 13, 2026, [https://osf.io/download/brxg7](https://osf.io/download/brxg7)  
8. Enhancing Transformer-Based Language Models for Hungarian Handwritten Text Recognition \- F1000Research, accessed May 13, 2026, [https://f1000research.com/articles/15-181/pdf](https://f1000research.com/articles/15-181/pdf)  
9. Enhancing Transformer-Based Language Models for Hungarian Handwritten Text Recognition. \- F1000Research, accessed May 13, 2026, [https://f1000research.com/articles/15-181](https://f1000research.com/articles/15-181)  
10. \[2508.11499\] Handwritten Text Recognition of Historical Manuscripts Using Transformer-Based Models \- arXiv, accessed May 13, 2026, [https://arxiv.org/abs/2508.11499](https://arxiv.org/abs/2508.11499)  
11. Best Handwriting OCR 2026: GPT, Claude, Gemini and TrOCR Compared | CodeSOTA, accessed May 13, 2026, [https://codesota.com/ocr/best-for-handwriting](https://codesota.com/ocr/best-for-handwriting)  
12. Updated 2025 Review: My notes on the best OCR for handwriting recognition and text extraction : r/computervision \- Reddit, accessed May 13, 2026, [https://www.reddit.com/r/computervision/comments/1mbpab3/updated\_2025\_review\_my\_notes\_on\_the\_best\_ocr\_for/](https://www.reddit.com/r/computervision/comments/1mbpab3/updated_2025_review_my_notes_on_the_best_ocr_for/)  
13. Evaluating Visual-Language Models for Handwritten Text Recognition on Historical Swedish Manuscripts \- Diva Portal, accessed May 13, 2026, [http://uu.diva-portal.org/smash/record.jsf?pid=diva2:1969262](http://uu.diva-portal.org/smash/record.jsf?pid=diva2:1969262)  
14. Evaluating Visual-Language Models for Handwritten Text Recognition on Historical Swedish Manuscripts \- Diva-Portal.org, accessed May 13, 2026, [https://www.diva-portal.org/smash/get/diva2:1969262/FULLTEXT01.pdf](https://www.diva-portal.org/smash/get/diva2:1969262/FULLTEXT01.pdf)  
15. datalab-to/chandra-ocr-2 \- Hugging Face, accessed May 13, 2026, [https://huggingface.co/datalab-to/chandra-ocr-2](https://huggingface.co/datalab-to/chandra-ocr-2)  
16. GitHub \- datalab-to/chandra: OCR model that handles complex tables, forms, handwriting with full layout., accessed May 13, 2026, [https://github.com/datalab-to/chandra](https://github.com/datalab-to/chandra)  
17. Chandra OCR 2: The Open-Source Model That Reads What Others Can't \- Towards AI, accessed May 13, 2026, [https://pub.towardsai.net/chandra-ocr-2-the-open-source-model-that-reads-what-others-cant-6a218faa0efd](https://pub.towardsai.net/chandra-ocr-2-the-open-source-model-that-reads-what-others-cant-6a218faa0efd)  
18. Announcing Chandra OCR 2: 90+ Languages, Top Benchmarks \- Datalab, accessed May 13, 2026, [https://www.datalab.to/blog/chandra-2](https://www.datalab.to/blog/chandra-2)  
19. datalab-to/chandra \- Hugging Face, accessed May 13, 2026, [https://huggingface.co/datalab-to/chandra](https://huggingface.co/datalab-to/chandra)  
20. fredrezones55/chandra-ocr-2 \- Ollama, accessed May 13, 2026, [https://ollama.com/fredrezones55/chandra-ocr-2](https://ollama.com/fredrezones55/chandra-ocr-2)  
21. Ultralytics YOLO26, accessed May 13, 2026, [https://docs.ultralytics.com/models/yolo26/](https://docs.ultralytics.com/models/yolo26/)  
22. opendatalab/MinerU2.5-Pro-2604-1.2B \- Hugging Face, accessed May 13, 2026, [https://huggingface.co/opendatalab/MinerU2.5-Pro-2604-1.2B](https://huggingface.co/opendatalab/MinerU2.5-Pro-2604-1.2B)  
23. MinerU2.5-Pro: Pushing the Limits of Data-Centric Document Parsing at Scale \- arXiv, accessed May 13, 2026, [https://arxiv.org/html/2604.04771v1](https://arxiv.org/html/2604.04771v1)  
24. MinerU2.5-Pro: Pushing the Limits of Data-Centric Document Parsing at Scale \- arXiv, accessed May 13, 2026, [https://arxiv.org/abs/2604.04771](https://arxiv.org/abs/2604.04771)  
25. \[2509.22186\] MinerU2.5: A Decoupled Vision-Language Model for Efficient High-Resolution Document Parsing \- arXiv, accessed May 13, 2026, [https://arxiv.org/abs/2509.22186](https://arxiv.org/abs/2509.22186)  
26. MinerU-Diffusion: A New Approach to OCR via Diffusion Decoding Speeds Up PDF Parsing 3× Without Accuracy Loss, accessed May 13, 2026, [https://neurohive.io/en/state-of-the-art/mineru-diffusion-a-new-approach-to-ocr-via-diffusion-decoding-speeds-up-pdf-parsing-3-without-accuracy-loss/](https://neurohive.io/en/state-of-the-art/mineru-diffusion-a-new-approach-to-ocr-via-diffusion-decoding-speeds-up-pdf-parsing-3-without-accuracy-loss/)  
27. GitHub \- PaddlePaddle/PaddleOCR: Turn any PDF or image document into structured data for your AI. A powerful, lightweight OCR toolkit that bridges the gap between images/PDFs and LLMs. Supports 100+ languages., accessed May 13, 2026, [https://github.com/PADDLEPADDLE/PADDLEOCR](https://github.com/PADDLEPADDLE/PADDLEOCR)  
28. 15 Best Lightweight Language Models Worth Running in 2026 \- Prem AI, accessed May 13, 2026, [https://blog.premai.io/best-lightweight-language-models-worth-running/](https://blog.premai.io/best-lightweight-language-models-worth-running/)  
29. Qwen/Qwen3-4B-Thinking-2507 \- Hugging Face, accessed May 13, 2026, [https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507](https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507)  
30. The Best Open-Source Small Language Models (SLMs) in 2026 \- BentoML, accessed May 13, 2026, [https://www.bentoml.com/blog/the-best-open-source-small-language-models](https://www.bentoml.com/blog/the-best-open-source-small-language-models)  
31. Qwen3 Technical Report \- arXiv, accessed May 13, 2026, [https://arxiv.org/html/2505.09388v1](https://arxiv.org/html/2505.09388v1)  
32. Qwen3 is the large language model series developed by Qwen team, Alibaba Cloud. \- GitHub, accessed May 13, 2026, [https://github.com/QwenLM/qwen3](https://github.com/QwenLM/qwen3)  
33. Cross-Lingual Bimodal Emotion Recognition with LLM-Based Label Smoothing \- MDPI, accessed May 13, 2026, [https://www.mdpi.com/2504-2289/9/11/285](https://www.mdpi.com/2504-2289/9/11/285)  
34. iPhone / Mobile benchmarking of popular tiny LLMs : r/LocalLLM \- Reddit, accessed May 13, 2026, [https://www.reddit.com/r/LocalLLM/comments/1om7jbq/iphone\_mobile\_benchmarking\_of\_popular\_tiny\_llms/](https://www.reddit.com/r/LocalLLM/comments/1om7jbq/iphone_mobile_benchmarking_of_popular_tiny_llms/)  
35. Tiny LLM Benchmark Showdown: 7 models tested on 50 questions with Galaxy S25U, accessed May 13, 2026, [https://www.reddit.com/r/LocalLLM/comments/1pe65bx/tiny\_llm\_benchmark\_showdown\_7\_models\_tested\_on\_50/](https://www.reddit.com/r/LocalLLM/comments/1pe65bx/tiny_llm_benchmark_showdown_7_models_tested_on_50/)  
36. Latest Advice and Guidance | Historic England, accessed May 13, 2026, [https://historicengland.org.uk/advice/find/latest-guidance/](https://historicengland.org.uk/advice/find/latest-guidance/)  
37. KNA 5.0 \- SIKB, accessed May 13, 2026, [https://www.sikb.nl/archeologie/kennisdelen-en-innovatie/kna-5-0](https://www.sikb.nl/archeologie/kennisdelen-en-innovatie/kna-5-0)  
38. Digging into Change: Ontario Proposes Updates to Archaeological Assessment Standards, accessed May 13, 2026, [https://davieshowe.com/digging-into-change-ontario-proposes-updates-to-archaeological-assessment-standards/](https://davieshowe.com/digging-into-change-ontario-proposes-updates-to-archaeological-assessment-standards/)  
39. Heritage Framework Transformation: Proposals related to Ontario's Archaeology Program, including targeted changes to the Standards and Guidelines for Consultant Archaeologists | Environmental Registry of Ontario, accessed May 13, 2026, [https://ero.ontario.ca/notice/026-0216](https://ero.ontario.ca/notice/026-0216)  
40. Proposed Amendments to the Standards and Guidelines for Consultant Archaeologists \- eSCRIBE Published Meetings, accessed May 13, 2026, [https://pub-kawarthalakes.escribemeetings.com/filestream.ashx?DocumentId=89239](https://pub-kawarthalakes.escribemeetings.com/filestream.ashx?DocumentId=89239)  
41. Summary of Updates to the Standards and Guidelines for Consultant Archaeologists, accessed May 13, 2026, [https://ero.ontario.ca/public/2026-03/Summary%20of%202026%20Updates%20to%20the%20Standards%20and%20Guidelines%20for%20Consultant%20Archaeologists.pdf](https://ero.ontario.ca/public/2026-03/Summary%20of%202026%20Updates%20to%20the%20Standards%20and%20Guidelines%20for%20Consultant%20Archaeologists.pdf)  
42. Burra Charter & Practice Notes | Australia ICOMOS, accessed May 13, 2026, [https://australia.icomos.org/publications/burra-charter-practice-notes/](https://australia.icomos.org/publications/burra-charter-practice-notes/)  
43. Burra Charter Archival Documents | Australia ICOMOS, accessed May 13, 2026, [https://australia.icomos.org/publications/burra-charter-practice-notes/burra-charter-archival-documents/](https://australia.icomos.org/publications/burra-charter-practice-notes/burra-charter-archival-documents/)  
44. Australia ICOMOS Burra Charter Series, accessed May 13, 2026, [https://australia.icomos.org/resources/burra-charter-series/](https://australia.icomos.org/resources/burra-charter-series/)  
45. Historic Environment Vol 35 number 3 2023 (2025) \- Australia ICOMOS, accessed May 13, 2026, [https://australia.icomos.org/publications/historic-environment/historic-environment-vol-35-number-3-2023-2025/](https://australia.icomos.org/publications/historic-environment/historic-environment-vol-35-number-3-2023-2025/)  
46. Historic Environment Vol 35 number 2 2023 (2025) \- Australia ICOMOS, accessed May 13, 2026, [https://australia.icomos.org/publications/historic-environment-vol-35-number-2-2023-2025/](https://australia.icomos.org/publications/historic-environment-vol-35-number-2-2023-2025/)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADQAAAAZCAYAAAB+Sg0DAAAC0UlEQVR4Xu2XS+hNURjFP+VNJJGEiUdGTBBFXikDKUUoUWTgkfIYeaSURwmFiWd5lCIMJEWSvDNRJAND7+QxkJBYq2/ve/d/3XP/556/e28G91erzv7WPnufs8+3H8esRVMYBt2D7kPLxWs6q6GbGizAQuh5Un4KPUnKnaAbSblmHkNLwvUk6Dv0GjoBjYyVhInQW2iQGgWYDf1Jyneg90mZsP11EmuXTdB+qDN0GHoJvTHviPpcrlpiIPTKCnaUQz/zgbyiBvgJDdWg0hM6B/0K19egh1CP4DOd4ksp+6BPVq6rHLPyval+QL2Seim7oW/QODXMv9pJDaYsNu9gTyjz+lDZLjHd3GMapjA2QWJZPLDsAVE4j8ZoMGG4eTs71Yh8hN5BvUOZnzprrgwxb2iexDnSXSWm9IV+W/4LMTumJOUzyXUKp8FtDUbYydZw3d+yPzPpYl53psS5zOYx1/zeL2oITPttiS61tUtcMB/I7mp0M+9ohBoZ8GW1bh+rPoopB8zvvahGAvedOL+islKf7DL3x6rByX5dg1VYaZUpw/m0Q2IK0zc+YFYqd4Rl5u3NV+MgdEuDVbhslS80A9ooMWWV+X1c2uvFHPM2OchtOAp90GAGPJKwgUcS5xfaIjHlvPm9x9UIPNNADXBhYpsr1ODSR2OwGsIp80k4XuKjoL0SU7gZZ3Ye4HwoSpxvC9RYG4z2RnmWeR2eIhQuFEc0KMT5M1oN82Wa+0pR1pu3yWerIHbIdZ17TYQ7/2ZoexLL4qsGBLbNYxRhm5OhRdCL4HWEu+b7ZyZXrfxSPG7wREsxVXjizYP3MfVSloZ4nnhkKgr3Qz7naTUiPJZvsPIhlJW5ojE/6eXB8x9ToFlw4+dzTlWjXpy12r5kveCZM/1vagicI/y5q+WL/iv8T2LaNRR2wN/mNWrUmWnQAA02Cm6+/EVoFDw38m+6RYv/gb8HvKyYG+yiigAAAABJRU5ErkJggg==>