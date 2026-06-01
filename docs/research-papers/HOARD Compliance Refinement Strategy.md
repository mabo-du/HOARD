# **Architectural Implementation of the HOARD Phase 4 Compliance Pipeline: Integrating Vision-Language Models with Deterministic Regulatory Frameworks**

The transition from structural drafting to rigorous jurisdictional compliance within the HOARD pipeline introduces complex architectural challenges. Phase 4 necessitates reconciling the high-level semantic reasoning capabilities of a Vision-Language Model (VLM) against highly deterministic, rigid regulatory frameworks encapsulated in YAML templates. Operating the Gemma 4-E2B model via a llama.cpp server under a strict 6 GB VRAM constraint requires highly optimized deployment strategies. This analysis explores the optimal compliance checking architectures, rule encoding paradigms, hardware-aware computational designs, and the specific schema evolutions required for the United Kingdom, the Netherlands, and Ontario, Canada.

## **Hardware-Aware Inference and Contextual Strategy**

The selection of Gemma 4-E2B introduces specific computational characteristics that profoundly influence the architectural approach to document compliance. Understanding the memory footprint of this model is foundational to designing a stable inference pipeline.

### **VRAM Mathematical Modeling for Gemma 4-E2B**

Gemma 4-E2B employs a Per-Layer Embedding (PLE) architecture, providing an effective parameter count of 2.3 billion during active inference, while housing a total of 5.1 billion parameters (including embeddings).1 In the Q4\_K\_M quantization format (4-bit), the baseline static model weights occupy approximately 1.71 GB to 2.1 GB of VRAM.3 However, static weight allocation is merely the foundation; the primary variable consumer of Video Random Access Memory (VRAM) during large-scale document processing is the Key-Value (KV) cache.  
The KV cache stores the attention key and value vectors for all previously processed tokens, allowing the model to generate the next token without recalculating the entire sequence.5 The memory footprint of the KV cache scales linearly with the context length. Standard calculations dictate that KV Cache VRAM is equal to ![][image1].6  
Gemma 4-E2B utilizes a Sliding Window Attention (SWA) mechanism across its 35 layers (sharing KV state across 20 of those layers) to mitigate unbounded cache growth.7 Despite this architectural efficiency, the llama.cpp server implementation defaults to allocating SWA memory in unquantized FP16 format.9 Furthermore, llama.cpp calculates the initial SWA allocation based on a formula roughly equivalent to the sliding window size multiplied by the number of parallel sequence slots, plus the micro-batch size.9 If the server initializes with the default multi-slot configuration (typically 4 slots), the SWA cache pre-allocates an excessively large footprint, routinely triggering Out-Of-Memory (OOM) errors on 6 GB hardware.9  
To operate safely within a 6 GB VRAM limit, the llama.cpp server must be explicitly launched with the \-np 1 flag, which restricts inference to a single parallel slot.9 This parameter reduction cuts the SWA cache VRAM consumption by approximately a factor of three, dropping the initial allocation overhead from roughly 900 MB down to 300 MB, thereby preserving crucial memory headroom for the actual document context.9

| Memory Component | Base FP16 Model (GB) | Q4\_K\_M Quantized (GB) | Impact of \-np 1 Flag |
| :---- | :---- | :---- | :---- |
| **Model Weights** | \~10.5 GB 4 | \~1.71 \- 2.1 GB 3 | N/A (Static) |
| **CUDA Overhead** | \~0.5 \- 1.0 GB 5 | \~0.5 \- 1.0 GB 5 | N/A (Static) |
| **SWA KV Cache (Idle)** | \~0.9 GB 9 | \~0.9 GB (Allocates in FP16) 9 | Reduces to \~0.3 GB 9 |
| **Context KV (Per 4K tokens)** | \~0.25 \- 0.5 GB 5 | \~0.25 \- 0.5 GB 5 | N/A (Dynamic) |
| **Total Estimated Peak VRAM** | **\~12.15 GB+** (Fails on 6GB) | **\~3.6 GB \- 4.1 GB** (Safe) | Prevents OOM crashes |

### **Section-by-Section Analysis vs. Single-Pass Evaluation**

A critical architectural decision is determining whether to submit the entire multi-page Markdown draft into the model simultaneously or to execute iterative, section-by-section inference calls.  
For the HOARD Phase 4 pipeline, a section-by-section strategy is vastly superior and operationally mandatory. A comprehensive archaeological report routinely exceeds 10,000 to 20,000 tokens. While Gemma 4-E2B theoretically supports a 128,000-token context window 1, processing 20,000 tokens simultaneously requires a proportional expansion of the KV cache that instantly breaches a 6 GB VRAM ceiling. Pushing the context size limits forces aggressive context offloading to system RAM, which severely degrades Time-To-First-Token (TTFT) metrics and overall inference speed.9  
Beyond memory constraints, large language models suffer from degraded recall precision—often termed the "Lost in the Middle" phenomenon—when instructed to monitor a vast context for multiple, highly granular rules simultaneously.13 Directing a 4-billion parameter VLM to simultaneously cross-reference the introduction against Rule A and the appendices against Rule Z within the same prompt predictably induces hallucination, instruction drift, and false positives.  
Section-by-section processing allows the system to filter the YAML rules programmatically, injecting only the constraints relevant to the specific section being analyzed into the system prompt. This drastically reduces prompt complexity and input token count, directly increasing the classification accuracy and deterministic reliability of the VLM.

## **Rule Encoding Approaches and Bipartite Processing**

A fundamental anti-pattern in generative AI pipeline design is utilizing probabilistic models for tasks that can be perfectly resolved through deterministic algorithms. Encoding strict jurisdictional rules requires a bifurcated approach where tasks are assigned to either a programmatic rule engine or the semantic VLM engine based entirely on their linguistic complexity.

### **Structural Integrity and Mandatory Sections**

Verifying that all mandatory sections are present and sequenced correctly is a purely topological problem. Utilizing the VLM for this verification is computationally wasteful and introduces unnecessary risk of hallucination.  
The optimal approach utilizes a programmatic Markdown Abstract Syntax Tree (AST) parser (such as Python's markdown-it-py). The parser traverses the document to extract a flattened list of all existing headings. This extracted sequence is subsequently evaluated algorithmically against the mandatory\_sections array defined in the jurisdiction's YAML file. Any missing sections, nested hierarchy errors, or sequence violations are immediately flagged without consuming GPU inference cycles.

### **Lexical Constraints and Prohibited Terms**

Jurisdiction-specific jargon bans are strict lexical constraints. For example, a regulatory body may prohibit obsolete geological terminology or mandate specific indigenous community nomenclatures (e.g., globally replacing "Aboriginal" with "Indigenous" as mandated by Ontario's ERO 026-0216 updates 14).  
A programmatic implementation, specifically utilizing an Aho-Corasick automaton for ![][image2] multi-pattern searching, is unequivocally superior to VLM evaluation for these tasks.6 VLMs process text by breaking it into sub-word tokens via Byte-Pair Encoding (BPE). This tokenization can obscure exact string matches. If a prohibited word is tokenized into three separate chunks, the VLM must rely on semantic attention to identify the word, which can lead to false negatives. Furthermore, a VLM may attempt to contextualize or justify the presence of a prohibited term (e.g., determining it was used acceptably within a direct quotation). Regulatory compliance often demands strict flagging regardless of context, making programmatic pre-processing the only reliable method for achieving 100% deterministic recall.

### **Typographical Normalisation and Heading Styles**

Enforcing heading capitalisation and hierarchical formatting relies on strict typographical rules. If a VLM is prompted to "ensure title case" across a document, it will consume heavy inference time and introduces the risk of inadvertently altering the semantic phrasing of the heading during text generation. Heading normalisation must be handled by a post-processing regular expression (Regex) engine paired with AST manipulation. This guarantees stylistic compliance without altering the semantic payload of the document.

### **Semantic Insertion of Exact Phrases**

Certain jurisdictions mandate the inclusion of exact, verbatim boilerplate language to fulfill legal requirements. Ontario's recent regulatory changes mandate highly specific phrasing for Stage 4 mitigation recommendations and buffer zone declarations.15  
Managing exact phrases requires a hybrid execution mechanism:

1. **Programmatic Verification**: A deterministic string-matching algorithm checks if the exact phrase exists in the target section. If it does, compliance is verified instantly.  
2. **Semantic VLM Insertion**: If the phrase is missing, the text cannot simply be appended to the end of the section via string concatenation, as this routinely breaks narrative flow and grammatical cohesion. The section text and the mandatory phrase are passed to Gemma 4-E2B with a specialized prompt. The model is instructed to seamlessly weave the exact verbatim phrase into the existing narrative context without altering the surrounding semantic meaning.

| Compliance Task Type | Execution Engine | Rationale for Engine Selection |
| :---- | :---- | :---- |
| **Mandatory Sections** | Programmatic (AST Parser) | Topological task; requires ![][image3] accuracy in sequence validation. |
| **Prohibited Terms** | Programmatic (Aho-Corasick) | Lexical task; BPE tokenization in VLMs causes string-matching failures. |
| **Heading Styles** | Programmatic (Regex) | Typographical task; VLM generation risks altering heading semantics. |
| **Word Counts** | Programmatic (Tokenizer) | Mathematical task; VLMs cannot accurately count words in long contexts. |
| **Tone & Style Verification** | VLM (Gemma 4-E2B) | Semantic task; requires understanding of nuance, professional tone, and context. |
| **Cross-Referencing Claims** | VLM (Gemma 4-E2B) | Semantic task; requires contextual memory to link claims across sections. |
| **Missing Phrase Insertion** | VLM (Gemma 4-E2B) | Generative task; requires narrative blending and grammatical restructuring. |

## **The Hybrid ComplianceEngine Architecture**

The findings dictate a bipartite architecture combining deterministic fast-paths with semantic slow-paths. The ComplianceEngine orchestrates this workflow, ensuring that the 2.1 GB Gemma model is invoked only when strict natural language understanding is required.

### **Core Class Skeleton**

The following Python architecture defines the operational flow of Phase 4\. It leverages Pydantic for strict output validation, ensuring the VLM's JSON responses are strongly typed before being integrated into the final compliance report.

Python  
import json  
import re  
from typing import List, Dict, Optional  
from pydantic import BaseModel, Field

class Violation(BaseModel):  
    rule\_id: str  
    severity: str \= Field(pattern="^(blocking|advisory)$")  
    description: str  
    suggested\_fix: Optional\[str\] \= None

class ComplianceReport(BaseModel):  
    document\_id: str  
    jurisdiction: str  
    overall\_status: str  
    violations: List\[Violation\]

class ProgrammaticChecker:  
    def \_\_init\_\_(self, template: dict):  
        self.template \= template  
          
    def check\_mandatory\_sections(self, ast\_tree: dict) \-\> List\[Violation\]:  
        \# Traverses AST to ensure template\['mandatory\_sections'\] are present in exact order  
        pass

    def check\_prohibited\_terms(self, text: str) \-\> List\[Violation\]:  
        \# Executes Aho-Corasick automaton against template\['prohibited\_terms'\]  
        \# Returns advisory violation if found  
        pass  
          
    def check\_exact\_phrases(self, section\_name: str, text: str) \-\> List\[Violation\]:  
        \# Simple string match for phrases required in specific sections  
        pass

class SemanticChecker:  
    def \_\_init\_\_(self, vlm\_endpoint: str):  
        self.endpoint \= vlm\_endpoint  
          
    def evaluate\_semantic\_rules(self, section\_name: str, text: str, rules: dict) \-\> List\[Violation\]:  
        \# Formats the Phase 4 Audit Prompt Template  
        \# Calls llama.cpp server hosting Gemma 4-E2B  
        \# Validates JSON response using Pydantic  
        pass  
          
    def insert\_exact\_phrase(self, text: str, phrase: str) \-\> str:  
        \# Calls VLM with the Semantic Insertion Prompt Template  
        pass

class ComplianceEngine:  
    def \_\_init\_\_(self, yaml\_template\_path: str, vlm\_endpoint: str):  
        self.template \= self.\_load\_yaml(yaml\_template\_path)  
        self.prog\_checker \= ProgrammaticChecker(self.template)  
        self.vlm\_checker \= SemanticChecker(vlm\_endpoint)

    def \_load\_yaml(self, path: str) \-\> dict:  
        \# Loads and validates jurisdiction YAML rules  
        pass

    def process\_document(self, markdown\_ast: dict) \-\> ComplianceReport:  
        all\_violations \=  
          
        \# 1\. Document-level programmatic sweeping  
        all\_violations.extend(self.prog\_checker.check\_mandatory\_sections(markdown\_ast))  
          
        \# 2\. Iterative section-by-section analysis  
        for section in markdown\_ast\['sections'\]:  
            \# Fast-path: Programmatic sweeps  
            all\_violations.extend(self.prog\_checker.check\_prohibited\_terms(section\['text'\]))  
              
            missing\_phrases \= self.prog\_checker.check\_exact\_phrases(section\['name'\], section\['text'\])  
            for missing in missing\_phrases:  
                \# Trigger semantic insertion if a mandated phrase is absent  
                corrected\_text \= self.vlm\_checker.insert\_exact\_phrase(  
                    section\['text'\], missing.suggested\_fix  
                )  
                section\['text'\] \= corrected\_text \# Update AST node  
                all\_violations.append(missing)  
              
            \# Slow-path: Semantic sweeps (VLM)  
            section\_rules \= self.\_extract\_relevant\_semantic\_rules(section\['name'\])  
            if section\_rules:  
                vlm\_violations \= self.vlm\_checker.evaluate\_semantic\_rules(  
                    section\['name'\], section\['text'\], section\_rules  
                )  
                all\_violations.extend(vlm\_violations)  
                  
        \# 3\. Final report compilation  
        status \= "fail" if any(v.severity \== "blocking" for v in all\_violations) else "pass"  
        return ComplianceReport(  
            document\_id=markdown\_ast.get('id', 'unknown'),  
            jurisdiction=self.template\['jurisdiction\_name'\],  
            overall\_status=status,  
            violations=all\_violations  
        )

### **Phase 4 System Prompt Templates**

To maximize the instruction-following capabilities of the 4B model, the prompts must clearly separate the regulatory constraints from the target text.  
**Prompt 1: Semantic Compliance Auditing**  
This prompt is utilized when a rule requires qualitative semantic verification (e.g., verifying that the Executive Summary accurately reflects the Results section). It enforces a strict JSON output schema.  
\<|im\_start|\>system  
You are an expert regulatory compliance auditor for archaeological documentation. Your task is to evaluate a specific section of a draft report against a defined set of jurisdictional rules.  
You must output your findings strictly as a valid JSON object. Do not output any conversational text or markdown formatting outside of the JSON block.

# **JURISDICTION RULES FOR CURRENT SECTION:**

{rule\_text}

# **INSTRUCTIONS:**

1. Read the provided section text carefully.  
2. Evaluate the text against the jurisdiction rules provided above.  
3. Identify any violations of the rules.  
4. Output a JSON object matching the following schema:  
   {{  
   "compliance\_status": "pass" | "fail",  
   "violations": \[  
   {{  
   "rule\_id": "string",  
   "severity": "blocking" | "advisory",  
   "description": "string",  
   "suggested\_fix": "string"  
   }}  
   \]  
   }}  
   \<|im\_end|\>  
   \<|im\_start|\>user

# **SECTION TITLE:**

{section\_title}

# **SECTION TEXT:**

{section\_text}  
\<|im\_end|\>  
\<|im\_start|\>assistant  
**Prompt 2: Semantic Phrase Insertion**  
This prompt is triggered dynamically when the programmatic engine detects the absence of an exact, mandated regulatory string.  
\<|im\_start|\>system  
You are an expert archaeological technical writer. You have been provided with a draft section of a report and a mandated regulatory phrase that MUST be included in this section.  
Your task is to rewrite the section to seamlessly weave the exact mandated phrase into the narrative.

1. The mandated phrase must appear EXACTLY as provided, word-for-word. Do not alter its punctuation or capitalization.  
2. Blend the phrase logically into the surrounding text. Do not simply append it to the end if it breaks the narrative flow.  
3. Do not change any other facts, figures, or semantic meaning in the original text.  
4. Output ONLY the rewritten text. Do not include conversational filler.  
   \<|im\_end|\>  
   \<|im\_start|\>user

# **MANDATED PHRASE TO INSERT:**

"{exact\_phrase}"

# **ORIGINAL SECTION TEXT:**

{section\_text}  
\<|im\_end|\>  
\<|im\_start|\>assistant

## **Confidence Gating and Log-Probability Calibration**

Because Gemma 4-E2B acts as an automated auditor, identifying when the model is uncertain is critical to preventing silent compliance failures. Phase 4 requires a mechanism to flag outputs for human review if the model's confidence falls below a specific threshold.  
A common anti-pattern in prompt engineering is explicitly instructing the LLM to output a confidence score within its JSON payload (e.g., "confidence": 0.85). Small language models are famously poorly calibrated when asked to self-evaluate certainty; they exhibit extreme overconfidence and will routinely assign 99% confidence intervals to catastrophic hallucinations.  
Conversely, document-level perplexity is an invalid metric for this specific classification task. Perplexity measures how well the model predicts the *input* text based on its training distribution. A poorly written, highly idiosyncratic Phase 3 draft will naturally generate high perplexity scores. However, a high perplexity score does not indicate that the model is uncertain about its *compliance classification*; it simply means the input text was statistically surprising.  
The mathematically sound method for confidence gating in a classification pipeline is analyzing the log-probabilities (logprobs) of the specific tokens generated for the JSON values.17 Because llama.cpp supports returning logprobs via its API inference endpoints, the SemanticChecker can inspect the probability distribution of the exact token generated for the "compliance\_status" key.  
If the model outputs "fail", the engine queries the logprobs to determine how certain the model was. If the logprob distribution reveals that the model was equally divided between generating "fail" (e.g., 51% probability) and "pass" (e.g., 49% probability), the system calculates an inherent uncertainty score. Any decision where the delta between the top two logprobs falls below a predefined margin of error is immediately flagged for mandatory human review. This ensures that borderline compliance assessments are never silently accepted by the automated pipeline.

## **Jurisdiction Schema Evolutions: YAML Updates for 2026**

Regulatory environments are continuously evolving to reflect new scientific consensus, legislative changes, and streamlined planning processes. Based on the provided research findings detailing impending regulatory shifts, the YAML schemas for three specific jurisdictions require immediate, extensive updates to maintain validity through 2026\.

### **England: Historic England MoRPHE CL3/CL4**

Historic England governs archaeological interventions through the Management of Research Projects in the Historic Environment (MoRPHE) framework.18 The compliance YAML must be restructured to reflect three critical guidance renewals affecting project designs, reporting, and marine archaeology integration:

1. **Environmental Archaeology Standards**: A new third edition titled *Environmental Archaeology: A Guide to the Theory and Practice of Methods, from Sampling and Recovery to Post-excavation* was published on December 20, 2025\.20 All references in Phase 3 drafts to the obsolete 2011 second edition must be programmatically prohibited, and exact phrases must mandate citations to the 2025 edition.  
2. **Waterlogged Wood**: Updated, specialized guidance on the excavation, recording, and conservation of waterlogged archaeological wood was published heavily in advance of the new year, on December 12, 2025\.21  
3. **Managing Archaeology in London (GLAAS)**: Published on February 18, 2026, this guidance shifts to a bifurcated structure (Part 1: Policy and Process, Part 2: Appendices).23 The updated London Plan policies emphasize public benefit and sustainable heritage asset integration, meaning reports submitted under GLAAS must now elevate discussions of public benefit to a mandatory structural section.24

**YAML Implementation for historic\_england\_morphe.yaml**:

YAML  
jurisdiction\_name: "Historic England MoRPHE"  
framework\_version: "2026.1"

mandatory\_sections:  
  \- "Non-technical Summary"  
  \- "Introduction"  
  \- "Methodology"  
  \- "Results"  
  \- "Environmental Assessment"  
  \- "Statement of Public Benefit" \# Mandated per GLAAS 2026 updates  
  \- "Discussion"  
  \- "Archive Preparation"

prohibited\_terms:  
  \# Lexical bans on obsolete guidance references  
  \- "Environmental Archaeology (2011)"  
  \- "English Heritage (2011)"  
  \- "Waterlogged Wood (2010)"  
  \- "Waterlogged Wood (2018)"

exact\_phrases:  
  Environmental Assessment:  
    \# Forces deterministic verification of the December 2025 publication  
    \- "Assessment of environmental remains was undertaken in accordance with Historic England (2025) Environmental Archaeology: A Guide to the Theory and Practice of Methods, from Sampling and Recovery to Post-excavation (third edition)."  
  Results:  
    \- "Waterlogged wood was recorded according to Historic England (2025) Waterlogged Wood guidelines."

### **The Netherlands: KNA 5.0**

The *Kwaliteitsnorm Nederlandse Archeologie* (KNA) is undergoing a systemic, nationwide transformation to version 5.0, managed by the Centraal College van Deskundigen (CCvD).26 The previous iterations of the KNA (versions 4.1 and 4.2) were criticized for being rigid and stifling to innovation.27 In response, KNA 5.0 explicitly abolishes the monolithic reporting structure in favor of a highly modular system (*modulaire opzet*) designed to align strictly with the specific research questions of a given site rather than a standardized template.26  
Furthermore, specific core guidelines (*Leidraden*) for coring and trenching (*Karterend Booronderzoek en Proefsleuvenonderzoek*) were definitively renewed on March 26, 2026\.26 The HOARD pipeline must adapt to the dissolution of monolithic reporting templates, relaxing the mandatory\_sections array to reflect modularity, while enforcing the new citations.  
**YAML Implementation for netherlands\_kna.yaml**:

YAML  
jurisdiction\_name: "KNA 5.0 (Netherlands)"  
framework\_version: "5.0.0"

\# KNA 5.0 shifts away from rigid monolithic reports to modularity.  
\# Hardcoded structural requirements for fieldwork methods are relaxed,   
\# making previously mandatory sections (Booronderzoek, Proefsleuven)   
\# optional dependencies based on project scope.  
mandatory\_sections:  
  \- "Management Summary"  
  \- "Inleiding"  
  \- "Onderzoeksvragen"  
  \- "Conclusie en Selectieadvies"

prohibited\_terms:  
  \- "BRL SIKB 4000 versie 4.1"  
  \- "BRL SIKB 4000 versie 4.2"  
    
exact\_phrases:  
  Methodologie:  
    \# Requires exact string matching for the March 26, 2026 Leidraad publication  
    \- "Uitgevoerd conform KNA Leidraden Karterend Booronderzoek en Proefsleuvenonderzoek (26 maart 2026)."

### **Canada: Ontario (MCM Standards and Guidelines)**

The Ministry of Citizenship and Multiculturalism (MCM) in Ontario instituted the most mathematically rigid policy changes of the three jurisdictions, enacted via the Environmental Registry of Ontario (ERO) posting 026-0216, published on March 6, 2026\.15 This policy push, heavily tied to the Heritage Framework Transformation and the Spring 2025 Red Tape Reduction package, aims to drastically streamline assessment turnaround times.15  
This framework introduces several severe compliance mandates that HOARD must encode:

1. **Exact Verbatim Language (Section 7.9.4)**: ERO 026-0216 dictates precise, unalterable verbatim language for Stage 4 mitigation and site protection recommendations.14 Any deviation in this wording risks rejection by the Ministry's automated screening tools.  
2. **50-Meter Buffer Zones**: A strict new mandate requires a 50m protective buffer to be established around sites retaining further Cultural Heritage Value or Interest (CHVI) at the conclusion of a Stage 2 assessment.31 Remaining areas outside this buffer must be explicitly, legally recommended as "cleared" for development.31  
3. **Site Update Forms (Section 7.12)**: A new standard requires a Site Update Form to be submitted following a Stage 2 inspection, strictly regardless of whether a previously known site was successfully relocated during the fieldwork.14  
4. **Lexical Glossary Updates**: The term "Aboriginal" must be universally updated to "Indigenous" throughout all reports, and all spatial location references to "GPS" must be updated to the modernized "GNSS" (Global Navigation Satellite System).14

| Feature Type | Previous Ontario Standard (2011) | New ERO 026-0216 Standard (2026) |
| :---- | :---- | :---- |
| **Site Update Forms** | Only upon successful relocation / significant alteration. | Mandatory after Stage 2, regardless of successful relocation.14 |
| **Stage 4 Language** | Discretionary language meeting broad guidelines. | Precise, mandated verbatim clauses per Section 7.9.4.14 |
| **Protective Buffers** | Varied based on consultant discretion. | Strict 50m buffer radius mandated around CHVI sites.31 |
| **Lexical Standards** | "Aboriginal", "GPS" | "Indigenous", "GNSS".14 |

**YAML Implementation for ontario\_mcm.yaml**:

YAML  
jurisdiction\_name: "Ontario MCM Standards and Guidelines"  
framework\_version: "2026\_ERO\_026-0216"

mandatory\_sections:  
  \- "Executive Summary"  
  \- "Project Personnel"  
  \- "Project Context"  
  \- "Field Methods"  
  \- "Record of Finds"  
  \- "Analysis and Conclusions"  
  \- "Recommendations"  
  \- "Advice on Compliance with Legislation"  
  \- "Supplementary Documentation" \# Elevated to support mandatory 50m buffer mapping

prohibited\_terms:  
  \- "Ministry of Tourism and Culture"  
  \- "Ministry of Tourism, Culture and Sport"  
  \- "Aboriginal" \# Lexical ban per ERO 026-0216 glossary changes  
  \- "GPS" \# Lexical ban per ERO 026-0216 glossary changes  
  \- "evaluate archaeological potential" \# Phrasing banned; must be "assess archaeological potential"  
    
exact\_phrases:  
  Recommendations:  
    \# ERO 026-0216 Section 7.9.4 Mandated verbiage for partial clearance and buffers  
    \- "A 50m protective buffer has been established around the archaeological site of further cultural heritage value or interest."  
    \- "Areas outside of the protective buffer, that were subject to assessment but of no further archaeological concern, are recommended as cleared."  
    \- "A signed letter has been provided by the landowner or development proponent stating their awareness of the presence and extent of the protected area."  
  Field Methods:  
    \# ERO 026-0216 Section 7.12 Site form mandates  
    \- "A site update form has been submitted to the Ministry for all known archaeological sites within the project area, regardless of successful relocation during Stage 2 fieldwork."

By tightly coupling a programmatic execution engine for topological and lexical rules with the constrained, slot-restricted semantic processing power of Gemma 4-E2B, the Phase 4 pipeline can successfully enforce these complex new regulatory templates while operating safely within the strict limitations of edge-computing hardware.

#### **Works cited**

1. Gemma 4 E2B \- Jetson AI Lab, accessed May 20, 2026, [https://www.jetson-ai-lab.com/models/gemma4-e2b/](https://www.jetson-ai-lab.com/models/gemma4-e2b/)  
2. google/gemma-4-E4B \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/google/gemma-4-E4B](https://huggingface.co/google/gemma-4-E4B)  
3. Run Google Gemma Locally: Ollama Setup Guide, accessed May 20, 2026, [https://localaimaster.com/blog/gemma-local-setup-guide](https://localaimaster.com/blog/gemma-local-setup-guide)  
4. bartowski/gemma-2-2b-it-GGUF \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/bartowski/gemma-2-2b-it-GGUF](https://huggingface.co/bartowski/gemma-2-2b-it-GGUF)  
5. VRAM Calculator: How Much GPU Memory for Your AI Model? | Local AI Master, accessed May 20, 2026, [https://localaimaster.com/tools/vram-calculator](https://localaimaster.com/tools/vram-calculator)  
6. The Math Behind Local LLMs: How to Calculate Exact VRAM Requirements Before You Crash Your GPU \- DEV Community, accessed May 20, 2026, [https://dev.to/bytecalculators/the-math-behind-local-llms-how-to-calculate-exact-vram-requirements-before-you-crash-your-gpu-12n5](https://dev.to/bytecalculators/the-math-behind-local-llms-how-to-calculate-exact-vram-requirements-before-you-crash-your-gpu-12n5)  
7. Gemma 4 Model download issues · Issue \#3448 · huggingface/candle \- GitHub, accessed May 20, 2026, [https://github.com/huggingface/candle/issues/3448](https://github.com/huggingface/candle/issues/3448)  
8. Gemma 4 Fine-tuning Guide | Unsloth Documentation, accessed May 20, 2026, [https://unsloth.ai/docs/models/gemma-4/train](https://unsloth.ai/docs/models/gemma-4/train)  
9. VRAM optimization for gemma 4 : r/LocalLLaMA \- Reddit, accessed May 20, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1sb80yv/vram\_optimization\_for\_gemma\_4/](https://www.reddit.com/r/LocalLLaMA/comments/1sb80yv/vram_optimization_for_gemma_4/)  
10. FINALLY GEMMA 4 KV CACHE IS FIXED : r/LocalLLaMA \- Reddit, accessed May 20, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1sbwkou/finally\_gemma\_4\_kv\_cache\_is\_fixed/](https://www.reddit.com/r/LocalLLaMA/comments/1sbwkou/finally_gemma_4_kv_cache_is_fixed/)  
11. VRAM Calculator for Local Open Source LLMs \- Accurate Memory Requirements 2025, accessed May 20, 2026, [https://localllm.in/blog/interactive-vram-calculator](https://localllm.in/blog/interactive-vram-calculator)  
12. Question about Gemma4 SWA on KCpp vs LlamaCpp · LostRuins koboldcpp · Discussion \#2098 \- GitHub, accessed May 20, 2026, [https://github.com/LostRuins/koboldcpp/discussions/2098](https://github.com/LostRuins/koboldcpp/discussions/2098)  
13. google/gemma-2-2b \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/google/gemma-2-2b](https://huggingface.co/google/gemma-2-2b)  
14. Summary of Updates to the Standards and Guidelines for Consultant Archaeologists, accessed May 20, 2026, [https://ero.ontario.ca/public/2026-03/Summary%20of%202026%20Updates%20to%20the%20Standards%20and%20Guidelines%20for%20Consultant%20Archaeologists.pdf](https://ero.ontario.ca/public/2026-03/Summary%20of%202026%20Updates%20to%20the%20Standards%20and%20Guidelines%20for%20Consultant%20Archaeologists.pdf)  
15. Heritage Framework Transformation: Proposals related to Ontario's Archaeology Program, including targeted changes to the Standards and Guidelines for Consultant Archaeologists | Environmental Registry of Ontario, accessed May 20, 2026, [https://ero.ontario.ca/notice/026-0216](https://ero.ontario.ca/notice/026-0216)  
16. Summary of Updates to the Standards and Guidelines for Consultant Archaeologists \- Planning Committee Meetings, accessed May 20, 2026, [https://pub-hamilton.escribemeetings.com/filestream.ashx?DocumentId=491372](https://pub-hamilton.escribemeetings.com/filestream.ashx?DocumentId=491372)  
17. Benchmarked Gemma 4 E2B: The 2B model beat every larger sibling on multi-turn (70%) : r/LocalLLaMA \- Reddit, accessed May 20, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1sklc53/benchmarked\_gemma\_4\_e2b\_the\_2b\_model\_beat\_every/](https://www.reddit.com/r/LocalLLaMA/comments/1sklc53/benchmarked_gemma_4_e2b_the_2b_model_beat_every/)  
18. Management of Research Projects in the Historic Environment: The MoRPHE Project Managers' Guide | Historic England, accessed May 20, 2026, [https://historicengland.org.uk/images-books/publications/morphe-project-managers-guide/](https://historicengland.org.uk/images-books/publications/morphe-project-managers-guide/)  
19. Management of Research Projects in the Historic Environment, accessed May 20, 2026, [https://historicengland.org.uk/images-books/publications/morphe-project-managers-guide/heag024-morphe-managers-guide/](https://historicengland.org.uk/images-books/publications/morphe-project-managers-guide/heag024-morphe-managers-guide/)  
20. Environmental Archaeology \- A Guide to the Theory and Practice of Methods, from Sampling and Recovery to Post-excavation (third edition) | Historic England, accessed May 20, 2026, [https://historicengland.org.uk/images-books/publications/environmental-archaeology-3rd/](https://historicengland.org.uk/images-books/publications/environmental-archaeology-3rd/)  
21. Environmental Archaeology | Historic England, accessed May 20, 2026, [https://historicengland.org.uk/advice/technical-advice/archaeological-science/environmental-archaeology/](https://historicengland.org.uk/advice/technical-advice/archaeological-science/environmental-archaeology/)  
22. Waterlogged Wood \- Guidance on the excavation, recording, sampling and conservation of ... \- Historic England, accessed May 20, 2026, [https://historicengland.org.uk/images-books/publications/waterlogged-wood/](https://historicengland.org.uk/images-books/publications/waterlogged-wood/)  
23. Publications and Guidance | Historic England, accessed May 20, 2026, [https://historicengland.org.uk/advice/planning/our-planning-services/greater-london-archaeology-advisory-service/publications-guidance/](https://historicengland.org.uk/advice/planning/our-planning-services/greater-london-archaeology-advisory-service/publications-guidance/)  
24. Managing Archaeology in London Part 1: Policy and Process \- Historic England, accessed May 20, 2026, [https://historicengland.org.uk/images-books/publications/managing-archaeology-london/heag335-managing-archaeology-london-pt1/](https://historicengland.org.uk/images-books/publications/managing-archaeology-london/heag335-managing-archaeology-london-pt1/)  
25. Managing Archaeology in London \- Guidance for developers, archaeologists and planners to promote the understanding and enjoyment of our historic environment | Historic England, accessed May 20, 2026, [https://historicengland.org.uk/images-books/publications/managing-archaeology-london/](https://historicengland.org.uk/images-books/publications/managing-archaeology-london/)  
26. KNA 5.0 \- SIKB, accessed May 20, 2026, [https://www.sikb.nl/archeologie/kennisdelen-en-innovatie/kna-5-0](https://www.sikb.nl/archeologie/kennisdelen-en-innovatie/kna-5-0)  
27. Nieuwsbrief Ondertussen in de archeologie nr 12 \- SIKB, accessed May 20, 2026, [https://www.sikb.nl/doc/nieuwsbrievenarcheo/Nieuwsbrief%20Ondertussen%20in%20de%20archeologie%20nr%2012%20-%20juli%202022.pdf](https://www.sikb.nl/doc/nieuwsbrievenarcheo/Nieuwsbrief%20Ondertussen%20in%20de%20archeologie%20nr%2012%20-%20juli%202022.pdf)  
28. Projectplan ontwikkeling KNA 5.0 \- SIKB, accessed May 20, 2026, [https://www.sikb.nl/doc/Projectplan%20KNA%205.0-vs%201.0%20def.pdf](https://www.sikb.nl/doc/Projectplan%20KNA%205.0-vs%201.0%20def.pdf)  
29. KNA Leidraden voor Karterend Booronderzoek en Proefsleuvenonderzoek vernieuwd, accessed May 20, 2026, [https://www.sikb.nl/nieuws/2026/kna-leidraden-voor-karterend-booronderzoek-en-proefsleuvenonderzoek-vernieuwd](https://www.sikb.nl/nieuws/2026/kna-leidraden-voor-karterend-booronderzoek-en-proefsleuvenonderzoek-vernieuwd)  
30. RSS-feeds bodem | Informatiepunt Leefomgeving, accessed May 20, 2026, [https://iplo.nl/thema/bodem/nieuws-bodem/rss-feeds-bodem/](https://iplo.nl/thema/bodem/nieuws-bodem/rss-feeds-bodem/)  
31. Heritage Framework Transformation: Proposals related to Ontario's Archaeology Program, including targeted changes to the Stand, accessed May 20, 2026, [https://pub-hamilton.escribemeetings.com/filestream.ashx?DocumentId=491370](https://pub-hamilton.escribemeetings.com/filestream.ashx?DocumentId=491370)  
32. Digging into Change: Ontario Proposes Updates to Archaeological Assessment Standards, accessed May 20, 2026, [https://davieshowe.com/digging-into-change-ontario-proposes-updates-to-archaeological-assessment-standards/](https://davieshowe.com/digging-into-change-ontario-proposes-updates-to-archaeological-assessment-standards/)  
33. City of Hamilton Report for Information \- Planning Committee Meetings, accessed May 20, 2026, [https://pub-hamilton.escribemeetings.com/filestream.ashx?DocumentId=491369](https://pub-hamilton.escribemeetings.com/filestream.ashx?DocumentId=491369)

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADMAAAAaCAYAAAAaAmTUAAAClklEQVR4Xu2WS8hNURiGX3e59kdKuWWACQMkM9cMFAMDRSK3GDBQLvVTBiYYGBADoVCYUESSkVAu5VYkEoVySyiExPv2rWOv/Z11zj717/NPnKfeTuv91lr722ev9a0FtPg/2Eqd9GYHGU09D7+dylOqvzdLYAX1gOrnA81iBLXImyVyk9rjzUZZC1sy76g/1FtqXq5HnsNUd28GulEfYPNI36lBuR7AvhCLNTKKL6G+UUMjrxAltI46RM2iulJdqNmwB+zMuv6jN/XJmzVQQppH+8szhrpHTaF6uJjyekntdX4STfSe+gxbMimWwhJ54nx9wTfOS7GGGk79hs2zPB9GL9TfF+qvcYXcgXVc6QMRE5AtgSGRr41/PmrX4lT4PQab43YUEzNc2zMeDb6MOmmT1UOfv/IyU4M3MLSLPr+Wq/afmIhsnpgdru3pi+oxVYyCdVrgfM8yZEm0BW9yaBclMom6FrUvozqx666d4pc3PFeQf1AtvsIS2B55c4O3OvJSXKJmRm0VlcfUgdBejGwZ1kNj6nKLOu3NBEr6BdUn8qYHXxWwFqp2H2EbPGYVrLoNpo6EdhHPvOE5iuINPBaWtD8YK0UhVWorzKEuepP0hI3dTL2GVboiCo+ADdQr2CZNMYy6T23zAVgCSmi3D0TobNrozYDGfqEe+kACLU2/z5LcgHXcAnspVSttap0fZ2FlsRYXkP78+hPWw+bVjSJ1b9sPi8/3gQRaFQ29jN56IXUcdiieo9rR2KfXEks9RF4sXWM8Wr66Kg3wgQS7qJ/eLBslpFO92aicn/BmMzjjjZLRBfMH8uW9aUyjxnmzRHT9f+TNZnIXtu/KRMVI56Aqbqeim/dV2CFYFpuog95s0aJFx/kLMzePS3ka6OMAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAZCAYAAAB3oa15AAACq0lEQVR4Xu2WW6hOQRTHl/sllw4vooTcigfliUiRXEq88uCEXB5JCZ1Siie8Uko8yC2hEInjEhHKNYQUilJyyYMk/v9vzXyzzjp7dt9XHsj+1b/W/Nfs75u1Z/bMiFT8v3yBNkIjoYsuF2HuPbTCJ8roAq3ypmEJdAZ6Cu2AenZM1+gOXYG+Qbek+PfumHgCdASaB/UL3jropeSLK2QcdAj65ROB9aKDWgnNFi3iJtTH9OkBHYXmQgOh5dBnkycskP9j4W/ugx5CX6Fd0EdorO2Uo7fooG9DP0LsmSrqbzfezOBtMt7m4Fm2iD4fGQHtNW3CF2LZCrU5ryG4Nv0AyDtRf4jzWXTsPzHED1K6Rgv0ynmHXZvLyDLFtRsmVwA9irNluRB8sjjEV1O6Rtfgc0lFnpiYg+9m2ktN3DRlBfz0Jjgpqf+GEJ9P6Tr07Xrm/3CJDIfajT8Mum/aTVNWAL8Pjy1gW4jPpXQd+tNNe47osvwE7TE+d7hFpt00ZQUUzcAJSf354ZXNwAJvGjgTb6Ghoc2i+H3xu1omHZdYKc0WcEpS/7UhzhVgdyLPaWi1abP/QtOeb+JSygqg+EFazgaftIb4UkrXoc9zJsdl0UM0wv58+5HdJi4lVwDXKv3Bzr8WfDI5xHdTugYPNz6fWwaDoDHO4++MNm3udg2RKyCe0OOd/xz6EGK+QX6Yb1K6Bu80x51nOegN6VxAu4mzjIK+iz7c3+U4OO44101up+ixzwFGOEO8w8Tl0Ff0z4vuTDzgXkMzfEJ0DDxXIryDlcIHimRP3gHQI+iF6GHF2Zpl8pFJ0A3Ry94z6XwyR/ZDB7wZ4IzdE30hraL3pz9CL2ia6FWYh04O3ix5L1ojOgsebpePRdd/ETzxj4nufLyp/pX4DaGioqLiH+M3xOWrDgfZNPkAAAAASUVORK5CYII=>