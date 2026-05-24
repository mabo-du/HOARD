# **Architectural Implementation of Phase 3 for the HOARD Pipeline: Large-Scale Archaeological Report Generation via Qwen3-4B**

The generation of publication-ready archaeological grey literature from raw, digitised field data represents a complex synthesis of natural language generation, spatial reasoning, and domain-specific academic register. Phase 3 of the HOARD pipeline is tasked with transforming disparate Phase 2 outputs—comprising digitised context records, finds catalogues, environmental sample data, and spatial notes—into a cohesive narrative. The deployment of a 4-billion parameter small language model (SLM), specifically the Qwen3-4B-Thinking-2507 (Q4\_K\_M quantization), operating via a local llama.cpp inference server, introduces severe constraints regarding memory (VRAM), context window management, and logic persistence.  
This comprehensive analysis details the optimal system architectures, prompting strategies, and programmatic interventions required to execute Phase 3 effectively. It addresses the synthesis of complex stratigraphic relationships, the chunk-and-merge mechanics for high-volume datasets, the intricacies of host-memory prompt caching, and the programmatic enforcement of structured outputs that bypass the inherent conflicts between chain-of-thought processing and rigid schema generation. The methodology detailed herein is designed to ensure that the output is indistinguishable from human-authored archaeological reports, maintaining strict adherence to jurisdictional templates and empirical objectivity.

## **System Prompt Architecture for Grey Literature Drafting**

The efficacy of a 4-billion parameter SLM in producing formal archaeological literature relies entirely on the structural rigidity of the system prompt. Unlike larger frontier models (e.g., 70B+ parameters) that can intuitively infer the required tone and structure from minimal instructions, a 4B model requires deterministic, highly segmented scaffolding. The system prompt must serve simultaneously as a style guide, a structural template, and an ontological rulebook for archaeological data. Without these strict boundaries, SLMs tend to drift into narrative hallucination, conversational tones, or structurally invalid outputs.

### **Encoding Template Structure and Academic Register**

The output must conform to specific jurisdictional templates, typically moving from executive summaries through site descriptions and results, down to the stratigraphic summaries and conclusions. To encode this in the system prompt, the architecture must utilise explicit XML-style demarcations to separate instructions, templates, and constraints. This segregation prevents the SLM from confusing the meta-instructions with the data it needs to process, a common failure mode in smaller models.  
To maintain a formal academic register, the prompt must explicitly define the stylistic parameters. Language models inherently default to a conversational or overly enthusiastic tone, often injecting narrative fluff (e.g., describing a standard Roman ditch as a "fascinating architectural marvel"). The prompt must strictly forbid such adverbs and enforce the passive voice where appropriate for site descriptions, maintaining objective, empirical descriptions. Furthermore, context number citations must be governed by strict formatting rules. Archaeological conventions dictate that context numbers are treated as proper nouns within the text. The model must be instructed to format these consistently, ensuring that every reference to a specific cut, fill, or layer is bracketed and zero-padded to a minimum of three digits.

| Architectural Component | Purpose within the System Prompt | SLM Failure Mitigated |
| :---- | :---- | :---- |
| \<role\> | Establishes the persona (commercial archaeologist) to anchor the vocabulary distribution toward academic and technical terms. | Prevents generic, conversational, or overly simplistic vocabulary choices. |
| \<tone\_and\_register\> | Explicitly forbids enthusiastic adverbs and mandates the passive voice for descriptive actions. | Prevents narrative fluff (e.g., "Interestingly, the Romans..."). |
| \<formatting\_rules\> | Defines the exact regex-like structure for context numbers (e.g., Context ) and citation styles for finds. | Prevents inconsistent citations (e.g., mixing "Context 1", "c.001", and "Layer 1"). |
| \<stratigraphic\_rules\> | Defines the temporal logic of physical relationships (cuts, overlies, fills). | Prevents chronological inversion during text generation. |
| \<document\_structure\> | Outlines the exact Markdown header hierarchy required by the jurisdictional template. | Prevents the model from inventing arbitrary sections or skipping required summaries. |

### **The Optimal System Prompt Structure**

The following represents the complete, optimal system prompt architecture for Phase 3\. It demonstrates how to partition instructions, enforce the academic register, and define the expected template using the XML-tag methodology. This string must remain entirely static across all inference calls for a given site to maximise prompt caching benefits.  
\<tone\_and\_register\>

1. Maintain a strictly objective, empirical, and formal academic register throughout the entire document.  
2. Do not use conversational language, enthusiastic adverbs (e.g., "interestingly", "remarkably", "surprisingly"), or narrative fluff.  
3. Use the passive voice for actions where the human actor is unknown or irrelevant (e.g., "The ditch was excavated," not "We excavated the ditch").  
4. Present metric data precisely as provided, without estimation or rounding unless explicitly instructed.  
   \</tone\_and\_register\>

\<formatting\_rules\>

1. All context numbers must be enclosed in square brackets and formatted as three digits minimum: e.g., "Context ", "Context ".  
2. Stratigraphic relationships must be described chronologically, moving strictly from the earliest (oldest) events to the latest (youngest) events.  
3. Always integrate finds data and environmental sample results directly into the narrative description of the context from which they were recovered.  
4. Do not invent or hallucinate context numbers or finds that do not exist in the provided dataset.  
   \</formatting\_rules\>

\<stratigraphic\_rules\>  
You must deduce relative chronology strictly from the provided relationships:

* If Context A "cuts" Context B, Context A is LATER/YOUNGER than Context B.  
* If Context A is "above" or "overlies" Context B, Context A is LATER/YOUNGER than Context B.  
* If Context A is a "fill of" Context B, Context A is LATER/YOUNGER than Context B, but represents the immediate subsequent depositional event.  
  \</stratigraphic\_rules\>

\<document\_structure\>  
The final output MUST be formatted in Markdown and strictly follow this hierarchical template. Do not deviate from these headers:

# **Executive Summary**

# **Site Description**

# **Fieldwork Methodology**

# **Results**

## **Phase 1: \[Earliest Period\]**

## **Phase 2:**

# **Stratigraphic Summary**

# **Discussion**

# **Conclusion**

\</document\_structure\>  
This architecture ensures the 4B model operates within a highly constrained conceptual space, significantly reducing the likelihood of stylistic deviations or structural errors during the drafting process.

## **The Dynamics of "Thinking" Mode in Llama.cpp**

The Qwen3-4B-Thinking-2507 model features a hybrid thinking mode, generating chain-of-thought reasoning within \<think\> tags before emitting its final response.1 This capability allows the model to process complex instructions and map out logical sequences before committing tokens to the final output stream. However, for a multi-section archaeological report, the requirement for deep reasoning varies significantly depending on the specific section being drafted.

### **Selective Application of Reasoning Tokens**

For sections such as the Executive Summary, Site Description, and Fieldwork Methodology, the data transformation is largely extractive and summative. Forcing the model into prolonged thinking modes for these descriptive sections wastes critical compute resources and increases the Time to First Token (TTFT) unnecessarily. The model evaluates the prompt and generates thousands of reasoning tokens to plan a simple summary, which is computationally inefficient.3  
Conversely, the Stratigraphic Summary and Discussion sections require complex synthesis, temporal deduction, and the resolution of stratigraphic paradoxes. In these sections, the chain-of-thought mechanism is indispensable. The model must use the \<think\> block to map the relative chronology, resolve the Harris Matrix relationships, and plan the narrative flow before writing the text.  
While the thinking mode is enabled by default in Qwen3 and its hard switch is not directly exposed in standard llama.cpp distributions without manipulating the chat template 1, the Phase 3 pipeline should execute a segmented drafting approach. The report must be drafted section-by-section via separate API calls. To control the depth of reasoning without hard-disabling the feature, the pipeline must utilize prompt-level directives and dynamic sampling parameters.

### **Sampling Parameters for Segmented Drafting**

To optimise generation speed and output precision across different sections, the sampling parameters in the llama-server inference call must be adjusted dynamically. The Qwen3 architecture responds highly to parameter tuning regarding its reasoning verbosity.5

| Report Section Category | Temperature | Top P | Presence Penalty | Reasoning Directive in Prompt | Expected Model Behavior |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Descriptive (Methodology, Site Description)** | 0.6 | 0.95 | 0.0 | "Minimize reasoning. Directly output the factual summary based on the provided data." | Low token count in \<think\> tags; fast generation; highly deterministic text extraction.5 |
| **Analytical (Stratigraphic Summary, Discussion)** | 1.0 | 0.95 | 1.5 | "Use the thinking block to map the complete chronological sequence of contexts before writing the draft." | High token count in \<think\> tags; deep spatial-temporal mapping; nuanced narrative generation.5 |
| **Data Formatting (Bibliography, Context Lists)** | 0.1 | 0.10 | 0.0 | "Format the provided data exactly as instructed without additional commentary." | Near-zero reasoning; strict adherence to syntax and formatting rules. |

By adjusting these parameters via the /v1/chat/completions payload for each specific section, the HOARD pipeline can force deep reasoning where it matters most, while conserving VRAM and processing time on standard descriptive tasks.

## **Harris Matrix Interpretation and Stratigraphic Reasoning**

A critical failure point for SLMs processing archaeological data is the misinterpretation of the Harris Matrix—the directed acyclic graph (DAG) that represents the stratigraphic sequence of a site.7 Phase 5 of the HOARD pipeline generates the visual matrix, but Phase 3 must interpret the raw textual relationships from the context sheets to write the narrative synthesis.

### **Theoretical Underpinnings and LLM Limitations**

The Law of Superposition dictates that in a series of layers, the upper units of stratification are younger and the lower are older, assuming standard depositional environments.7 Furthermore, the Law of Stratigraphic Succession dictates that a unit's place in the sequence is defined by its position between the undermost of all units above it and the uppermost of all units below it.7 Crucially, while stratigraphic units meet physically in space, this does not automatically imply they meet contiguously in time.8 There may be significant temporal gaps between a cut being made and its primary fill being deposited.  
Language models, particularly those in the 4-billion parameter class, struggle inherently with spatial and graph-based reasoning. They process data as a linear, autoregressive sequence of tokens. When presented with a raw list of relationships (e.g., "001 cuts 002", "002 overlies 003", "004 cuts 003"), the model often loses track of the transitive properties of the graph. This leads to severe chronological hallucinations, such as the model stating that Context is younger than Context , directly contradicting the temporal logic of the site.

### **Prompting Formats for Stratigraphic Superposition**

To guard against these stratigraphic reasoning errors, the Phase 2 dataset fed into Phase 3 must not rely on the LLM to deduce the entire DAG from raw textual descriptions. SLMs are not graph calculators. The data must be pre-processed into a format that explicitly defines the topological sort of the contexts before the prompt is constructed.  
The optimal format combines explicit natural language with structural JSON arrays. Presenting the data purely as a mathematical adjacency matrix fails because SLMs are poor at raw matrix mathematics. Presenting it purely as natural language invites narrative confusion and attention drift over long contexts. The Phase 2 output injected into the Phase 3 prompt should format context relationships by explicitly segregating physical actions from temporal placement.

JSON  
{  
  "context\_id": "005",  
  "type": "Cut",  
  "interpretation": "Boundary Ditch",  
  "dimensions": "Length: 14m, Width: 1.2m, Depth: 0.6m",  
  "stratigraphic\_relationships": {  
    "relative\_chronology\_phase": "Mid-Roman",  
    "stratigraphically\_younger\_than\_BEFORE": \["001", "002"\],  
    "stratigraphically\_older\_than\_AFTER": \["008", "009"\],  
    "physical\_relationships": \[  
      {"target\_context": "001", "relation\_type": "cuts"},  
      {"target\_context": "008", "relation\_type": "filled\_by"}  
    \]  
  },  
  "finds\_summary": "Two sherds of Samian ware recovered from the basal interface."  
}

By explicitly pre-calculating and providing the stratigraphically\_younger\_than and older\_than arrays during Phase 2, the prompt offloads the heavy graph traversal calculations from the SLM. The model is then only required to translate these explicit temporal markers into narrative prose, a linguistic task at which even 4B SLMs excel. The variable instruction appended to the prompt for the Stratigraphic Summary section must explicitly guide the model's attention to these arrays: *"When synthesizing the Stratigraphic Summary, group the contexts strictly by their relative chronology phase, beginning with the oldest events. Rely exclusively on the 'stratigraphically\_older\_than' and 'younger\_than' arrays to establish the timeline, using the 'physical\_relationships' only for descriptive flavor."*

## **Chunk-and-Merge Strategy for High-Volume Datasets (\>500 Contexts)**

A standard commercial excavation dataset containing over 500 contexts, combined with extensive finds catalogues, environmental sample results, and photo registers, will inevitably exceed the practical operating limits of a 4B SLM running on 6 GB VRAM. While Qwen3-4B and llama.cpp can theoretically support context windows between 65,000 and 85,000 tokens when using aggressive quantization like Q4\_K\_M 9, real-world performance degrades severely at these upper boundaries. Prompt processing times (TTFT) become untenable, and the model's attention mechanism begins to suffer from the "lost in the middle" phenomenon, where critical stratigraphic links buried in the center of the context window are ignored.  
Processing a massive archaeological dataset requires a highly programmatic "chunk-and-merge" strategy. The fundamental challenge unique to archaeology is that splitting a dataset arbitrarily (e.g., by alphabetical order, raw numerical splits, or naive token counting) destroys the cross-chunk stratigraphic context. If Context in Chunk 2 cuts Context in Chunk 1, the model processing Chunk 2 has absolutely no knowledge of Context 's nature, dimensions, or period. This leads to critical narrative gaps and prevents the model from accurately describing the interaction between the two features.

### **Topological Partitioning and Boundary Contexts**

To split the dataset without losing cross-chunk context, the partitioning algorithm must respect the stratigraphic graph. The dataset should be chunked using a combination of **Topological Partitioning** and the injection of **Ghost Contexts** (or boundary contexts).

1. **Chronological Phase Chunking:** The primary partition must be chronological. All contexts belonging to Phase 1 (e.g., Iron Age) form Chunk 1\. Phase 2 (Roman) forms Chunk 2\. This ensures that the bulk of interdependent relationships are contained within the same inference call.  
2. **Spatial Sub-Partitioning:** If a single chronological phase is still too large for the token limit, the data must be sub-partitioned by spatial grid, trench number, or specific excavation area.

To resolve the cross-chunk dependency problem, the pipeline must programmatically identify boundary crossing edges in the Harris Matrix. Before Chunk 2 is sent to the LLM, a pre-processing script queries the DAG for any physical relationships that cross the chunk boundary. If Chunk 2 contains Context A, and Context A cuts Context B (which resides in Chunk 1), a condensed, read-only summary of Context B must be appended to the context payload of Chunk 2\.  
The payload for subsequent chunks must carry forward this state. The context information carried forward should include a high-level summary of the previous chunk's narrative, plus the specific ghost contexts required for the current chunk's physical relationships.

### **Implementation of the Chunking Algorithm**

The following logic demonstrates how to structure the data payloads to preserve stratigraphic integrity across multiple API calls.

Python  
def prepare\_chunk\_payload(current\_phase\_contexts, previous\_phase\_graph, max\_tokens):  
    """  
    Prepares a dataset chunk for the LLM, injecting ghost contexts   
    to preserve cross-phase stratigraphic relationships.  
    """  
    active\_dataset \=  
    ghost\_contexts \= {}

    for context in current\_phase\_contexts:  
        active\_dataset.append(context)  
          
        \# Check all physical relationships for cross-boundary edges  
        for rel in context\['stratigraphic\_relationships'\]\['physical\_relationships'\]:  
            target\_id \= rel\['target\_context'\]  
              
            \# If the target context is not in the current chunk, fetch it as a ghost  
            if target\_id not in \[c\['context\_id'\] for c in current\_phase\_contexts\]:  
                if target\_id in previous\_phase\_graph:  
                    \# Create a minimized, read-only version of the context  
                    ghost\_contexts\[target\_id\] \= {  
                        "context\_id": target\_id,  
                        "type": previous\_phase\_graph\[target\_id\]\['type'\],  
                        "note": "Fully described in previous phase. Provided here for relationship context only."  
                    }

    payload \= {  
        "active\_contexts\_to\_describe": active\_dataset,  
        "ghost\_contexts\_from\_previous\_phases": list(ghost\_contexts.values())  
    }  
      
    return json.dumps(payload)

This ensures the SLM understands exactly what Context is interacting with, without requiring the massive token weight of the entire Chunk 1 dataset. The model reads the ghost context, recognizes it as a previously established entity, and accurately integrates it into the description of the active context.

### **The Editorial Merge Pass Mechanics**

Once the LLM has generated draft sections for each individual chunk (e.g., drafting Phase 1, then Phase 2, then Phase 3), these sub-documents must be merged into a single cohesive report. Concatenating them programmatically is insufficient. Simple concatenation results in jarring narrative transitions, redundant introductory sentences at the start of each phase, and a lack of overarching synthesis.  
A final "Merge Pass" inference call is required. Because the generated drafts are natural language summaries rather than dense JSON data arrays, the combined drafts will fit comfortably within a standard context window, circumventing the initial capacity constraints.  
The Merge Pass prompt must be structurally distinct from the initial drafting prompt. It must operate with a much lower temperature parameter (e.g., 0.3) to prevent the hallucination of new data, forcing the model to act strictly as a copy editor rather than a primary author.  
*Merge Pass Prompt Architecture:*  
You are the Lead Editor for an archaeological grey literature report.  
Below are sequentially generated drafts of the "Stratigraphic Summary" section, representing different chronological phases of the excavation site.  
Your task is to merge these disjointed drafts into a single, cohesive, flowing narrative.  
\<editorial\_constraints\>

1. Do NOT alter any context numbers, metric dimensions, or stratigraphic relationships.  
2. Do NOT add new archaeological interpretations or historical context that is not present in the provided drafts.  
3. Smooth the narrative transitions between the chronological phases. Ensure the text flows logically from the earliest phase to the latest.  
4. Remove redundant introductory sentences from the beginning of sub-sections (e.g., delete repetitive phrases like "This section describes the contexts belonging to Phase 2").  
5. Ensure formatting remains perfectly aligned with the requested Markdown structure.  
   \</editorial\_constraints\>

This two-tiered architecture—topological chunking with ghost context injection, followed by a low-temperature editorial merge pass—guarantees both data integrity across large sites and a highly polished, professional final document.

## **Prompt Caching Mechanics with Llama.cpp**

The HOARD pipeline's Phase 3 design inherently involves multiple sequential inference calls against the same static dataset. Whether drafting different report sections separately (e.g., generating the Methodology, then the Results, then the Discussion) or querying specific finds catalogues, the core dataset remains identical. Reprocessing a 30,000-token archaeological dataset for every single section draft would result in catastrophic compute inefficiencies and untenable TTFT (Time to First Token) delays, rendering the pipeline useless for rapid deployment.  
llama.cpp and its HTTP server counterpart, llama-server, provide highly robust prompt caching mechanisms designed specifically to mitigate this bottleneck. However, the precise configuration of host-memory caching and exact-match prefix routing is required to maximise throughput, particularly when operating near the absolute VRAM limits of a 6 GB environment.

### **Host-Memory Prompt Caching Architecture**

Host-memory prompt caching is an optimization feature in llama-server that allows the system to store pre-computed prompt representations (the Key-Value or KV cache) in the system RAM rather than relying exclusively on the highly constrained GPU VRAM.10 When a new API request is received, the server evaluates the incoming prompt to see if its initial tokens match a state currently stored in the system RAM. If a sufficient prefix match is found, the server executes a hot-swap, pulling the cached prefix from RAM back into the active GPU context, thereby bypassing the computationally expensive prompt evaluation phase for those tokens entirely.10  
This architecture is controlled via specific Command Line Interface (CLI) parameters during the initial llama-server startup sequence.

| llama-server Parameter | Function in the HOARD Pipeline | Recommended Configuration |
| :---- | :---- | :---- |
| \-c \<tokens\> or \--ctx-size | Defines the maximum total context size the server can handle per slot. | \-c 65536\. Must be large enough to accommodate the dataset chunk plus the generated output.9 |
| \--cram \<MB\> | Controls the amount of system RAM allocated for storing the host-memory KV cache. | \--cram 2048\. Allocating 2GB of system RAM ensures the massive JSON dataset can remain hot across multiple section requests.10 |
| \-np \<slots\> | Defines the number of concurrent processing slots the server maintains. | \-np 2\. Even for sequential script processing, having multiple slots prevents immediate cache eviction if a malformed request is sent.11 |
| \-sps \<float\> | Controls the slot assignment based on prompt similarity. | \-sps 0.5. Default behavior. Assigns a slot if at least 50% of the prompt context matches the cache.13 |
| \--system-prompt-file | Loads a static file to be cached identically across all slots. | Optional. Can be used to permanently cache the \<role\> and \<tone\_and\_register\> XML blocks.10 |

### **Prefix Matching and the Exact String Constraint**

The fundamental operational rule of llama.cpp prompt caching is that the cache hit relies on strict, exact string matching (byte-for-byte, including all whitespace, tabs, and punctuation) starting from the very first token.11 The server processes the incoming string until it finds the first token that diverges from the cached state. From that divergence point onward, it must compute the remaining tokens conventionally.  
This dynamic presents a significant architectural trap for developers building automated pipelines. If the script injects dynamic data at the beginning of the prompt—such as a timestamp, a unique request ID, or dynamic telemetry headers (a known issue that causes complete cache flushes in downstream tools like Claude Code 14)—the exact match fails immediately at token one. Consequently, the entire KV cache is invalidated, and the 30,000-token dataset must be re-evaluated from scratch.13  
Furthermore, when utilizing the llama-server OpenAI-compatible API endpoint (/v1/chat/completions), the HTTP request payload must explicitly include the parameter "cache\_prompt": true to instruct the server to leverage the cached slots.13 Without this parameter, older versions of the server may default to reprocessing the context.15

### **Structuring HOARD Prompts for Maximum Caching Efficiency**

To maximize prompt caching benefits, the Phase 3 prompt architecture must be strictly ordered from the most static elements to the most variable elements. While the theoretical minimum prefix length to trigger a cache hit is just one token, practical performance benefits only emerge when thousands of tokens are successfully bypassed. The longer the static prefix, the higher the efficiency gains.  
The optimal assembly order for the Phase 3 inference calls must follow this strict hierarchy:

1. **Static System Prompt:** The XML-tagged rules for role, tone, register, and formatting. This is identical across every call for the entire project.  
2. **Static Site Dataset:** The massive JSON array of context records, finds, and ghost contexts. This remains identical for the specific chunk being processed.  
3. **Variable Section Instruction:** The specific, dynamic command dictating what the model should generate (e.g., "Draft the Methodology" or "Draft the Results").

By placing the variable instruction at the absolute end of the prompt payload, the first 95-99% of the token sequence remains identical across sequential API calls.  
*Concrete Implementation Example:*  
**1\. Server Startup Execution:**

Bash  
./llama-server \\  
  \--model./models/Qwen3-4B-Thinking-2507-Q4\_K\_M.gguf \\  
  \--ctx-size 65536 \\  
  \--cram 2048 \\  
  \--np 2 \\  
  \--flash-attn \\  
  \--port 8080 \\  
  \--log-disable

**2\. API Request Structure (Python Integration):**

Python  
import requests  
import json  
import time

\# 1\. Static Prefix (System Rules)  
system\_rules \= """\<role\>You are an expert commercial archaeologist...\</role\>  
\<formatting\_rules\>...\</formatting\_rules\>"""

\# 2\. Static Context Data (Massive payload loaded from disk)  
with open("phase2\_output\_chunk1.json", "r") as file:  
    site\_dataset \= file.read()

\# 3\. Variable Instructions  
instruction\_methodology \= "\<instruction\>Task: Generate the Fieldwork Methodology section based exclusively on the data provided above.\</instruction\>"  
instruction\_results \= "\<instruction\>Task: Generate the Results section based exclusively on the data provided above.\</instruction\>"

def request\_report\_section(instruction\_text):  
    payload \= {  
        "model": "Qwen3-4B-Thinking",  
        "messages": \[  
            {"role": "system", "content": system\_rules},  
            {"role": "user", "content": f"\<dataset\>\\n{site\_dataset}\\n\</dataset\>\\n\\n{instruction\_text}"}  
        \],  
        "stream": False,  
        "cache\_prompt": True, \# CRITICAL: Forces exact-match cache reuse   
        "temperature": 0.6,  
        "presence\_penalty": 0.0  
    }  
      
    start\_time \= time.time()  
    response \= requests.post(  
        "http://localhost:8080/v1/chat/completions",  
        headers={"Content-Type": "application/json"},  
        data=json.dumps(payload)  
    )  
    print(f"Request completed in {time.time() \- start\_time:.2f} seconds")  
    return response.json()

\# Initial Inference Call: Processes all 30k tokens.   
\# Result: Evaluates full prompt, creates new KV cache. (Takes \~45 seconds TTFT)  
methodology\_draft \= request\_report\_section(instruction\_methodology)

\# Subsequent Inference Call: Cache hit on System Rules \+ Dataset.   
\# Result: Only processes the short instruction suffix. (Takes \~0.5 seconds TTFT)  
results\_draft \= request\_report\_section(instruction\_results)

In the execution logs of the llama-server, the second request will trigger an update\_slots entry indicating a massive token match rate (e.g., n\_past \= 30500, n\_tokens \= 25). This confirms that the bulky archaeological dataset was successfully hot-swapped from the host RAM cache, allowing the model to begin generating the Results section almost instantly.13

## **Phase 3 Output Format and Compliance Validation**

Phase 3 is not the final terminus in the HOARD pipeline. The drafted narrative must be ingested by Phase 4 for rigorous compliance refinement, where the generated text is cross-referenced against strict jurisdictional guidelines, such as the Chartered Institute for Archaeologists (CIfA) reporting standards. This downstream requirement heavily dictates the necessary structural format of the Phase 3 output.

### **The Superiority of Structured JSON over Monolithic Markdown**

While the ultimate deliverable intended for human consumption is a formatted Markdown document, Phase 3 should **not** output a single contiguous Markdown blob. If the 4B SLM generates a single monolithic file, the Phase 4 compliance module is forced to rely on fragile regex parsing or highly expensive secondary LLM calls merely to locate specific sections for checking. This approach is highly error-prone; if the SLM slightly alters a header format (e.g., generating \#\#\# Site Description instead of \#\# Site Description), the regex fails, and the compliance pipeline collapses.  
Instead, Phase 3 must be programmatically forced to output structured JSON, where the requested section titles operate as keys, and the drafted Markdown contents are the values. This deterministic schema allows the Phase 4 compliance module to efficiently target, extract, evaluate, and correct individual sections programmatically without relying on text parsing.  
*Target Schema Design for Phase 4 Ingestion:*

JSON  
{  
  "report\_section": "Stratigraphic Summary",  
  "markdown\_content": "\#\# Phase 1: Iron Age\\n\\nThe earliest activity on site was represented by Context , a boundary ditch traversing the northern limit of excavation..."  
}

### **Resolving the Qwen3 \<think\> Tag Conflict via GBNF Grammars**

Enforcing strict JSON schema outputs with a specialized thinking model like Qwen3-4B-Thinking-2507 presents a severe architectural conflict. The llama-server natively supports structured JSON generation via the response\_format parameter, accepting either json\_schema or json\_object configurations.17 However, when a Qwen3 model receives a prompt, its fundamental operational behavior is to immediately open a \<think\> block, pouring its chain-of-thought tokens into the stream before emitting the final answer.2  
If the llama-server API is instructed to strictly enforce a JSON schema via the standard OpenAI-compatible parameters, it will violently reject the \<think\> tag because it violates the formal JSON object definition (a valid JSON payload must initiate with a {, not a \<). This constraint violation causes the model generation to crash, enter an infinite loop, or output heavily malformed text as it fights against the schema constraints.2  
Because the hard switch to cleanly disable thinking mode (enable\_thinking=False) is not natively exposed in the llama.cpp API endpoints without implementing complex custom chat templates 1, the Phase 3 pipeline must employ a sophisticated workaround leveraging **GBNF (GGML BNF) Grammars**.2  
The llama.cpp grammar engine allows developers to define exact regular expressions and token sequences that the model is permitted to output, overriding the standard tokenizer rules. To allow Qwen3 to utilise its reasoning capabilities while guaranteeing a strict JSON output immediately afterward, a custom grammar rule must be constructed that explicitly permits the \<think\>...\</think\> block to precede the JSON object in the output stream.  
Using the json\_schema\_to\_grammar.py utility provided in the core llama.cpp repository, the target JSON schema is converted into a base grammar format.2 A root rule is then manually prepended to the top of the grammar definition to handle the reasoning format cleanly.  
*Implementation of the GBNF Grammar Workaround:*

Python  
import json\_schema\_to\_grammar

\# Define the target schema  
schema \= {  
    "type": "object",  
    "properties": {  
        "report\_section": {"type": "string"},  
        "markdown\_content": {"type": "string"}  
    },  
    "required": \["report\_section", "markdown\_content"\],  
    "additionalProperties": False  
}

\# Convert Python schema to GBNF format  
converter \= json\_schema\_to\_grammar.SchemaConverter(  
    prop\_order={}, allow\_fetch=False, dotall=False, raw\_pattern=False  
)  
converter.visit(schema, 'json-schema')  
json\_grammar \= converter.format\_grammar()

\# The base rules explicitly allow the \<think\> block, capturing all tokens   
\# inside it, followed by any whitespace, followed by the strict JSON schema.  
base\_rules \= """  
root ::= "\<think\>" \[^\<\]+ "\</think\>" \[\\\\n\]\* json-schema  
"""

\# Combine into the final grammar payload  
final\_grammar \= base\_rules \+ json\_grammar

\# Pass via the extra\_body parameter in the API call, ignoring response\_format  
params \= {  
    "model": "Qwen3-4B-Thinking",  
    "messages": prompt\_messages,  
    "extra\_body": {  
        "grammar": final\_grammar  
    }  
}

This configuration achieves the best of both computational paradigms. It allows the 4B SLM to freely utilise its reasoning tokens to map the complex Harris Matrix relationships and plan its narrative structure within the \<think\> block, while simultaneously guaranteeing that the final output payload is a perfectly formatted, Phase 4-compliant JSON object containing the Markdown draft. The downstream systems can then easily strip away the \<think\> block using simple string splitting, ingesting only the clean JSON payload.

## **Synthesis and Operational Outlook**

The deployment of a 4-billion parameter small language model for automated archaeological report drafting is a highly viable but structurally demanding endeavour. The success of Phase 3 of the HOARD pipeline hinges not on the innate, generalized reasoning power of the model, but on the meticulous, deterministic scaffolding built around it. Operating within severe hardware constraints necessitates a departure from standard, conversational LLM interaction patterns.  
By flattening the complex spatial dimensions of the Harris Matrix into explicit temporal arrays within the Phase 2 data payload, the pipeline successfully circumvents the topological hallucination tendencies inherent in small models. The burden of graph traversal is shifted to programmatic pre-processing, allowing the SLM to focus purely on its strength: natural language synthesis. Furthermore, implementing a topological chunk-and-merge strategy with the injection of boundary ghost contexts ensures that massive commercial datasets can be processed iteratively without exceeding VRAM constraints or sacrificing critical cross-cutting physical relationships.  
At the infrastructure level, optimizing the llama-server's host-memory prompt caching transforms a process that would otherwise require hours of repetitive token evaluation into a streamlined sequence of rapid, suffix-only generations. By rigorously ordering the prompt payload to protect the static prefix from dynamic data pollution, the pipeline achieves maximal compute efficiency. Finally, the strategic application of GBNF grammars elegantly reconciles the conflict between Qwen3's reasoning mechanisms and the rigid JSON structural requirements of downstream compliance modules. Through these integrated architectural interventions, Phase 3 establishes a robust, highly scalable mechanism for translating raw, digitised archaeological data into formal, publication-ready grey literature, setting a new benchmark for automated reporting in the heritage sector.

#### **Works cited**

1. Qwen3: Think Deeper, Act Faster | Qwen, accessed May 20, 2026, [https://qwenlm.github.io/blog/qwen3/](https://qwenlm.github.io/blog/qwen3/)  
2. JSON output from Deepseek R1 and distills with llama.cpp \- Sadiq Jaffer, accessed May 20, 2026, [https://toao.com/blog/json-output-from-deepseek-r1-and-distills-with-llamacpp](https://toao.com/blog/json-output-from-deepseek-r1-and-distills-with-llamacpp)  
3. Offline Agentic coding with llama-server · ggml-org llama.cpp · Discussion \#14758 \- GitHub, accessed May 20, 2026, [https://github.com/ggml-org/llama.cpp/discussions/14758](https://github.com/ggml-org/llama.cpp/discussions/14758)  
4. llama.cpp \- Qwen, accessed May 20, 2026, [https://qwen.readthedocs.io/en/v3.0/run\_locally/llama.cpp.html](https://qwen.readthedocs.io/en/v3.0/run_locally/llama.cpp.html)  
5. Qwen3.5 \- How to Run Locally | Unsloth Documentation, accessed May 20, 2026, [https://unsloth.ai/docs/models/qwen3.5](https://unsloth.ai/docs/models/qwen3.5)  
6. llama.cpp \- Qwen \- Read the Docs, accessed May 20, 2026, [https://qwen.readthedocs.io/en/latest/run\_locally/llama.cpp.html](https://qwen.readthedocs.io/en/latest/run_locally/llama.cpp.html)  
7. Harris matrix \- Wikipedia, accessed May 20, 2026, [https://en.wikipedia.org/wiki/Harris\_matrix](https://en.wikipedia.org/wiki/Harris_matrix)  
8. The Matrix: Connecting Time and Space in Archaeological Stratigraphic Records and Archives, accessed May 20, 2026, [https://intarch.ac.uk/journal/issue55/8/full-text.html](https://intarch.ac.uk/journal/issue55/8/full-text.html)  
9. Everything I've learned so far about running local LLMs, accessed May 20, 2026, [https://nullprogram.com/blog/2024/11/10/](https://nullprogram.com/blog/2024/11/10/)  
10. \[Tutorial\] Mastering Host-Memory Prompt Caching in llama-server ..., accessed May 20, 2026, [https://github.com/ggml-org/llama.cpp/discussions/20574](https://github.com/ggml-org/llama.cpp/discussions/20574)  
11. Tutorial: Reusing Multiple Prompt Prefixes with slots ( \-np ) in llama-server \#15530 \- GitHub, accessed May 20, 2026, [https://github.com/ggml-org/llama.cpp/discussions/15530](https://github.com/ggml-org/llama.cpp/discussions/15530)  
12. How to cache system prompt? \#8947 \- ggml-org llama.cpp \- GitHub, accessed May 20, 2026, [https://github.com/ggml-org/llama.cpp/discussions/8947](https://github.com/ggml-org/llama.cpp/discussions/8947)  
13. Tutorial: KV cache reuse with llama-server · ggml-org llama.cpp · Discussion \#13606 · GitHub, accessed May 20, 2026, [https://github.com/ggml-org/llama.cpp/discussions/13606](https://github.com/ggml-org/llama.cpp/discussions/13606)  
14. PSA: Using Claude Code without Anthropic: How to fix the 60-second local KV cache invalidation issue. : r/LocalLLaMA \- Reddit, accessed May 20, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1s7tn5s/psa\_using\_claude\_code\_without\_anthropic\_how\_to/](https://www.reddit.com/r/LocalLLaMA/comments/1s7tn5s/psa_using_claude_code_without_anthropic_how_to/)  
15. Caching (some) prompts when using llama-server : r/LocalLLaMA \- Reddit, accessed May 20, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1fkv940/caching\_some\_prompts\_when\_using\_llamaserver/](https://www.reddit.com/r/LocalLLaMA/comments/1fkv940/caching_some_prompts_when_using_llamaserver/)  
16. Misc. bug: \--cache-reuse no longer seems to be caching prompt prefixes · Issue \#15082 · ggml-org/llama.cpp \- GitHub, accessed May 20, 2026, [https://github.com/ggml-org/llama.cpp/issues/15082](https://github.com/ggml-org/llama.cpp/issues/15082)  
17. Misc. bug: "response\_format" on the OpenAI compatible "v1/chat/completions" issue · Issue \#11847 · ggml-org/llama.cpp \- GitHub, accessed May 20, 2026, [https://github.com/ggml-org/llama.cpp/issues/11847](https://github.com/ggml-org/llama.cpp/issues/11847)  
18. Misc. bug: \`json\_schema\` under \`response\_format\` is not working on OpenAI compatible API endpoint \`v1/chat/completions\` · Issue \#11988 · ggml-org/llama.cpp \- GitHub, accessed May 20, 2026, [https://github.com/ggml-org/llama.cpp/issues/11988](https://github.com/ggml-org/llama.cpp/issues/11988)  
19. Best config for Qwen3.6 27b / llama.cpp / opencode : r/LocalLLaMA \- Reddit, accessed May 20, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1ssp9kq/best\_config\_for\_qwen36\_27b\_llamacpp\_opencode/](https://www.reddit.com/r/LocalLLaMA/comments/1ssp9kq/best_config_for_qwen36_27b_llamacpp_opencode/)  
20. Is there any Structured output library that works with llama-server without llama-cpp-python? : r/LocalLLaMA \- Reddit, accessed May 20, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1f2kq4n/is\_there\_any\_structured\_output\_library\_that\_works/](https://www.reddit.com/r/LocalLLaMA/comments/1f2kq4n/is_there_any_structured_output_library_that_works/)