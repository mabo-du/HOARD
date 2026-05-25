# **HOARD Phase 1: Multi-Modal Digitisation Architecture and Implementation Strategy**

The operationalization of the Heritage Observation And Report Drafter (HOARD) relies intrinsically on the fidelity and resilience of its Phase 1 multi-modal digitisation pipeline. The central objective of this phase is the translation of complex, unstructured, and visually degraded archaeological field data—including handwritten context sheets, dot-matrix printed finds catalogues, and interpretative field sketches—into highly structured, schema-compliant JSON formats. Given the hardware constraints of a 6–8 GB VRAM consumer GPU (specifically targeting the RTX 3070 mobile architecture), the pipeline must balance high-precision extraction with aggressive, deterministic memory management.  
In the temporal context of May 2026, the landscape of Vision-Language Models (VLMs) has shifted dramatically. The industry has moved away from cascaded Optical Character Recognition (OCR) systems—where layout detection, text recognition, handwriting transcription (HTR), and reading order were handled by distinct, pipelined architectures—toward monolithic, unified end-to-end models capable of performing all these tasks in a single pass. This research report provides an exhaustive evaluation of the current state of the art in compact VLMs, presenting a comprehensive architectural blueprint for Phase 1\. The analysis rigorously examines model selection, optimal memory routing protocols, strict schema enforcement for structured JSON output, and the deterministic image pre-processing fallbacks required to digitize heavily degraded archaeological materials.

## **The Paradigm Shift in Document Extraction (May 2026\)**

Historically, digitizing complex forms required a multi-stage process: a vision model (such as YOLO or LayoutLM) would detect bounding boxes, an OCR engine (like Tesseract or PaddleOCR) would extract printed text, and specialized HTR models would attempt to transcribe handwriting within segmented zones. This approach was highly brittle. In the context of archaeological context sheets, where a field archaeologist's cursive handwriting frequently spills across bounding box lines, overlaps with checkboxes, or integrates with stratigraphic sketches, cascaded models routinely failed.  
By May 2026, the paradigm has firmly shifted toward unified Vision-Language Models. These architectures treat document parsing as a holistic vision-language task, enabling the model to read text while simultaneously reasoning over the document layout, hierarchical structure, and visual semantics.1 This evolution allows a single inference pass to extract printed text, interpret handwritten nuances, evaluate the status of checkboxes, and map these disparate elements into a cohesive data structure. However, this advancement introduces new computational demands, necessitating a rigorous evaluation of the available models against the rigid 8 GB VRAM constraint and the open-source licensing mandates of the HOARD project.

## **Comprehensive Evaluation of Model Candidates**

The selection of the primary extraction engine for Phase 1 requires analyzing the latest sub-10-billion parameter models. The evaluation criteria include parameter count, 4-bit quantized VRAM footprint, licensing encumbrances (strictly requiring Apache 2.0, MIT, or compatible licenses for commercial distribution), and empirical performance on complex document understanding tasks such as olmOCR and OmniDocBench.

### **GLM-OCR**

GLM-OCR has emerged as a highly optimized, 0.9-billion parameter compact multimodal model specifically engineered for real-world document understanding.3 Architecturally, it achieves a powerful balance by integrating a 0.4-billion parameter CogViT visual encoder with a 0.5-billion parameter GLM language decoder.3 A critical mathematical and architectural innovation within GLM-OCR is its Multi-Token Prediction (MTP) mechanism. Traditional autoregressive decoding is highly inefficient for deterministic OCR tasks; the MTP mechanism mitigates this by predicting multiple tokens per step. This significantly improves decoding throughput while maintaining a minimal memory overhead through shared parameters.3  
From a licensing perspective, the GLM-OCR model weights are distributed under the MIT License, while the integration code relies on the Apache 2.0 License.4 This dual-license structure ensures complete compliance with HOARD’s commercial distribution requirements. The model excels at structured information extraction, particularly for forms and documents requiring schema adherence. When prompted with a strict JSON schema, the GLM-OCR core implicitly attends to relevant visual regions without requiring explicit, pre-calculated layout cropping.5 Performance metrics indicate an exceptional score of 94.62 on the OmniDocBench V1 evaluation.6  
Operating efficiently through the Ollama runtime, the model occupies approximately 2.2 GB of VRAM.7 However, deploying GLM-OCR requires careful context management. Standard Ollama deployments default to a 4096-token context window, which is insufficient for high-resolution image encoding. Attempting to process complex images without adjusting this parameter results in a GGML\_ASSERT crash during tensor multiplication.7 The context window parameter (num\_ctx) must be explicitly overridden and set to a minimum of 16384 tokens to ensure stable vision processing.7

### **Chandra OCR 2**

Released by Datalab, Chandra OCR 2 is a 4-billion parameter vision-language model that represents a significant distillation and improvement over its 9-billion parameter predecessor.8 It achieves a state-of-the-art score of 85.9% on the independent olmOCR benchmark, surpassing models significantly larger in scale and establishing itself as a premier model for document digitization.9 The architecture is uniquely proficient at interpreting complex mathematical structures, retaining complex layout formatting across wide documents, and demonstrating exceptional accuracy in cursive handwriting recognition.10 This last feature is highly relevant for archaeological context sheets.  
Despite its technical superiority and its proven ability to reconstruct forms accurately (including checkboxes) 10, Chandra OCR 2 presents a critical licensing vulnerability for the HOARD project. While the repository code is licensed under Apache 2.0, the model weights operate under a Modified OpenRAIL-M license.9 This specific license introduces revenue caps (restricting free commercial use to entities with under $2M in revenue) and necessitates commercial negotiations for broader self-hosting.9 Because the HOARD pipeline mandates open-source compatibility (Apache 2.0, MIT, BSD) to allow unencumbered distribution to archaeological units of varying sizes, Chandra OCR 2 violates the fundamental architectural constraints and cannot be adopted as the primary extraction engine.

### **Granite-Docling-258M and the Docling Framework**

The Docling project, developed jointly by IBM and MIT, has evolved into a cornerstone toolkit for structured document parsing. Recently, the project introduced Granite-Docling-258M—an ultra-compact, 258-million parameter VLM designed specifically for high-fidelity document-to-text conversion.12 Released under the Apache 2.0 license, this model replaces earlier iterations (such as the SmolDocling preview) by integrating a modernized SigLIP2 visual encoder and a Granite 165M language backbone.13  
The model is purposefully built to interface directly with the Docling library. It explicitly avoids the pitfalls of general-purpose image understanding models by focusing exclusively on structural layout, cross-page tables, equations, and complex hierarchical lists.14 Docling utilizes an internal layout model (Heron) to segment the document before applying the VLM to complex regions, outputting highly structured JSON, Markdown, or HTML.12  
The integration of Granite-Docling-258M resolves a significant friction point in previous technical designs of the HOARD pipeline. Historically, complex cross-page table parsing (essential for Finds Catalogues) relied on the MinerU 1.2B model. However, MinerU is distributed under the AGPL-3.0 license.15 The AGPL-3.0 license acts as a viral, "copyleft" mandate, requiring that any dependent software interacting over a network must also release its source code under identical terms. For commercial Cultural Resource Management (CRM) applications utilizing the HOARD pipeline, this acts as a prohibitive legal barrier. Furthermore, empirical benchmarking demonstrates that Docling processes multi-page documents significantly faster than MinerU, completing a 12-page extraction in 8.2 seconds compared to MinerU's 14.7 seconds, while maintaining pristine Markdown and HTML table structures without the risk of bounding box misalignment.15

### **Qwen3-VL Series (Qwen3-VL-4B-Instruct)**

The Qwen3-VL series represents the pinnacle of generalized open-weight multimodal architectures in 2026\. The series features models ranging from 2 billion to 235 billion parameters, all uniquely offering a native 256K-token context window.17 For local deployment within an 8 GB VRAM constraint, the Qwen3-VL-4B-Instruct variant serves as a highly capable candidate.19  
Released under the Apache 2.0 license, the Qwen3-VL architecture introduces substantial advancements in spatial understanding. It leverages an enhanced MRope mechanism with interleaved layouts for superior spatial-temporal modeling, alongside DeepStack integration to effectively utilize multi-level features from the Vision Transformer (ViT).20 This grants the model robust 2D and 3D grounding capabilities, allowing it to determine absolute and relative object positions.18  
Qwen3-VL-4B-Instruct is particularly notable for its robust OCR capabilities across 32 languages, demonstrating high resilience against low-light conditions, blur, and tilt.21 These optical phenomena are ubiquitous in field archaeology photography. Operating in a 4-bit quantized GGUF format (or via Ollama), the model consumes roughly 2.8 GB of VRAM.18 While it acts as an exceptional generalized visual agent, its broader focus on embodied AI, GUI operation, and visual coding means that it requires significantly more intricate prompt engineering to enforce strict JSON document parsing compared to purpose-built OCR models like GLM-OCR.21

### **dots.mocr (dots.ocr 1.5)**

The dots.ocr lineage, specifically the dots.mocr variant (often referred to as dots.ocr 1.5), operates as a 3-billion parameter model (upgraded from a 1.7B foundation) that unifies layout detection and content recognition.23 Licensed under the permissive MIT agreement, it presents no commercial barriers.25 It scores an impressive 83.9% on the olmOCR benchmark, placing it in direct competition with much larger models.10  
A unique operational feature of dots.mocr is its deterministic structured output. The model natively outputs a single JSON object containing bounding box coordinates, element categories (e.g., text, formula, table), and the extracted textual content. It applies specific formatting rules autonomously, rendering tables in HTML and equations in LaTeX.26 This predictable reading order and bounding box preservation make it highly suitable for mapping complex visual hierarchies. However, head-to-head comparisons on community benchmarks indicate that generalized models like Qwen3-VL-8B occasionally outperform dots.ocr in raw extraction accuracy for highly degraded text, winning approximately 57% of direct comparisons.28

### **GOT-OCR 2.0 and Phi-Vision Models**

**GOT-OCR 2.0** represents an advanced, end-to-end General OCR Transformer. It operates on a unified transformer architecture that eliminates the need for separate text detectors and recognizers.1 By treating document parsing, formula reading, and scene text detection as a holistic vision-language task, it can handle a wide range of visual content in a single pass.1 However, while mathematically elegant, GOT-OCR 2.0 remains primarily an extraction engine rather than an interpretative reasoning engine, making it less adept at the complex schema-filling required by the HOARD project compared to instruction-tuned VLMs.  
General-purpose multimodal models such as **Phi-3.5-vision-instruct** and **Phi-4-vision** (already present in the caching infrastructure) possess the theoretical capability to read text while reasoning over document layout.2 However, recent evaluations in analogous industries (such as the digitization of noisy clinical records captured via smartphone) reveal that general-purpose MLLMs often lack robustness on degraded, real-world inputs compared to dedicated OCR pipelines.2 Their training distributions heavily favor synthetic or well-scanned inputs, rendering them highly sensitive to the shadows, mud stains, and low contrast typical of archaeological carbon copies.2

### **Comparative Matrix of VLM Candidates**

| Model | Params | VRAM (4-bit/FP16) | License | Primary Strengths | Constraint Compatibility |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **GLM-OCR** | 0.9B | \~1.5GB / 2.2GB | MIT / Apache 2.0 | Native strict JSON schema adherence, ultra-fast Multi-Token Prediction. | Ideal for complex handwritten form and checkbox extraction. |
| **Chandra OCR 2** | 4B | \~2.8GB | OpenRAIL-M | 85.9% olmOCR, high handwriting fidelity, math extraction. | **Failed:** License violates open-source distribution mandate. |
| **Granite-Docling** | 258M | \< 1.0GB | Apache 2.0 | Exceptional cross-page layout preservation, explicit tabular rendering. | Ideal for finds catalogues and structured typed records. |
| **Qwen3-VL-4B** | 4B | \~2.8GB | Apache 2.0 | Deep spatial reasoning, degraded image resilience, 256K context limit. | Highly suitable as a fallback model for complex sketches. |
| **dots.mocr** | 3.0B | \~2.4GB | MIT | Strict JSON bounding box extraction, HTML table synthesis. | Strong alternative for complex hierarchical visual mapping. |
| **MinerU** | 1.2B | \~2.4GB | AGPL-3.0 | 97.5 mAP layout preservation. | **Failed:** AGPL-3.0 viral license restricts commercial CRM use. |

## **Optimal Phase 1 Architecture for 8 GB VRAM Constraints**

The architectural formulation for Phase 1 must navigate the strict hardware realities of an 8 GB VRAM ceiling imposed by the RTX 3070 mobile GPU. The VRAM budget is inherently tight. The operating system (whether a Windows Desktop Window Manager or a Linux X11/Wayland compositor) will universally consume between 1.0 and 1.5 GB of VRAM. This leaves approximately 6.5 GB of operational memory for model weights, the Key-Value (KV) cache required for context processing, and the tensor activations generated during inference.  
Attempting to load a single, monolithic 8-billion parameter model (which occupies roughly 5.5 GB at 4-bit quantization) alongside high-resolution image context windows will inevitably result in out-of-memory (OOM) assertions or severe performance degradation through PCIe bus thrashing as the system swaps memory to system RAM.  
To circumvent this hardware limitation, the optimal architecture explicitly abandons the concept of a single model handling all document types simultaneously. Instead, Phase 1 must implement a highly synchronized, dynamically routed multi-model architecture. The existing Phase 0 ingestion module acts as the orchestration layer, utilizing triage metadata to sequence and load specialized models via API directives that strictly govern memory eviction.

### **The Tri-Partite Document Routing Strategy**

A standard archaeological evaluation produces a dataset that can be broadly categorized into three distinct data archetypes. Each archetype demands a specialized extraction vector, as generalist models fail to handle the unique edge cases of each format.  
**Route 1: Context Sheets (Handwritten Forms with Checkboxes)**  
Context sheets present the highest degree of complexity in the pipeline. They feature erratic cursive handwriting, inconsistent checkbox markings (e.g., a tick, a cross, or a fully shaded box), crossed-out text denoting errors, and integrated field sketches mapping stratigraphic cuts. Traditional general-purpose OCR models frequently fail to associate isolated checkboxes with their corresponding textual labels, interpreting them as stray punctuation.  
The optimal model for this route is **GLM-OCR**. Operating at 0.9 billion parameters, it requires minimal VRAM (occupying roughly 2.2 GB when deployed via Ollama).7 Its primary architectural advantage lies in its capacity for conditional structured generation. When provided with a rigorous Pydantic-defined JSON schema, GLM-OCR implicitly attends to the corresponding spatial regions without relying on brittle, explicit bounding box cropping.5 This holistic attention allows the model to correctly interpret the spatial relationship between a label (e.g., "Layer" vs. "Cut") and a hastily marked checkbox, outputting the result as a precise boolean value within a JSON object. The model's MIT license and Apache 2.0 pipeline dependencies ensure total compliance.4  
**Route 2: Finds Catalogues (Typed Cross-Page Tables)**  
Finds catalogues are typically typewritten or dot-matrix printed documents featuring dense tabular data that extends across multiple physical pages. The central challenge involves maintaining column alignment, preventing the erroneous merging of adjacent cells, and accurately capturing headers that apply to subsequent pages.  
The optimal model for this route is **Granite-Docling-258M** executing directly through the Docling Python library.12 As previously noted, replacing the MinerU model with Docling eliminates the AGPL-3.0 licensing vulnerability.15 Granite-Docling operates at a fraction of the VRAM cost (under 1 GB) while leveraging the Docling framework’s superior layout detection (the Heron model).12 Docling parses these tabular structures and exports them into multidimensional Markdown, HTML, or JSON representations.30 The underlying algorithm specifically avoids reading tables linearly from left to right; instead, it identifies the bounding grid, preserving the semantic relationship between column headers and their data rows, even when grid lines are faint or absent.32  
**Route 3: Existing Typed Notes (DOCX / TXT / MD)** Archaeological evaluations often include supplementary digital notes or partial drafts generated in word processors. Passing native digital text through a GPU-bound VLM is a massive misallocation of compute resources. The Docling library natively ingests PDF, DOCX, and TXT formats using highly efficient, CPU-bound parsing algorithms.12 The Phase 0 manifest will route these documents directly into the Docling standard parser, entirely bypassing GPU inference and preserving VRAM for downstream drafting phases.

### **VRAM Lifecycle and Explicit Memory Eviction Protocols**

To ensure that the 6.5 GB available VRAM limit is never breached during the transition between processing Context Sheets and Finds Catalogues, strict memory eviction policies must be programmatically enforced.  
The previous Phase 1 technical design considered utilizing llama.cpp in router mode to juggle multiple models. However, contemporary community analysis reveals a critical flaw for hardware-constrained systems: while llama.cpp router mode allows for LRU (Least Recently Used) eviction, it frequently suffers from race conditions during rapid model switching. The previous process fails to unload from VRAM fast enough before the new model weights are loaded, triggering immediate CUDA out-of-memory errors.33 The lack of a synchronous, guaranteed "unload all" API endpoint in standard configurations makes this approach dangerously unstable for an autonomous pipeline.33  
The superior and more deterministic approach is to utilize the **Ollama HTTP API** combined with explicit memory expiration parameters. Ollama implements a keep\_alive parameter that dictates exactly how long a model remains resident in GPU memory.35 By manipulating this parameter, the orchestrator achieves absolute control over the VRAM lifecycle.  
The execution sequence operates as follows:

1. **Batch Identification:** The Phase 0 manifest identifies a batch of Context Sheets ready for processing.  
2. **Model Locking:** The orchestrator triggers GLM-OCR via the Ollama API, passing the parameter "keep\_alive": \-1. This locks the model into VRAM indefinitely during batch processing, preventing redundant and time-consuming disk reads between individual sheets.35  
3. **Explicit Eviction:** Upon completing the batch, the orchestrator issues a null-generation request containing "keep\_alive": 0\. This command instructs the Ollama scheduler to instantly purge GLM-OCR, immediately freeing the 2.2 GB of VRAM.35  
4. **Garbage Collection:** Before initializing Granite-Docling for tabular data, the Python orchestrator explicitly invokes the garbage collector (gc.collect()) and torch.cuda.empty\_cache() to clear any orphaned tensors from the PyTorch memory allocator.37  
5. **Handoff:** Granite-Docling is loaded via the Hugging Face transformers pipeline to process the Finds Catalogues.

This mutually exclusive execution pattern mathematically ensures that GLM-OCR and Granite-Docling never occupy the GPU simultaneously, completely neutralizing the VRAM contention risk.

## **Enforcing Structured Output and Schema Adherence**

Phase 1 cannot output raw, conversational text; it must produce highly structured, deterministic JSON that conforms strictly to the canonical HOARD schema. The architectural shift to generative VLMs introduces the inherent risk of hallucinated fields, unexpected verbosity, or broken JSON syntax. The integration layer must ensure absolute adherence to the defined data structure so that Phases 3 and 4 receive valid, parsable data.

### **Pydantic Validation and Constrained Decoding**

Modern iterations of the Ollama Python library provide native support for structured outputs through deeply integrated schema injection. Rather than relying on fragile prompt engineering (e.g., appending "please output valid JSON" to a prompt), the system leverages Constrained Decoding driven by Pydantic models.38  
The architecture defines a rigorous Pydantic BaseModel containing the canonical fields expected from a context sheet:

Python  
from pydantic import BaseModel  
from typing import List, Optional

class Find(BaseModel):  
    type: str  
    qty: int  
    period: str

class ContextSheet(BaseModel):  
    context\_number: str  
    type: str  
    cut\_by: List\[str\]  
    cuts: List\[str\]  
    fills: List\[str\]  
    description: str  
    interpretation: str  
    period: str  
    finds: List\[Find\]  
    samples: List\[str\]  
    review\_flags: List\[str\]

During inference, this Pydantic class is serialized using the .model\_json\_schema() method and passed directly to Ollama’s format parameter in the API call.38 This parameter structurally constrains the model's output generation. At the fundamental tensor level, the decoding algorithm masks the logits of any token that would violate the defined JSON grammar, forcing the model to generate a strictly compliant object.  
To maximize determinism and eliminate creative hallucination, the model's inference hyperparameters must be strictly controlled. The temperature parameter must be set to 0 40, the top\_p to 0.95, and top\_k to 20\.41 This configuration forces greedy decoding, ensuring the model prioritizes the highest-probability tokens based purely on the visual evidence, preventing it from inventing archaeological interpretations not present on the sheet.  
Once the response string is generated, it is passed through ContextSheet.model\_validate\_json(response.message.content).39 This acts as a rigid, secondary validation layer. If the model attempts to map an alphabetical string into the integer qty field, or omits a required array entirely, the Pydantic validator will immediately raise an exception. This deterministic failure allows the pipeline to intercept the error and flag the document for human review, rather than silently passing corrupted data downstream.

### **Handling Low-Confidence and Ambiguous Data**

Archaeological records are inherently ambiguous. A faint pencil mark on a mud-stained context sheet might legitimately resemble either a "3" or an "8". The HOARD schema accommodates this uncertainty via the review\_flags array. To populate this effectively, the schema definitions injected into GLM-OCR must include explicit semantic instructions regarding visual ambiguity.  
The prompt structure (the system instructions passed alongside the JSON schema) must dictate that if the model cannot determine the contents of a field with high visual certainty, it must populate the primary field with its best statistical estimation, but simultaneously append a diagnostic string to the review\_flags array.  
For example, the prompt must enforce a rule: *“If handwriting is illegible or obscured, provide the most likely transcription in the target field, and append a flag to the review\_flags array formatted exactly as {"field": "\<field\_name\>", "issue": "\<description of ambiguity\>"}.”*  
Because compact monolithic models like GLM-OCR do not expose granular token-level confidence scores (logits) through high-level APIs like Ollama's structured output mode 42, confidence evaluation cannot be calculated mathematically post-generation. Therefore, self-reporting ambiguity must be engineered semantically into the schema itself. If a document generates an output where the review\_flags array is populated, the HOARD frontend can highlight these specific fields in red for the human reviewer during Phase 0/1 triage review.

## **Fallback Strategy for Degraded Documents**

Real-world archaeological archives are notoriously degraded. Datasets frequently encompass third-generation photocopies, carbon-copy context sheets with minimal contrast, forms printed on failing 1990s dot-matrix printers, and field notes obscured by soil, rain, and physical damage. Attempting to pass these degraded images directly into a VLM results in exponential accuracy degradation; the visual encoders fail to separate the signal (handwriting) from the noise (mud).  
Consequently, Phase 1 must implement a robust, deterministic image pre-processing pipeline leveraging the OpenCV library. This pre-processing runs exclusively on the CPU, zeroing out any VRAM impact and operating concurrently while models load or unload.

### **CPU-Bound OpenCV Algorithmic Interventions**

The Phase 0 triage module classifies documents and assigns quality flags (BLUR\_LOW, SKEW\_HIGH, EXPOSURE\_LOW). These flags act as deterministic routing directives for the OpenCV pre-processing algorithms, ensuring that compute resources are not wasted on clean documents.  
**1\. Deskewing and Geometric Transformation (SKEW\_HIGH)** Misaligned document orientation heavily distorts the spatial attention mechanisms of VLMs. When lines of text are angled, the bounding box interpretation algorithms struggle to maintain reading order, often confusing adjacent columns. If the SKEW\_HIGH flag is present, OpenCV algorithms utilizing Hough Line Transforms or contour bounding boxes calculate the rotational deviation of the primary text blocks against the horizontal axis.32 An affine transformation matrix is then generated and applied to mathematically rotate the image, re-establishing parallel alignment with the pixel coordinate grid.43 This instantly stabilizes the VLM's spatial grounding.  
**2\. Contrast Limited Adaptive Histogram Equalization (EXPOSURE\_LOW)** Carbon-copy sheets present uniform, low-contrast grey profiles that effectively blind standard optical recognition models. Applying standard, global histogram equalization to these images frequently overexposes the background, entirely washing out faint pencil strokes. To resolve this, the pipeline applies Contrast Limited Adaptive Histogram Equalization (CLAHE).44  
CLAHE operates by dividing the image into small contextual tiles (typically 8x8 pixels) and equalizing the histogram locally within each tile.43 To prevent the amplification of noise in homogenous regions (such as a blank area of the page), CLAHE mathematically clips the histogram at a predefined limit before calculating the cumulative distribution function. Bilinear interpolation is then used to stitch the tiles back together, eliminating artificial boundaries. This technique drastically enhances local contrast, pulling faint handwriting out from dark, muddy backgrounds without amplifying localized speckling.  
**3\. Adaptive Thresholding and Morphological Operations** For documents exhibiting heavy background noise—such as mud splatters or severe shadow gradients caused by folded paper—global thresholding techniques (like Otsu’s method) fail because the background darkness varies wildly across the page.45 Adaptive thresholding resolves this by calculating the binarization threshold dynamically for small pixel neighborhoods, adapting to the changing lighting conditions across the document.45  
Following adaptive binarization, morphological transformations are applied to reconstruct damaged characters. A morphological *opening* operation (erosion followed by dilation) uses a localized kernel to remove isolated noise artifacts, successfully erasing stray dust or speckles.46 Conversely, a morphological *closing* operation (dilation followed by erosion) is applied to bridge small geometric gaps inside handwritten characters, reconnecting broken strokes caused by faint or skipping pens.46

### **The Secondary VLM Fallback Path**

If the primary GLM-OCR model continuously fails to validate against the Pydantic schema—indicating total structural failure due to severe document degradation—the system requires a fallback mechanism. While specialized Historical Text Recognition (HTR) models (e.g., trocr-medieval-base) were previously considered, the contemporary landscape suggests that compact multi-modal models actually demonstrate superior resilience to noise than traditional pipelined HTR.2 Advanced MLLMs like Qwen-2.5-VL and Qwen3-VL-4B can read text while reasoning over highly degraded document layouts.2  
In the event of a GLM-OCR failure (triggered after two unsuccessful schema re-ask loops), the fallback protocol involves routing the pre-processed OpenCV image into the **Qwen3-VL-4B-Instruct** model. While its strict JSON schema adherence is slightly less rigorous than GLM-OCR, its significantly larger parameter count (4B vs 0.9B) and advanced 2D spatial grounding grant it superior raw interpretative power for highly degraded cursive handwriting.19  
If this secondary extraction via Qwen3-VL-4B also fails validation, the document is permanently marked with a critical review flag in the database, and a blank placeholder JSON object is exported. This "fail-safe" mechanism ensures the automated pipeline continues executing without crashing, quarantining the unreadable document for manual human transcription at a later stage.

## **Infrastructure Integration and Phase 0 Handoff**

The integration of these models into the existing HOARD architecture requires precise orchestration of Python dependencies, Inter-Process Communication (IPC), and data encoding.

### **Phase 0 Manifest Routing**

Phase 0 outputs a JSON manifest detailing the file paths, document types, and quality flags for all ingested images. The Phase 1 Python orchestrator parses this manifest and groups the files into discrete batches based on their document type. This batching is critical for minimizing VRAM churn. All Context Sheets are processed sequentially, followed by all Finds Catalogues.

### **API Strategy and Image Encoding**

The interaction with GLM-OCR and the fallback Qwen3-VL-4B-Instruct is managed exclusively through the Ollama Python SDK. Operating locally, the orchestrator script does not rely on external networking or cloud API calls. To prevent file-locking issues, optimize disk I/O, and maintain execution speed, images processed by the OpenCV pipeline are not written back to the physical disk. Instead, the resulting NumPy arrays are encoded directly into Base64 strings in memory. These Base64 strings are appended to the payload and passed directly into the Ollama API endpoint.47  
Conversely, Docling and Granite-Docling operate natively within the Python runtime environment via PyTorch and the Hugging Face transformers library.37 Docling consumes file paths natively. When transitioning from the Ollama-managed workflow to the Docling workflow, the system must carefully manage the handoff to prevent resource contention, as detailed in the memory eviction protocols.

## **Implementation Risk Register and Dependency Matrix**

Implementing a highly orchestrated, multi-model pipeline operating on the absolute limits of consumer hardware introduces specific technical risks. A proactive mitigation strategy is required.

### **Dependency Matrix**

To execute Phase 1, the following software dependencies must be integrated into the HOARD environment:

* **System Binaries:** Ollama v0.12.7+ (Required for Qwen3-VL and Structured Output support).49  
* **Python Packages:** ollama, pydantic, opencv-python (cv2), numpy, docling, torch, transformers, accelerate.  
* **Ollama Models:** glm-ocr:latest, qwen3-vl:4b-instruct.  
* **Hugging Face Models:** ibm-granite/granite-docling-258M.

### **Risk Register**

| Risk Category | Description | Mitigation Strategy |
| :---- | :---- | :---- |
| **VRAM Fragmentation** | The rapid loading and unloading of models via Ollama and PyTorch may leave orphaned tensors in VRAM, gradually consuming the 8 GB limit until a CUDA OOM crash occurs. | Enforce strict sequential execution. Issue keep\_alive: 0 to Ollama, instantiate a 2-second blocking time.sleep(), and explicitly call gc.collect() and torch.cuda.empty\_cache() before loading Docling components. |
| **Context Window Explosion** | GLM-OCR requires num\_ctx to be set to 16384 for image processing.7 Processing exceptionally tall or high-resolution context sheets may exceed this limit, crashing the KV cache. | Implement a deterministic image resizing pre-processor. Downscale input images to a maximum dimension of 2048 pixels on the longest edge prior to Base64 encoding and inference. |
| **Schema Hallucination** | Despite Pydantic JSON schema constraints, the model may hallucinate keys or nest structures improperly due to layout confusion on messy pages. | Wrap the Ollama inference call in a try/except block utilizing Pydantic's ValidationError. Implement a maximum of two automated "re-ask" loops before failing gracefully to the Qwen3-VL fallback or the review flag system. |
| **Table Merging Artifacts** | Carbon-copy finds catalogues often lack distinct grid lines. Docling may falsely merge adjacent rows if vertical spacing is inconsistent. | Utilize Docling's advanced configuration to adjust spatial tolerance parameters, prioritizing horizontal reading alignment over vertical proximity when detecting row boundaries.16 |
| **License Contamination** | Inadvertent inclusion of AGPL-3.0 models (e.g., MinerU) or OpenRAIL-M models (Chandra OCR) restricts commercial deployment. | Strictly audit all dependencies. Phase 1 must rely exclusively on MIT (GLM-OCR, dots.mocr) and Apache 2.0 (Granite-Docling, Qwen3-VL) components. |

## **Synthesis**

The architecture detailed herein establishes a highly robust, hardware-compliant, and legally unencumbered framework for HOARD Phase 1\. By decisively pivoting away from cascaded legacy OCR systems and legally restrictive models like MinerU, the pipeline fully embraces the May 2026 state of the art in compact Vision-Language Models.  
The strategic deployment of GLM-OCR for complex, unstructured context sheets leverages its unparalleled efficiency and deterministic JSON schema alignment through Multi-Token Prediction. Simultaneously, the integration of Granite-Docling-258M secures precise, layout-aware tabular extraction for multi-page Finds Catalogues while remaining securely within Apache 2.0 licensing boundaries.  
By offloading the critical task of document pre-processing to CPU-bound OpenCV algorithms utilizing CLAHE, affine transformations, and morphological closing, the system mathematically neutralizes visual degradation without penalizing the 8 GB VRAM budget. When unified under strict Ollama memory eviction protocols (keep\_alive: 0\) and Pydantic validation structures, this architecture guarantees the seamless, autonomous transformation of chaotic archaeological field data into publication-ready, machine-readable intelligence.

#### **Works cited**

1. 8 Top Open-Source OCR Models Compared: A Complete Guide \- Modal, accessed May 25, 2026, [https://modal.com/blog/8-top-open-source-ocr-models-compared](https://modal.com/blog/8-top-open-source-ocr-models-compared)  
2. Compact Multimodal Language Models as Robust OCR Alternatives for Noisy Textual Clinical Reports \- ACL Anthology, accessed May 25, 2026, [https://aclanthology.org/2026.eacl-industry.4.pdf](https://aclanthology.org/2026.eacl-industry.4.pdf)  
3. \[2603.10910\] GLM-OCR Technical Report \- arXiv, accessed May 25, 2026, [https://arxiv.org/abs/2603.10910](https://arxiv.org/abs/2603.10910)  
4. zai-org/GLM-OCR \- GitHub, accessed May 25, 2026, [https://github.com/zai-org/GLM-OCR](https://github.com/zai-org/GLM-OCR)  
5. 1 Performance of GLM-OCR on OmniDocBench v1.5. \- arXiv, accessed May 25, 2026, [https://arxiv.org/html/2603.10910v1](https://arxiv.org/html/2603.10910v1)  
6. zai-org/GLM-OCR \- Hugging Face, accessed May 25, 2026, [https://huggingface.co/zai-org/GLM-OCR](https://huggingface.co/zai-org/GLM-OCR)  
7. Ultimate Guide: Run GLM-OCR Locally on MacBook Fast \- BuildWithMatija, accessed May 25, 2026, [https://www.buildwithmatija.com/blog/run-glm-ocr-macbook-ollama](https://www.buildwithmatija.com/blog/run-glm-ocr-macbook-ollama)  
8. Chandra OCR 2: The Open-Source Model That Reads What Others Can't \- Towards AI, accessed May 25, 2026, [https://pub.towardsai.net/chandra-ocr-2-the-open-source-model-that-reads-what-others-cant-6a218faa0efd](https://pub.towardsai.net/chandra-ocr-2-the-open-source-model-that-reads-what-others-cant-6a218faa0efd)  
9. Chandra OCR 2: 4B Open-Source Model Hits 85.9% SOTA on olmOCR Benchmark, Crushes Handwriting, Math, Tables, Forms, Diagrams & 90+ Languages\! : r/computervision \- Reddit, accessed May 25, 2026, [https://www.reddit.com/r/computervision/comments/1svx4zx/chandra\_ocr\_2\_4b\_opensource\_model\_hits\_859\_sota/](https://www.reddit.com/r/computervision/comments/1svx4zx/chandra_ocr_2_4b_opensource_model_hits_859_sota/)  
10. datalab-to/chandra-ocr-2 · Hugging Face, accessed May 25, 2026, [https://huggingface.co/datalab-to/chandra-ocr-2](https://huggingface.co/datalab-to/chandra-ocr-2)  
11. GitHub \- datalab-to/chandra: OCR model that handles complex tables, forms, handwriting with full layout., accessed May 25, 2026, [https://github.com/datalab-to/chandra](https://github.com/datalab-to/chandra)  
12. GitHub \- docling-project/docling: Get your documents ready for gen AI, accessed May 25, 2026, [https://github.com/docling-project/docling](https://github.com/docling-project/docling)  
13. ibm-granite/granite-docling-258M \- Hugging Face, accessed May 25, 2026, [https://huggingface.co/ibm-granite/granite-docling-258M](https://huggingface.co/ibm-granite/granite-docling-258M)  
14. IBM Granite-Docling: End-to-end document understanding, accessed May 25, 2026, [https://www.ibm.com/new/announcements/granite-docling-end-to-end-document-conversion](https://www.ibm.com/new/announcements/granite-docling-end-to-end-document-conversion)  
15. Docling vs MinerU: I Tested Both (2025) | Real Results | CodeSOTA, accessed May 25, 2026, [https://www.codesota.com/ocr/docling-vs-mineru](https://www.codesota.com/ocr/docling-vs-mineru)  
16. Evidence Units: Ontology-Grounded Document Organization for Parser-Independent Retrieval \- arXiv, accessed May 25, 2026, [https://arxiv.org/html/2604.00500v1](https://arxiv.org/html/2604.00500v1)  
17. \[2511.21631\] Qwen3-VL Technical Report \- arXiv, accessed May 25, 2026, [https://arxiv.org/abs/2511.21631](https://arxiv.org/abs/2511.21631)  
18. qwen3-vl:4b \- Ollama, accessed May 25, 2026, [https://ollama.com/library/qwen3-vl:4b](https://ollama.com/library/qwen3-vl:4b)  
19. Qwen/Qwen3-VL-4B-Instruct \- Hugging Face, accessed May 25, 2026, [https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct)  
20. Qwen3-VL \- Hugging Face, accessed May 25, 2026, [https://huggingface.co/docs/transformers/en/model\_doc/qwen3\_vl](https://huggingface.co/docs/transformers/en/model_doc/qwen3_vl)  
21. Qwen3 VL 4B \- LM Studio, accessed May 25, 2026, [https://lmstudio.ai/models/qwen/qwen3-vl-4b](https://lmstudio.ai/models/qwen/qwen3-vl-4b)  
22. Qwen2.5 VL for OCR : r/LocalLLaMA \- Reddit, accessed May 25, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1nwuslg/qwen25\_vl\_for\_ocr/](https://www.reddit.com/r/LocalLLaMA/comments/1nwuslg/qwen25_vl_for_ocr/)  
23. dots.ocr \- Multilingual Document OCR & Layout Parsing with Vision-Language Model, accessed May 25, 2026, [https://www.dotsocr.net/](https://www.dotsocr.net/)  
24. GitHub \- rednote-hilab/dots.ocr: Multilingual Document Layout Parsing in a Single Vision-Language Model, accessed May 25, 2026, [https://github.com/rednote-hilab/dots.ocr](https://github.com/rednote-hilab/dots.ocr)  
25. dots.ocr/LICENSE at master · rednote-hilab/dots.ocr · GitHub, accessed May 25, 2026, [https://github.com/rednote-hilab/dots.ocr/blob/master/LICENSE](https://github.com/rednote-hilab/dots.ocr/blob/master/LICENSE)  
26. DOTS OCR \- mlx-vlm \- GitHub, accessed May 25, 2026, [https://github.com/Blaizzy/mlx-vlm/blob/main/mlx\_vlm/models/dots\_ocr/README.md](https://github.com/Blaizzy/mlx-vlm/blob/main/mlx_vlm/models/dots_ocr/README.md)  
27. Small but Mighty: How dots.ocr is Revolutionizing Document AI \- Evnek Quest, accessed May 25, 2026, [https://www.evnekquest.com/post/small-but-mighty-how-dots-ocr-is-revolutionizing-document-ai](https://www.evnekquest.com/post/small-but-mighty-how-dots-ocr-is-revolutionizing-document-ai)  
28. dots.ocr vs Qwen3-VL-8B \- OCR Model Comparison | OCR Arena, accessed May 25, 2026, [https://www.ocrarena.ai/compare/dots-ocr/qwen3-vl-8b](https://www.ocrarena.ai/compare/dots-ocr/qwen3-vl-8b)  
29. Vision models \- Docling \- GitHub Pages, accessed May 25, 2026, [https://docling-project.github.io/docling/usage/vision\_models/](https://docling-project.github.io/docling/usage/vision_models/)  
30. Table export \- Docling \- GitHub Pages, accessed May 25, 2026, [https://docling-project.github.io/docling/examples/export\_tables/](https://docling-project.github.io/docling/examples/export_tables/)  
31. Document Processing and Query Automation with IBM Docling: Converting to Markdown and JSON with Ease | by Onur Sakar | Medium, accessed May 25, 2026, [https://medium.com/@onur.sakar1997/document-processing-and-query-automation-with-ibm-docling-converting-to-markdown-and-json-with-4f318257669a](https://medium.com/@onur.sakar1997/document-processing-and-query-automation-with-ibm-docling-converting-to-markdown-and-json-with-4f318257669a)  
32. Detect Table in an Image in Python: Complete Guide \- Cloudinary, accessed May 25, 2026, [https://cloudinary.com/guides/image-effects/detect-table-in-image-python](https://cloudinary.com/guides/image-effects/detect-table-in-image-python)  
33. Unload All llama.cpp Router Models Without Restarting | by Rost Glukhov \- Medium, accessed May 25, 2026, [https://medium.com/@rosgluk/https-www-glukhov-org-llm-hosting-llama-cpp-unload-llama-cpp-router-models-ae44fa14fd6f](https://medium.com/@rosgluk/https-www-glukhov-org-llm-hosting-llama-cpp-unload-llama-cpp-router-models-ae44fa14fd6f)  
34. Anyone got llama.cpp router mode actually working on limited VRAM (12GB/16GB)?, accessed May 25, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1tirdlx/anyone\_got\_llamacpp\_router\_mode\_actually\_working/](https://www.reddit.com/r/LocalLLaMA/comments/1tirdlx/anyone_got_llamacpp_router_mode_actually_working/)  
35. FAQ \- Ollama's documentation, accessed May 25, 2026, [https://docs.ollama.com/faq](https://docs.ollama.com/faq)  
36. Freeing VRAM with ollama : r/LocalLLaMA \- Reddit, accessed May 25, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/18ed9tr/freeing\_vram\_with\_ollama/](https://www.reddit.com/r/LocalLLaMA/comments/18ed9tr/freeing_vram_with_ollama/)  
37. Granite Docling \- IBM, accessed May 25, 2026, [https://www.ibm.com/granite/docs/models/docling](https://www.ibm.com/granite/docs/models/docling)  
38. Structured Outputs \- Ollama's documentation, accessed May 25, 2026, [https://docs.ollama.com/capabilities/structured-outputs](https://docs.ollama.com/capabilities/structured-outputs)  
39. Structured Outputs with Ollama: Harnessing Local AI Models for Reliable Data \- Medium, accessed May 25, 2026, [https://medium.com/@danushidk507/structured-outputs-with-ollama-harnessing-local-ai-models-for-reliable-data-ae49221e9c13](https://medium.com/@danushidk507/structured-outputs-with-ollama-harnessing-local-ai-models-for-reliable-data-ae49221e9c13)  
40. Structured outputs · Ollama Blog, accessed May 25, 2026, [https://ollama.com/blog/structured-outputs](https://ollama.com/blog/structured-outputs)  
41. Qwen3-VL: How to Run Guide | Unsloth Documentation, accessed May 25, 2026, [https://unsloth.ai/docs/models/tutorials/qwen3-how-to-run-and-fine-tune/qwen3-vl-how-to-run-and-fine-tune](https://unsloth.ai/docs/models/tutorials/qwen3-how-to-run-and-fine-tune/qwen3-vl-how-to-run-and-fine-tune)  
42. Using Structured Outputs with Reasoning Models : r/LocalLLaMA \- Reddit, accessed May 25, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1ihs6tw/using\_structured\_outputs\_with\_reasoning\_models/](https://www.reddit.com/r/LocalLLaMA/comments/1ihs6tw/using_structured_outputs_with_reasoning_models/)  
43. Image Pre-Processing Techniques for OCR | by Tech for Humans | Medium, accessed May 25, 2026, [https://medium.com/@TechforHumans/image-pre-processing-techniques-for-ocr-d231586c1230](https://medium.com/@TechforHumans/image-pre-processing-techniques-for-ocr-d231586c1230)  
44. 27 \- CLAHE and Thresholding using opencv in Python \- YouTube, accessed May 25, 2026, [https://www.youtube.com/watch?v=XfDkg3z3BCg](https://www.youtube.com/watch?v=XfDkg3z3BCg)  
45. Adaptive Thresholding with OpenCV ( cv2.adaptiveThreshold ) \- PyImageSearch, accessed May 25, 2026, [https://pyimagesearch.com/2021/05/12/adaptive-thresholding-with-opencv-cv2-adaptivethreshold/](https://pyimagesearch.com/2021/05/12/adaptive-thresholding-with-opencv-cv2-adaptivethreshold/)  
46. Enhancing OCR Accuracy in Python with OpenCV and PyTesseract | Trenton McKinney, accessed May 25, 2026, [https://trenton3983.github.io/posts/ocr-image-processing-pytesseract-cv2/](https://trenton3983.github.io/posts/ocr-image-processing-pytesseract-cv2/)  
47. OpenAI compatibility \- Ollama's documentation, accessed May 25, 2026, [https://docs.ollama.com/api/openai-compatibility](https://docs.ollama.com/api/openai-compatibility)  
48. The Complete Guide to vLLM & Ollama: LLM Serving Engine Setup, Parameters, and Environment Variables, accessed May 25, 2026, [https://www.youngju.dev/blog/llm/vllm\_ollama\_serving\_complete\_guide.en](https://www.youngju.dev/blog/llm/vllm_ollama_serving_complete_guide.en)  
49. qwen3-vl \- Ollama, accessed May 25, 2026, [https://ollama.com/library/qwen3-vl:latest](https://ollama.com/library/qwen3-vl:latest)