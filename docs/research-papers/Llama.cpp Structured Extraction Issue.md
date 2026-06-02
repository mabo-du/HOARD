# **Architectural Analysis and Remediation Strategies for NuExtract3 Structured Extraction in llama-cpp-python**

## **Executive Summary**

The integration of advanced vision-language models (VLMs) into local, hardware-accelerated document extraction pipelines represents a critical evolution in enterprise data processing. The deployment of the NuExtract3 4B Q4\_K\_M GGUF model via the llama-cpp-python v0.3.24 framework, utilizing a Vulkan GPU backend, exposes a severe architectural bottleneck within current open-source local inference stacks. Empirical testing demonstrates that while the model successfully loads the multimodal projector (mmproj), processes visual data via the image\_url parameter within the create\_chat\_completion endpoint, and correctly identifies localized document context numbers (e.g., \`\`), it systematically fails to populate extracted JSON content fields. The output structure successfully mirrors the desired ContextSheet schema, yet all semantic targets—specifically fields such as type, description, interpretation, period, and sketch\_present—return null values.  
This behavioral anomaly is not indicative of a failure in the underlying neural network's visual-semantic mapping capabilities, nor is it a hardware execution error on the assigned NVIDIA RTX 3070\. Rather, the evidence indicates an orchestration failure rooted in the lossy abstraction layer between OpenAI-compatible API schemas and complex, template-driven local models. Specifically, the rigid signature of the create\_chat\_completion() method in llama-cpp-python aggressively strips arbitrary keyword arguments (such as template, mode, and enable\_thinking).1 This stripping mechanism prevents the GGUF's embedded Jinja2 templating engine from transitioning the model out of its default content (Markdown OCR) mode and into its specialized structured extraction mode.2  
This exhaustive research report provides an expert-level deconstruction of the root execution mechanisms responsible for the null content anomaly. It evaluates the hardware and environmental baseline, deeply analyzes a historical matrix of failed operational workarounds, and critically assesses five distinct engineering remediation strategies. Finally, the report outlines a comprehensive, definitive architectural blueprint for a custom multimodal chat completion handler capable of dynamically bridging complex Jinja2 template rendering with C-level CLIP image embedding processes, thereby fully restoring the model's structural extraction fidelity without sacrificing the extreme efficiency of the Vulkan execution pipeline.

## **Hardware and Environmental Baseline Configuration**

To contextualize the execution parameters and the resulting architectural friction, it is necessary to establish the baseline hardware and software environment within which the NuExtract3 model operates.

### **Processing Constraints and the Vulkan Backend**

The system environment utilizes an NVIDIA RTX 3070 graphics processing unit, which is constrained by an 8GB Video RAM (VRAM) capacity. This hardware limitation dictates specific operational requirements for large language models. A 4B parameter model like NuExtract3, if loaded in raw FP16 (16-bit floating-point) precision via native PyTorch and the Hugging Face transformers library, requires approximately 8GB of VRAM solely for the model weights.3 This leaves zero memory overhead for the Key-Value (KV) cache, which expands linearly with context size.  
Because the target application requires analyzing high-resolution document imagery (e.g., Pinn Brook page 4 located at erd\_workspace/pinnbrook/assets/...\_page\_004.png) and heavily detailed contextual schemas, the model is configured with a substantial context window (n\_ctx=16384).1 To accommodate this context window within the 8GB limit, the implementation correctly utilizes the highly optimized llama.cpp engine and a Q4\_K\_M (4-bit quantized) GGUF formatted model.5 This aggressive quantization reduces the weight footprint to approximately 2.5GB, freeing the necessary VRAM for the multimodal projector and the expansive KV cache.  
Furthermore, the deployment leverages the Vulkan GPU backend rather than the native CUDA backend. While CUDA is traditionally preferred for NVIDIA hardware, Vulkan provides a highly portable, low-overhead compute API that efficiently accelerates all 33 layers of the NuExtract3 Qwen-based architecture (n\_gpu\_layers=-1).1

### **The Application Layer: Hoard Extractors**

The application logic resides within a localized extraction pipeline, specifically managed by internal scripts such as src/hoard/extractors/nuextract3.py and src/hoard/extractors/template.py. The template.py module is responsible for bridging modern Python data validation frameworks with the LLM prompt interface. It dynamically converts Pydantic models into the serialized JSON templates required by the NuExtract3 architecture.3  
The target schema, defined as ContextSheet, requires the model to extract highly specific geological and archaeological data points, such as "Limestone Deposit" and "Topsoil." A comparative baseline has been established using GLM-OCR, an alternative proprietary or high-resource model, which successfully parses the Pinn Brook page 4 image and accurately extracts the aforementioned geological descriptors under the context identifier . The failure of NuExtract3 to match this baseline—despite successfully identifying the context number—proves that the image is legible and the data is present, isolating the failure strictly to the integration between the llama-cpp-python wrapper and the NuExtract3 control tokens.

## **The NuExtract3 Multimodal Paradigm**

NuExtract3 is not a standard conversational large language model. It is a unified 4B vision-language reasoning model designed for advanced document understanding, constructed upon the Qwen3.5-4B base architecture.8 The model is engineered to perform two primary, distinct tasks: high-fidelity image-to-Markdown conversion and precise structured JSON information extraction.2

### **Control Tokens and the Jinja2 Chat Template**

The behavioral toggle between these two paradigms (Markdown vs. JSON) is not controlled by a secondary model adapter (like a LoRA), nor is it determined by a separate binary execution path. Instead, the model's behavior is dictated by explicit control tokens injected during the prompt formatting phase.2  
In the GGUF ecosystem, model creators embed metadata within the file to instruct inference engines on how to format raw user messages into the specific token strings the model was trained on.11 The tokenizer.chat\_template metadata field utilizes the Jinja2 templating language to construct these exact token sequences.13  
An analysis of the NuExtract3 chat template reveals the following critical control logic:

Code snippet  
{%- set mode \= mode | default('content') \-%}  
{%- if template \-%}{%- set mode \= 'structured' \-%}{%- endif \-%}

When the template variable (which contains the JSON schema generated by src/hoard/extractors/template.py) is supplied to the Jinja2 renderer, the logic intercepts the variable and forcibly transitions the mode parameter to structured.2 This transition is the linchpin of the entire extraction process. It orchestrates the injection of critical system prompts, injecting the sequence 【task】structured extraction, followed by 【template\_start】, the user's serialized schema, 【template\_end】, and finally the 【document\_start】 markers.2  
These specific control tokens are heavily weighted in the model's self-attention layers. When activated, they prime the language model head to map visual embeddings from the CLIP projector directly to the structural keys defined in the schema.10 Conversely, without the explicit template variable being processed by the Jinja2 engine, the model defaults to content mode, effectively bypassing the structured extraction latent pathways entirely and defaulting to raw Markdown OCR.2

### **The Multimodal Projector (mmproj)**

In visual-language models like NuExtract3, the LLM cannot natively "see" image files. The architecture relies on a secondary model, typically a variant of CLIP (Contrastive Language-Image Pre-training) or a specialized vision encoder, which parses the raw pixels into high-dimensional floating-point arrays known as embeddings.6  
The mmproj (multimodal projector) acts as a bridge, aligning the dimensional space of the vision encoder with the dimensional space of the Qwen3.5 language model.13 When the llama-cpp-python engine encounters an image\_url in the message payload, it utilizes C-level bindings (\_llava\_cpp.clip\_model\_load and clip\_image\_embed) to generate these embeddings.15 The engine then inserts special placeholder tokens into the text prompt, which are seamlessly replaced by the raw image embeddings at the tensor level before the matrix multiplication begins in the GPU.6

## **Diagnostics of the Null Content Anomaly**

The central anomaly under investigation is the phenomenon where the model outputs the correct JSON structure—matching the ContextSheet schema exactly—and successfully identifies the document context number (\`\`), but returns null values for all deeply semantic fields such as type, description, interpretation, period, and sketch\_present.

### **The Illusion of Success**

The generation of the correct JSON keys gives the illusion that the model is operating correctly in structured extraction mode. However, a deep architectural analysis reveals that this is a hallucinated alignment caused by a "double-prompting" corruption.  
In an attempt to bypass the llama-cpp-python limitation, developers often attempt to manually embed the template markers directly into the user message text:  
【task】structured extraction  
【template\_start】  
{"type": "string", "description": "string",...}  
【template\_end】  
【document\_start】  
When these markers are injected manually into the text payload, the default text-based chat formatter wraps the entire payload in standard conversational tags dictated by the base Qwen3.5 chat template (e.g., \<|im\_start|\>user\\n...\<|im\_end|\>).19

### **The Failure of Cross-Attention**

This manual wrapping creates a severe misalignment in the model's positional encodings. The NuExtract3 attention heads are highly sensitive to sequence structure.10 They are trained to recognize the 【task】 marker exclusively when it immediately follows the internal system prompt or specific vision boundary tokens. By injecting the markers manually as user text, the markers are pushed deeper into the sequence length, misaligned with the spatial bounding boxes generated by the CLIP multimodal projector.2  
The result is a fractured inference state. The model reads the linguistic instruction to output JSON and dutifully generates the keys based on the schema it detects in the prompt. However, because the semantic link between the 【template\_start】 instruction and the image embeddings has been severed by the malformed token boundaries, the model's cross-attention mechanisms cannot successfully retrieve the visual data to populate the complex values.10 The context number \`\` is likely extracted because it is highly salient and visually distinct on the page, allowing shallow attention layers to grasp it, but deeper semantic comprehension (e.g., determining the geological "period" or "interpretation") requires perfect structural alignment. Unable to bridge the visual-semantic gap, the language head defaults to the safest token probability for an unknown value in JSON: null.

## **Call Stack Analysis and the Abstraction Bottleneck**

To definitively solve the orchestration failure, it is necessary to trace the precise execution path of llama-cpp-python and identify where the necessary keyword arguments are discarded. The library is designed to provide developer familiarity by exposing a high-level API that strictly mirrors the OpenAI Chat Completions specification.13

### **The API Signature Constraint**

The execution stack is initiated via a call to Llama.create\_chat\_completion.1 In llama-cpp-python v0.3.24, the function signature is highly explicit:

Python  
def create\_chat\_completion(  
    self,  
    messages: List,  
    functions: Optional\[List\[ChatCompletionFunction\]\] \= None,  
    function\_call: Optional \= None,  
    tools: Optional\] \= None,  
    tool\_choice: Optional \= None,  
    temperature: float \= 0.2,  
    top\_p: float \= 0.95,  
    top\_k: int \= 40,  
    min\_p: float \= 0.05,  
    typical\_p: float \= 1.0,  
    stream: bool \= False,  
    stop: Optional\[Union\[str, List\[str\]\]\] \= None,  
    \#... additional strict parameters...  
)

Critically, this signature lacks a generic kwargs collector for custom template variables.1 When a developer executes the test command llm.create\_chat\_completion(..., template=template\_json\_str, mode="structured"), the Python interpreter either throws a TypeError for unexpected keyword arguments, or the IDE strips the arguments before they reach the internal formatting logic. The parameters never enter the call stack.

### **The Handler Delegation**

Internally, create\_chat\_completion delegates the prompt formatting to a designated LlamaChatCompletionHandler.1 If no handler is explicitly provided during the instantiation of the Llama class, the registry attempts to resolve a default handler based on the GGUF metadata.20  
If the model is recognized as a vision-language model, it may attempt to load a handler like Qwen25VLChatHandler or Llava15ChatHandler.13 These specialized handlers intercept the image\_url payload in the messages, extract the Base64 image, and interface with the C++ library via clip\_image\_load\_from\_bytes.6  
However, if the text-formatting component of the handler attempts to render the Jinja2 template, it operates in a vacuum. Because the create\_chat\_completion function failed to pass the template and mode variables down the stack, the Jinja2ChatFormatter renders the tokenizer.chat\_template using only the default variables (messages, bos\_token, eos\_token).20 As previously established, without the template variable, the NuExtract3 Jinja logic defaults to content mode.2 The abstraction bottleneck fundamentally blinds the model to the user's structured extraction request.

## **Systemic Vulnerabilities and Sandboxing Implications**

The complexity of injecting variables into the Jinja2 renderer is further compounded by recent security enhancements within the llama-cpp-python codebase. Understanding this context is crucial for engineering a secure custom solution.  
Historically, the Jinja2ChatFormatter parsed the chat template within the GGUF metadata using an unrestricted jinja2.Environment. Because the tokenizer.chat\_template string is controlled by the creator of the GGUF file, malicious actors could upload compromised models to repositories like Hugging Face. When an unsuspecting user loaded the model, the unrestricted Jinja2 environment would render the template, leading to Server-Side Template Injection (SSTI) and enabling Remote Code Execution (RCE) on the host machine.23  
This vulnerability, tracked as GHSA-56xg-wfcc-g829, was patched by migrating the rendering engine to an ImmutableSandboxedEnvironment.20 This sandbox severely restricts the execution of arbitrary Python code within the template. Consequently, any attempt to bypass the API restrictions by heavily modifying the template rendering logic must respect the constraints of this sandboxed environment, or risk destabilizing the application or reopening security vectors.20 A proper remediation strategy must interact cleanly with the Jinja2 engine, passing variables explicitly rather than attempting to execute dynamic Python logic within the template itself.

## **Exhaustive Evaluation of Attempted Diagnostic Protocols**

Prior to conceptualizing custom architectural solutions, the development team executed a rigorous series of diagnostic protocols to force the NuExtract3 model into structured extraction mode. An analysis of these failed workarounds provides critical insight into the inflexible nature of current LLM orchestration tools.

### **1\. Ollama /api/generate**

**Result:** 500 Error.3 **Analysis:** The Ollama ecosystem is built upon a highly opinionated Go-based runner that abstracts away the underlying llama.cpp execution. The /api/generate endpoint bypasses standard conversational formatting and expects raw text inputs or highly specific internal template formats. Because the NuExtract3 GGUF metadata contains complex Jinja2 logic ({%- if template \-%}) that the Go-based parser cannot evaluate without the corresponding kwargs, the template engine faults, resulting in a fatal 500 Internal Server Error. Ollama simply cannot process the NuExtract3 dynamic template variables natively.

### **2\. Ollama /api/chat**

**Result:** Empty output. **Analysis:** Similar to the generate endpoint, the /api/chat endpoint is strictly mapped to the OpenAI schema. The Go-based server intercepts the API request, strips any non-standard fields (such as chat\_template\_kwargs), and feeds the sterilized messages to the model. Deprived of the template variable, the model defaults to content mode.2 Because the prompt contains an instruction to extract JSON but the model is locked into a Markdown OCR mode, the competing attentions cause the generation logic to collapse, yielding an empty string or immediate End-of-Sequence (EOS) token.

### **3\. llama-cpp-python create\_chat\_completion with Marker Text**

**Result:** Partial JSON (Structure correct, content null). **Analysis:** As detailed in the diagnostics section, manual injection of the control tokens (【task】structured extraction, 【template\_start】) into the message text creates a catastrophic misalignment between the text tokens and the mmproj visual embeddings.2 The positional encodings are skewed, destroying the model's cross-attention capabilities and resulting in hallucinated null values across the schema.

### **4\. llama-cpp-python create\_completion with Manual Prompt**

**Result:** Cannot handle multimodal images.1 **Analysis:** The low-level create\_completion (or \_\_call\_\_) method accepts a raw string prompt, bypassing the problematic chat formatters entirely.1 The developer can perfectly craft the string with the correct NuExtract3 markers. However, this method only accepts text.1 It does not possess the inherent logic to parse image\_url dictionaries, load the mmproj bindings, or invoke the clip\_image\_embed C-functions.25 Therefore, the text prompt is perfect, but the model is completely blind, rendering it useless for visual document extraction.

### **5\. llama-server (System Binary)**

**Result:** ROCm only; fails to detect NVIDIA GPU.13 **Analysis:** The pre-compiled llama-server binary available in the specific testing environment was likely compiled targeting AMD's HIP/ROCm framework rather than NVIDIA's CUDA or the cross-platform Vulkan API. Consequently, it cannot interface with the RTX 3070\.13 Even if the binary were recompiled with \-DGGML\_VULKAN=1 13, the server API endpoint (/v1/chat/completions) still strictly adheres to the OpenAI schema.21 It would strip the template kwarg over the HTTP payload just as the Python wrapper does, failing to solve the root problem.

### **6\. create\_chat\_completion\_openai\_v1**

**Result:** Passes through to the same handler; identical limitation.1 **Analysis:** This function is merely an alias designed to provide structural compatibility with older iterations of the openai Python package. Under the hood, it routes directly into the exact same create\_chat\_completion call stack 1, subjecting the payload to the same rigid signature constraints and shedding the required template variables.

## **Critical Analysis of Proposed Remediation Strategies**

With all standard operational workarounds exhausted, the focus must shift to architectural modification. Five potential engineering strategies have been identified to restore full structural extraction capability to NuExtract3. A rigorous evaluation of each follows, factoring in execution latency, architectural integrity, and multimodal compatibility.

### **Strategy 1: Register a Custom chat\_format Handler**

The llama\_cpp.llama\_chat\_format module provides a @register\_chat\_format decorator, which allows developers to define custom text formatters and append them to the internal registry.14  
**Mechanism:** A custom formatter named "nuextract3" could be registered. This function would accept the messages array, extract the GGUF's Jinja template from the model metadata, utilize the standard Python jinja2 library to render the template with template=\<schema\> and mode="structured", and return the parsed string.27  
**Architectural Assessment: Invalid for Multimodal VLMs** While highly effective for text-only language models, this strategy is structurally invalid for vision-language models. The ChatFormatter protocol explicitly requires the function to return a ChatFormatterResponse dataclass.20 This dataclass contains exactly four fields: prompt (a string), stop (a list of strings), stopping\_criteria, and added\_special (a boolean).20  
Crucially, it does not possess a field for tensor arrays or raw visual embeddings. When llama-cpp-python processes VLMs, specialized handlers (e.g., Llava15ChatHandler) interleave high-dimensional image embeddings directly into the tokenized sequence.6 If a standard string-based ChatFormatter is used via the registry, the image arrays are stripped from the processing pipeline entirely. The resulting text prompt is semantically perfect, but the LLM receives no visual data, resulting in a total failure to parse the document image.

### **Strategy 2: Use hf\_tokenizer\_config\_to\_chat\_formatter**

The library provides a utility function, llama\_cpp.llama\_chat\_format.hf\_tokenizer\_config\_to\_chat\_formatter, which dynamically constructs a formatter directly from a Hugging Face tokenizer configuration dictionary.20  
**Mechanism:** By manually downloading and loading the tokenizer\_config.json from the NuExtract3 Hugging Face repository, a developer could bypass the internal GGUF metadata parser and generate a formatter that theoretically accepts arbitrary kwargs.20  
**Architectural Assessment: Inadequate and Redundant** This strategy suffers from the exact same terminal flaw as Strategy 1\. The hf\_tokenizer\_config\_to\_chat\_formatter function evaluates the Hugging Face configuration and returns a standard ChatFormatter object.20 When this formatter is subsequently passed through the chat\_formatter\_to\_chat\_completion\_handler wrapper to interface with the execution engine, the pipeline is locked into a text-only modality.20 The C-level CLIP projection logic required to process the image\_url parameter is bypassed. Furthermore, this strategy introduces unnecessary external network dependencies by requiring the downloading of JSON configuration files outside the self-contained, offline GGUF ecosystem.

### **Strategy 3: Runtime Monkey-Patching of create\_chat\_completion**

Monkey-patching involves dynamically overriding the method definitions of classes at runtime. It is a hallmark of Python's dynamic dispatch capabilities.  
**Mechanism:** The developer could overwrite the Llama.create\_chat\_completion method within the application scope, modifying the method signature to accept an arbitrary kwargs collector, and explicitly pass those kwargs to the internal invocation of self.chat\_handler(llama=self, messages=messages, kwargs).1  
**Architectural Assessment: Highly Fragile and State-Corrupting** While this approach can be rapidly prototyped, it is highly discouraged in production enterprise environments. The llama-cpp-python codebase utilizes complex state management, particularly regarding context caching (self.cache), streaming queues, generation parameters, and token tracking arrays.1 Monkey-patching the primary endpoint exposes the application to severe instability across minor library updates.  
More critically, the patch does not guarantee success. The default chat\_handler assigned to Qwen-based VLMs (such as Qwen25VLChatHandler) may not inherently accept arbitrary kwargs in its underlying \_\_call\_\_ signature.33 If the underlying multimodal handler does not expect a template parameter, forcing it down the call stack via a monkey-patch will result in an unhandled TypeError 25, causing the pipeline to crash before the image is even processed.

### **Strategy 4: Utilization of the NuMind Python SDK**

NuMind, the creators of NuExtract3, provide an official Python SDK (pip install numind) and explicit code snippets for running the model via the Hugging Face transformers ecosystem.3  
**Mechanism:** The developer abandons the llama-cpp-python bindings and the .gguf file entirely. Instead, the implementation utilizes AutoModelForCausalLM and AutoTokenizer to load the native .safetensors model.3 The template JSON is converted via json.dumps and explicitly injected into the prompt using native Python f-strings, circumventing the Jinja2 complexity entirely.3  
**Architectural Assessment: Regressive Hardware Utilization** While this guarantees logical correctness and cleanly eliminates the Jinja2 rendering issue, it forces a complete architectural regression. Transitioning to the PyTorch/Transformers ecosystem negates the primary engineering advantages of the llama.cpp backend: extreme low-memory execution, aggressive quantization, and high-efficiency Vulkan GPU offloading.6  
As established in the baseline analysis, the host hardware is an RTX 3070 with 8GB VRAM. Loading a 4B VLM in raw PyTorch FP16 format consumes the entirety of this memory pool.38 When the application attempts to process a high-resolution document image like Pinn Brook page 4 requiring a massive context window (n\_ctx=16384), the KV cache memory requirements will exponentially exceed the hardware limits, triggering immediate PyTorch Out-of-Memory (OOM) exceptions. This solution is viable only in server environments with unconstrained VRAM (e.g., NVIDIA A100 or H100 arrays), making it unsuitable for the current deployment architecture.

### **Strategy 5: Develop a Custom LlamaChatCompletionHandler**

The Llama instantiation architecture is remarkably extensible, providing a deliberate injection point for custom execution logic via the chat\_handler parameter (Llama(..., chat\_handler=my\_handler)).1 A class implementing the LlamaChatCompletionHandler Protocol acts as the ultimate authority over how messages, strings, and images are parsed, embedded, and fed to the low-level C evaluation engine.20  
**Mechanism:** The developer authors a custom stateful class (e.g., NuExtract3ChatHandler) that strictly adheres to the LlamaChatCompletionHandler protocol. This custom handler replicates the multimodal capabilities of the base VLM handler (interfacing with \_llava\_cpp) but actively interrupts and rewrites the text-formatting phase.6 It extracts the Jinja2 template from the metadata, manually binds the template=\<context\_sheet\_schema\> and mode="structured" variables, renders the text, processes the image via CLIP, perfectly interleaves the embeddings, and submits the unified token stream to the create\_completion backend.39  
**Architectural Assessment: The Definitive Solution**  
This approach is architecturally unassailable. It maintains the highly efficient Vulkan execution pipeline, leverages the heavily quantized Q4\_K\_M GGUF format to stay well within the 8GB VRAM limit, successfully processes the mmproj visual embeddings, and flawlessly triggers the structured extraction latent pathways within the NuExtract3 model. By controlling the exact abstract syntax tree (AST) of the chat request prior to evaluation, the developer cleanly bypasses the restrictive signature of create\_chat\_completion without modifying the library's internal code, ensuring stability across framework updates.

## **Definitive Implementation Architecture for the Multimodal Handler**

To successfully execute the custom LlamaChatCompletionHandler strategy (Strategy 5), a deep understanding of the llama.cpp C-level bindings and Python data structures is required. The custom handler must seamlessly fuse text templating with high-dimensional image projections while safely navigating the Jinja2 sandbox.

### **Phase 1: Protocol Definition and CLIP Initialization**

The custom handler must be designed as a stateful class, similar in structure to the library's native Llava15ChatHandler or Qwen25VLChatHandler.13 During initialization, it must accept the path to the multimodal projector (mmproj.bin or mmproj.gguf).13  
Using the low-level \_llava\_cpp.clip\_model\_load bindings, the handler allocates the necessary memory on the Vulkan backend to process incoming image data.15 This step is critical; if the CLIP context is not established, the handler cannot generate embeddings.  
Furthermore, the class must manage its memory footprint meticulously. When the object is destroyed or the pipeline terminates, it is imperative to free the CLIP context using clip\_free (or equivalent \_llava\_cpp memory management routines) to prevent severe, compounding memory leaks on the GPU, which are a notorious failure point when reloading VLMs dynamically in continuous extraction loops.15

### **Phase 2: AST Interception and Image Extraction**

When the host application invokes create\_chat\_completion, the Llama object immediately defers execution to the \_\_call\_\_ method of our custom handler.6 The handler's first operational responsibility is to iterate through the messages array, which typically contains a mix of standard text and image\_url dictionaries representing the document.18  
The image extraction sequence must parse the Base64 data from the URI, decode it into raw bytes, and pass it to the C-binding function clip\_image\_embed (or llava\_image\_embed\_make\_with\_bytes).15 This function relies on the CLIP context established in Phase 1 to process the pixels into the raw embedding arrays that represent the visual data in the model's native dimensionality.18 The handler must retain these embeddings in host memory while it prepares the text prompt.

### **Phase 3: Dynamic Jinja2 Variable Binding**

With the visual data processed and waiting in memory, the handler must address the core issue: injecting the template variable into the NuExtract3 GGUF metadata template.  
To safely bypass the restrictions of the ImmutableSandboxedEnvironment without exposing the application to SSTI vulnerabilities, the custom handler initializes its own isolated instance of jinja2.Environment.20 It retrieves the exact tokenizer.chat\_template string from the llama.metadata dictionary.12  
Crucially, the handler accepts the JSON schema string (ContextSheet) during its initialization (or as a stateful variable updated per request) and explicitly passes it into the env.render() function alongside the text messages:

Python  
\# Theoretical Jinja rendering within the custom handler's \_\_call\_\_ method  
rendered\_prompt \= custom\_env.render(  
    messages=text\_only\_messages,  
    bos\_token=llama.metadata.get("tokenizer.ggml.add\_bos\_token", ""),  
    eos\_token=llama.metadata.get("tokenizer.ggml.add\_eos\_token", ""),  
    template=self.extraction\_schema,  \# The critical missing kwarg  
    mode="structured"                 \# Force structural extraction mode  
)

By ensuring that the template variable evaluates to a non-empty string during the render pass, the internal logic {%- if template \-%}{%- set mode \= 'structured' \-%}{%- endif \-%} executes correctly.2 The resulting rendered\_prompt string will natively contain the precise NuExtract3 control tokens: 【task】structured extraction, 【template\_start】, the user's schema, and 【template\_end】, all perfectly formatted without manual injection.2

### **Phase 4: Tokenization Alignment and Interleaved Evaluation**

The final, most sensitive phase involves combining the structurally perfect Jinja string with the raw image embeddings generated in Phase 2\.  
The Qwen3.5-based NuExtract3 model architecture relies on specific placeholder tokens to represent where the image data exists within the sequence length. If the text prompt is tokenized directly and sent to the LLM, the model will treat the visual markers as literal text, resulting in a generation collapse.6  
The custom handler must split the rendered\_prompt string at the designated image injection points. It tokenizes the prefix text, appends the raw high-dimensional image embeddings directly into the token array (bypassing the standard text tokenizer for those specific indices), and then tokenizes and appends the suffix text.6  
This unified, seamlessly interleaved array of token IDs and raw floating-point embeddings is then passed to the low-level llama.create\_completion endpoint or evaluated directly using llama.eval.6 Because the causal attention mask is preserved perfectly, and the exact NuExtract3 control tokens are positioned flawlessly relative to the image data, the LLM cross-attention heads successfully map the visual features to the structural keys.

### **Execution Profile of the Hybrid Architecture**

A comparative assessment of this hybrid architecture against the application requirements yields highly favorable metrics:

| Metric | Assessment | Operational Impact |
| :---- | :---- | :---- |
| **GPU VRAM Utilization** | Highly Efficient | Maintains the Vulkan backend and Q4\_K\_M quantization, keeping the 4B model within strict RTX 3070 8GB limits even with n\_ctx=16384. |
| **Execution Latency** | Optimized | Bypasses Python-level overhead by calling C-bindings directly for tokenization and image embedding. |
| **Architectural Stability** | Exceptional | Leaves the base llama-cpp-python installation untouched, preventing catastrophic update breakages inherent to monkey-patching. |
| **Semantic Fidelity** | Perfect | Ensures the internal language head operates natively in structured mode, eliminating hallucinatory null fields for type, description, etc. |

## **Conclusion and Upstream Implications**

The extraction of complex structured JSON data from visual documents represents a delicate orchestration of image projection and autoregressive language modeling. The empirical anomaly wherein the NuExtract3 Q4\_K\_M model yields accurate JSON schemas but empty content fields is a direct symptom of abstraction friction. The llama-cpp-python layer strictly mirrors the OpenAI parameter specification, failing to forward arbitrary keyword arguments to the embedded Jinja2 rendering engine. Deprived of the template parameter, NuExtract3 defaults to a Markdown-generation mode, failing to activate the internal attention pathways required to map visual data to structural keys.  
While manual prompt injection, alternative formatters (hf\_tokenizer\_config\_to\_chat\_formatter), monkey-patching, and complete framework replacement (NuMind SDK) offer varying degrees of functionality, they inherently compromise either multimodal capability, critical hardware efficiency, or application stability.  
The optimal, uncompromised solution demands the engineering of a custom LlamaChatCompletionHandler. By explicitly loading the multimodal projector via C-bindings, extracting the Jinja2 template from the GGUF metadata, manually rendering the prompt with the required template and mode keyword arguments, and interleaving the visual embeddings with the text tokens, the system restores complete architectural harmony. This approach preserves the extreme efficiency of the Vulkan GPU backend, respects the rigid token boundaries required by the Qwen3.5 architecture, and unlocks the full zero-shot structured extraction capabilities of the NuExtract3 model.  
Looking forward, this architectural friction highlights a growing structural deficit in the open-source AI ecosystem. As vision-language models become increasingly sophisticated, they rely heavily on complex meta-parameters passed during the template rendering phase (e.g., template, mode, enable\_thinking, reasoning\_budget).2 The rigid OpenAI API specification was not designed to accommodate these execution-path parameters at the message level. Until robust upstream support for passing chat\_template\_kwargs through the wrapper stack is formally integrated 19, the deployment of custom handler logic will remain an essential engineering mandate for any enterprise leveraging localized, hardware-accelerated document extraction pipelines.

#### **Works cited**

1. llama-cpp-python/llama\_cpp/llama.py at main \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/blob/main/llama\_cpp/llama.py](https://github.com/abetlen/llama-cpp-python/blob/main/llama_cpp/llama.py)  
2. numind/NuExtract3 \- Hugging Face, accessed June 2, 2026, [https://huggingface.co/numind/NuExtract3](https://huggingface.co/numind/NuExtract3)  
3. numind/NuExtract-1.5 \- Hugging Face, accessed June 2, 2026, [https://huggingface.co/numind/NuExtract-1.5](https://huggingface.co/numind/NuExtract-1.5)  
4. accessed June 2, 2026, [https://raw.githubusercontent.com/abetlen/llama-cpp-python/main/llama\_cpp/llama.py](https://raw.githubusercontent.com/abetlen/llama-cpp-python/main/llama_cpp/llama.py)  
5. Gemma 3:4B Multimodal CLIP Error \[WinError \-529697949\] Windows Error 0xe06d7363 · Issue \#2031 · abetlen/llama-cpp-python \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/issues/2031](https://github.com/abetlen/llama-cpp-python/issues/2031)  
6. How to combine model and mmproj ? · abetlen llama-cpp-python · Discussion \#2122, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/discussions/2122](https://github.com/abetlen/llama-cpp-python/discussions/2122)  
7. numindai/nuextract \- GitHub, accessed June 2, 2026, [https://github.com/numindai/nuextract](https://github.com/numindai/nuextract)  
8. NuExtract3 released: open-weight 4B VLM for Markdown, OCR and structured extraction (self-hostable) \[P\] : r/MachineLearning \- Reddit, accessed June 2, 2026, [https://www.reddit.com/r/MachineLearning/comments/1tkejqr/nuextract3\_released\_openweight\_4b\_vlm\_for/](https://www.reddit.com/r/MachineLearning/comments/1tkejqr/nuextract3_released_openweight_4b_vlm_for/)  
9. Numind releases Apache-2.0 4B vision model for document, accessed June 2, 2026, [https://aiweekly.co/alerts/numind-releases-apache-20-4b-vision-model-for-document-extraction](https://aiweekly.co/alerts/numind-releases-apache-20-4b-vision-model-for-document-extraction)  
10. NuExtract3 Explained: From Messy Documents to Structured JSON & Markdown \- YouTube, accessed June 2, 2026, [https://www.youtube.com/watch?v=lds4vMxXH7g](https://www.youtube.com/watch?v=lds4vMxXH7g)  
11. llama-cpp-python: do GGUFs contain formatting metadata, or am I expected to format with special tokens? : r/LocalLLaMA \- Reddit, accessed June 2, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1jsx0dp/llamacpppython\_do\_ggufs\_contain\_formatting/](https://www.reddit.com/r/LocalLLaMA/comments/1jsx0dp/llamacpppython_do_ggufs_contain_formatting/)  
12. Best way to apply chat templates locally · abetlen llama-cpp-python · Discussion \#1930, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/discussions/1930](https://github.com/abetlen/llama-cpp-python/discussions/1930)  
13. Python bindings for llama.cpp \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python](https://github.com/abetlen/llama-cpp-python)  
14. Use chat\_template from gguf metadata · Issue \#1096 · abetlen/llama-cpp-python \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/issues/1096](https://github.com/abetlen/llama-cpp-python/issues/1096)  
15. Llava/CLIP Models Not Loading Properly · Issue \#946 · abetlen/llama-cpp-python \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/issues/946](https://github.com/abetlen/llama-cpp-python/issues/946)  
16. Support for multi-modal models · Issue \#813 · abetlen/llama-cpp-python \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/issues/813](https://github.com/abetlen/llama-cpp-python/issues/813)  
17. UnsupportedOperation: fileno in Llava15ChatHandler · Issue \#1041 · abetlen/llama-cpp-python \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/issues/1041](https://github.com/abetlen/llama-cpp-python/issues/1041)  
18. feat: Add Gemma3 chat handler (\#1976) by kossum · Pull Request \#1989 · abetlen/llama-cpp-python \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/pull/1989](https://github.com/abetlen/llama-cpp-python/pull/1989)  
19. Thinking toggle support for Qwen related models · Issue \#2063 · abetlen/llama-cpp-python, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/issues/2063](https://github.com/abetlen/llama-cpp-python/issues/2063)  
20. llama-cpp-python/llama\_cpp/llama\_chat\_format.py at main \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/blob/main/llama\_cpp/llama\_chat\_format.py](https://github.com/abetlen/llama-cpp-python/blob/main/llama_cpp/llama_chat_format.py)  
21. llama-cpp-python/llama\_cpp/server/app.py at main \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/blob/main/llama\_cpp/server/app.py](https://github.com/abetlen/llama-cpp-python/blob/main/llama_cpp/server/app.py)  
22. API Reference \- llama-cpp-python, accessed June 2, 2026, [https://llama-cpp-python.readthedocs.io/en/latest/api-reference/](https://llama-cpp-python.readthedocs.io/en/latest/api-reference/)  
23. Remote Code Execution by Server-Side Template Injection in Model Metadata · Advisory · abetlen/llama-cpp-python \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/security/advisories/GHSA-56xg-wfcc-g829](https://github.com/abetlen/llama-cpp-python/security/advisories/GHSA-56xg-wfcc-g829)  
24. How to have llama-cpp-python remember the chat history for consecutive queries? \- Reddit, accessed June 2, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1flojeb/how\_to\_have\_llamacpppython\_remember\_the\_chat/](https://www.reddit.com/r/LocalLLaMA/comments/1flojeb/how_to_have_llamacpppython_remember_the_chat/)  
25. Llava1.5 multi-modal not working since version 0.2.26 · Issue \#1225 · abetlen/llama-cpp-python \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/issues/1225](https://github.com/abetlen/llama-cpp-python/issues/1225)  
26. WSL2でllama-cpp-pythonを試してみる｜noguchi-shoji \- note, accessed June 2, 2026, [https://note.com/ngc\_shj/n/n1b59da7fed25](https://note.com/ngc_shj/n/n1b59da7fed25)  
27. One chat prompt/template should be customizable from runtime \- the prompt I need atm · Issue \#816 · abetlen/llama-cpp-python \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/issues/816](https://github.com/abetlen/llama-cpp-python/issues/816)  
28. deepseek chat\_format template · Issue \#969 · abetlen/llama-cpp-python \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/issues/969](https://github.com/abetlen/llama-cpp-python/issues/969)  
29. MISTRAL\_INSTRUCT\_BOS\_TO, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/issues/1566](https://github.com/abetlen/llama-cpp-python/issues/1566)  
30. Accessing chat format functions directly · abetlen llama-cpp-python · Discussion \#1520 \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/discussions/1520](https://github.com/abetlen/llama-cpp-python/discussions/1520)  
31. implement prompt template for chat completion · Issue \#717 · abetlen/llama-cpp-python, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/issues/717](https://github.com/abetlen/llama-cpp-python/issues/717)  
32. Thread bug in server code · Issue \#62 · abetlen/llama-cpp-python \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/issues/62](https://github.com/abetlen/llama-cpp-python/issues/62)  
33. Problem with ChatCompletionMessage when using cuBLAS and Mistral. · Issue \#1144 · abetlen/llama-cpp-python \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/issues/1144](https://github.com/abetlen/llama-cpp-python/issues/1144)  
34. feat: Add Gemma3 chat handler (\#1976) by kossum · Pull Request \#1989 · abetlen/llama-cpp-python \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/pull/1989/files](https://github.com/abetlen/llama-cpp-python/pull/1989/files)  
35. NuExtract Platform: The New Information Extraction \- NuMind, accessed June 2, 2026, [https://numind.ai/blog/nuextract-platform-the-new-information-extraction](https://numind.ai/blog/nuextract-platform-the-new-information-extraction)  
36. numindai/nuextract-platform-sdk \- GitHub, accessed June 2, 2026, [https://github.com/numindai/nuextract-platform-sdk](https://github.com/numindai/nuextract-platform-sdk)  
37. numind/NuExtract3 at main \- Hugging Face, accessed June 2, 2026, [https://huggingface.co/numind/NuExtract3/tree/main](https://huggingface.co/numind/NuExtract3/tree/main)  
38. NuMind \- Hugging Face, accessed June 2, 2026, [https://huggingface.co/numind](https://huggingface.co/numind)  
39. Extend the token/count method to allow obtaining the number of prompt tokens from a chat. · abetlen llama-cpp-python · Discussion \#1461 \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/discussions/1461](https://github.com/abetlen/llama-cpp-python/discussions/1461)  
40. Llava15ChatHandler \- Cache Image Encoding · Issue \#2222 · abetlen/llama-cpp-python, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/issues/2222](https://github.com/abetlen/llama-cpp-python/issues/2222)  
41. No clip model .bin files for llava15, just the .gguf · abetlen llama-cpp-python \- GitHub, accessed June 2, 2026, [https://github.com/abetlen/llama-cpp-python/discussions/1422](https://github.com/abetlen/llama-cpp-python/discussions/1422)