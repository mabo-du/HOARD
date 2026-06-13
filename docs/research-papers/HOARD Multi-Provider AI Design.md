# **HOARD Architectural Blueprint: Multi-Provider AI Abstraction Layer and Hybrid Inference Scaling**

The Heritage Observation And Report Drafter (HOARD) platform represents a critical advancement in computational archaeology, accelerating the conversion of raw field data into comprehensive grey literature reports. These archaeological reports typically range between ten and sixty pages in length, forming the foundational documentary evidence of developer-led and academic excavations.1 Historically, the creation of this ubiquitous typescript grey literature has been a manual, time-intensive process involving the synthesis of hundreds of context sheets, finds catalogues, and site matrices.2 HOARD automates this pipeline using a four-phase inference architecture: document digitization, photo captioning, synthesis and drafting, and compliance refinement.  
However, the current architectural reliance on a monolithic local inference backend anchored exclusively to Ollama imposes severe operational constraints. Archaeologists operate in highly variable environments, frequently drafting reports on underpowered laptops in remote field houses, cafes, or museum archives lacking dedicated graphical processing units (GPUs). Furthermore, while localized inference guarantees data privacy, preliminary economic and qualitative analyses reveal a substantial cloud quality gap. Modern cloud-hosted large language models produce superior narrative prose compared to heavily quantized 4-billion-parameter local models, and they do so at a fraction of the cost when accounting for the rapid depreciation of high-end consumer hardware.  
To resolve these constraints, this engineering specification details the implementation of a comprehensive multi-provider AI abstraction layer. This layer dynamically routes inference requests across local consumer-grade hardware and enterprise cloud endpoints, utilizing advanced provider selection heuristics, rigorous cryptographic credential management, and privacy-first data sanitization protocols.

## **Provider Abstraction Interface Design**

The transition from a hardcoded Ollama dependency to a multi-provider ecosystem necessitates a highly robust abstraction layer. The fundamental design question involves choosing between a "thin wrapper"—where the application formats requests uniquely for each provider—and a "thick abstraction"—where a universal internal representation is dynamically translated into provider-specific schemas. A full abstraction layer with intelligent normalization is strictly required for HOARD. Relying on generalized third-party libraries like LiteLLM 4 introduces unnecessary dependency bloat and relinquishes fine-grained control over payload sanitization, which is unacceptable given the sensitive nature of archaeological data.

### **Concrete Type Signatures and Interface Contracts**

The abstraction framework is built upon strict Pydantic data validation and Python interface protocols. This ensures deterministic execution across HOARD's specific four-phase pipeline regardless of the underlying backend.

Python  
from typing import Protocol, List, Dict, Any, Optional, Literal, Union  
from pydantic import BaseModel, Field, SecretStr  
from enum import Enum

class Modality(str, Enum):  
    TEXT \= "text"  
    VISION \= "vision"  
    STRUCTURED \= "structured"

class Message(BaseModel):  
    role: Literal\["system", "user", "assistant"\]  
    content: str  
    images: Optional\[List\[str\]\] \= Field(default=None, description="Base64 encoded images")

class ProviderConfig(BaseModel):  
    provider\_name: str  
    model\_name: str  
    api\_key: Optional \= None  
    base\_url: Optional\[str\] \= None  
    max\_retries: int \= 3  
    timeout\_seconds: int \= 60

class InferenceRequest(BaseModel):  
    messages: List\[Message\]  
    model\_name: str  
    temperature: float \= 0.0  
    max\_tokens: Optional\[int\] \= None  
    response\_schema: Optional\] \= Field(default=None, description="Standard JSON Schema for structured output")  
    template\_format: Optional\[str\] \= Field(default=None, description="NuExtract proprietary empty JSON template")  
    provider\_kwargs: Dict\[str, Any\] \= Field(default\_factory=dict)

class TokenUsage(BaseModel):  
    prompt\_tokens: int  
    completion\_tokens: int  
    total\_tokens: int  
    estimated\_cost\_usd: float \= 0.0

class InferenceResponse(BaseModel):  
    content: str  
    raw\_response: Any  
    usage: TokenUsage  
    provider\_name: str

class ModelProvider(Protocol):  
    config: ProviderConfig  
      
    async def generate(self, request: InferenceRequest) \-\> InferenceResponse:  
        """Executes the normalized inference request against the designated provider."""  
       ...  
          
    async def is\_available(self) \-\> bool:  
        """Executes a lightweight health check to verify endpoint availability."""  
       ...

class CredentialStore(Protocol):  
    def get\_key(self, provider: str, profile: str \= "default") \-\> str:  
       ...  
    def set\_key(self, provider: str, key: str, profile: str \= "default") \-\> None:  
       ...

### **Context Window and Modality Normalization**

Context window management represents a critical divergence point between local and cloud inference. Local instances of models like Qwen3.5-4B typically operate efficiently within a 32,000 to 64,000 token context window, necessitating complex chunk-and-merge map-reduce logic during Phase 3 synthesis to process extensive site data. In contrast, modern cloud models possess vastly superior context capacities. Google Gemini 2.5 Flash and Gemini 2.0 natively support up to a 1,000,000 token context window 6, while Anthropic's Claude 3.5 Sonnet and Haiku operate seamlessly with 200,000 token limits.7  
The abstraction layer introduces a dynamic context awareness protocol. Before executing a Phase 3 request, the InferenceRequest evaluates the target model's maximum context length against an approximate tokenized count of the input context sheets. If the count falls within the model's native capacity, the abstraction layer entirely bypasses the chunk-and-merge algorithm. Transmitting the archaeological data as a continuous stream significantly decreases latency by eliminating iterative API calls and vastly enhances synthesis quality, as the model retains simultaneous global attention across the entire site dataset.  
Vision input normalization requires a specialized data transformation pipeline centralized within the provider implementation classes. Phase 2 utilizes models like Qwen3-VL-8B for photo captioning, where spatial understanding of excavation trenches is critical. The core InferenceRequest standardizes all vision inputs as Base64 encoded PNG strings. The abstraction layer delegates the serialization to the specific provider class, ensuring the application logic remains entirely agnostic to the routing destination.

### **Structured Output Architecture**

Structured data extraction, which forms the backbone of Phase 1 (digitization) and Phase 4 (compliance refinement), presents the highest implementation variance across the language model ecosystem. Providers enforce strictly divergent methodologies for guaranteeing JSON outputs.  
The ModelProvider must ingest the standardized JSON Schema defined in the InferenceRequest.response\_schema and seamlessly translate it into the target provider's native format. For Ollama, the interface injects the schema directly into the format parameter. For OpenAI compatible endpoints, the provider maps the schema into the response\_format object utilizing the strict json\_schema configuration.8 Anthropic implementations require the system to disguise the JSON schema as a function signature within a tool\_use array.9 Google Gemini configurations convert the schema into a response\_schema object while setting the response\_mime\_type to application/json.  
The integration of highly specialized extraction models like NuExtract3 requires an entirely distinct architectural pathway. NuExtract3 demonstrates exceptional capability in unifying document extraction and Optical Character Recognition through targeted reasoning reinforcement.10 However, NuExtract3 discards standard JSON Schema in favor of a proprietary empty JSON template structure (e.g., {"reactants": \[{"name": "", "quantity": ""}\]}).12 When the template\_format parameter is detected within an InferenceRequest, the abstraction layer must route the execution through custom chat format handlers, bypassing standard schema enforcement entirely.

### **Provider Implementation Outlines**

The concrete implementations of the ModelProvider protocol encapsulate the specific HTTP client logic and payload transformation required for each ecosystem.

#### **Ollama Provider Implementation**

The Ollama provider acts as the primary local workhorse. It receives the normalized InferenceRequest and constructs a payload compatible with the local daemon. It specifically maps Base64 strings into the images array of the message object.14 For Phase 1 and Phase 4, it leverages the format parameter for structured extraction. VRAM eviction is managed by injecting keep\_alive=0 into the provider\_kwargs when transitioning between phases, ensuring the GPU is flushed before loading the subsequent model.

#### **OpenAI and OpenRouter Provider Implementations**

The OpenAI provider translates the InferenceRequest into the standard Chat Completions API format. Vision inputs are transformed into content arrays featuring type: "image\_url" dictionaries. OpenRouter utilizes an identical implementation, achieved through classical inheritance, with the singular addition of injecting specific routing headers (e.g., HTTP-Referer and X-Title) into the HTTP client session to identify the HOARD application.15 Both providers utilize the response\_format parameter configured for strict JSON schema compliance when structured output is requested.8

#### **Anthropic Provider Implementation**

The Anthropic API mandates distinct structural deviations. The provider implementation must separate the system prompt from the messages array, passing it as a top-level parameter. Vision inputs require transformation into a source block specifying the exact media type and encoding. Structured data generation relies on the Anthropic tool-use paradigm, where the response\_schema is mapped to a mock function definition that the model is strictly compelled to invoke.9

#### **Google Gemini Provider Implementation**

The Google Gemini REST implementation requires mapping standard message roles to user and model. System instructions are nested within a dedicated system\_instruction object. Vision inputs are encoded into inline\_data parts. For structured outputs, the provider assigns application/json to the response\_mime\_type and attaches the schema directly to the generation configuration. This integration seamlessly supports lightweight, high-speed models like Gemini 2.5 Flash-Lite, which offers highly economical token processing.16

### **Telemetry and Cost Tracking**

A unified telemetry module is integrated directly into the InferenceResponse generation pipeline. The abstraction layer incorporates a dynamically updated pricing manifest tracking the input and output token costs per million tokens across supported cloud providers.6 As the HTTP response is parsed, the provider implementation extracts the usage statistics. The cost tracker intercepts the TokenUsage object, multiplies the input and output token counts by their respective real-time rates, and attaches the calculated estimated\_cost\_usd to the final response. This critical telemetry is automatically serialized into the project's audit trail, providing organizations with granular, per-phase visibility into the financial overhead of producing individual grey literature reports.

## **Dynamic Provider Selection Heuristics**

The previous architecture mapped fixed models to specific phases, creating brittle failure points when operating in environments with fluctuating internet connectivity or shared, heavily utilized GPU resources. The multi-provider layer introduces a sophisticated routing framework governed by a local YAML configuration file \~/.config/hoard/config.yaml. This heuristic engine dynamically orchestrates inference based on endpoint availability, privacy constraints, and required output quality.

### **Routing Modes**

The system operates under three distinct routing paradigms, configurable globally or per-project.  
**Manual Mode** executes a strict compliance pathway. The system attempts inference exclusively against the explicitly configured provider and model designated for each phase. If the specific endpoint is unavailable, the application gracefully halts and alerts the user. This mode is paramount for rigid institutional environments where data compliance and funding mandates dictate exact routing trajectories without autonomous deviation.  
**Auto Mode** implements a robust, cascading availability protocol. Upon the initialization of a pipeline phase, the engine proactively probes the primary provider's health endpoint. If the local Ollama daemon is targeted, the system dispatches a lightweight HTTP GET request to http://localhost:11434/api/tags. If the connection times out—indicating the daemon is offline or currently deadlocked by an external workload—the system automatically transitions to the secondary provider in the configuration hierarchy. Furthermore, the engine conducts a preliminary environment assessment. If the host machine lacks a dedicated GPU and the configuration permits cloud access, the engine preemptively strips all local providers from the routing queue, neutralizing inevitable out-of-memory errors before execution begins. Conversely, if a network ping to a reliable external DNS resolver fails, all cloud providers are pruned, enforcing local-only execution.  
**Quality Mode** represents an advanced orchestration strategy designed to balance narrative prose quality against financial expenditure and hardware limitations. Extensive pre-deployment analyses demonstrate that cloud models consistently produce vastly superior archaeological narrative synthesis compared to consumer-grade local models, whereas structured data extraction tasks can be handled reliably by localized instances. Under Quality Mode, the pipeline defaults to a hybridized approach. Phase 1 (Document Digitization) targets localized GLM-OCR, prioritizing deterministic data extraction over prose fluidity, falling back to Gemini 2.5 Flash-Lite only if local hardware is insufficient. Phase 2 (Photo Captioning) defaults to a localized Qwen3-VL instance, purposefully retaining sensitive, unredacted trench images on-device, utilizing Gemini 2.5 Flash solely as a secondary fallback. Conversely, Phase 3 (Synthesis) and Phase 4 (Compliance Refinement) automatically target advanced cloud instances like Claude 3.5 Sonnet 19 or GPT-4o-mini 18 to guarantee publication-grade syntactic structures, reverting to local Qwen variants only during severe network degradation.

### **Latency Budgets and Per-Section Routing**

Archaeological fieldwork dictates intermittent connectivity. The routing engine introduces a strict latency budget protocol to prevent pipeline stagnation. Each provider request is wrapped in an asynchronous timeout mechanism defined in the configuration schema (e.g., latency\_budget\_seconds: 45). If a cloud provider stalls due to severe rate limiting, or a local model throttles excessively due to thermal constraints on a laptop, the abstraction layer intercepts the resulting timeout exception. The degradation event is logged to the system core, and the remaining unfulfilled payload is immediately redirected to the configured fallback provider.  
In Phase 4, compliance refinement is executed iteratively across individual document sections rather than as a monolithic payload. For this phase, the provider selection and health monitoring are evaluated on a per-request basis rather than a per-phase basis. This architectural decision prevents an entire document phase from catastrophic failure due to a momentary network disruption or API gateway error. If a cloud provider fails mid-phase, the system securely caches the successfully processed JSON sections locally, switches the active provider based on the heuristic queue, and resumes processing the remaining sections without data loss or duplicate token expenditure.

## **Error Handling and Resilience Patterns**

Robust error handling is fundamental to the stability of the multi-provider layer. The interface implements a comprehensive middleware interceptor that categorizes upstream provider errors and triggers specific resilience patterns.  
**Retry Logic and Rate Limiting:** Cloud providers enforce strict rate limits, typically resulting in HTTP 429 Too Many Requests errors. The abstraction layer parses the response headers (such as x-ratelimit-reset) to determine the exact backoff duration. If no header is present, the system implements an exponential backoff algorithm with jitter, retrying up to the configured max\_retries limit. If the threshold is exceeded, the request is routed to the fallback provider.  
**Context Window Exceeded:** Submitting a payload that exceeds the maximum token limit generates an HTTP 400 or 413 error. When this specific error signature is detected from a cloud provider, the abstraction layer automatically intercepts the failure, engages the localized text-splitting utility, and forces the application into the chunk-and-merge map-reduce algorithm normally reserved for local models, ensuring the payload is processed regardless of the provider's native constraints.  
**Authentication and Network Failures:** HTTP 401 Unauthorized or 403 Forbidden errors indicate invalid API keys or expired enterprise tokens. These errors immediately halt the retry loop, as subsequent requests will inevitably fail. The system logs a sanitized warning, prunes the offending provider from the queue, and routes to the fallback. General network timeouts trigger standard retry logic but rapidly transition to local fallbacks if the host machine's internet connection is determined to be fundamentally unstable.

## **Cryptographic Credential Management**

Integrating third-party cloud APIs into the HOARD ecosystem necessitates rigorous, institutional-grade credential management. Exposing highly privileged API keys in plaintext YAML configuration files or environmental variables introduces severe security vulnerabilities, particularly when archaeological projects are frequently shared among academic teams via version control systems. The credential system aligns with the security posture of the existing Kryptis vault ecosystem, ensuring AES-256-GCM encryption is utilized for localized secret storage, functioning entirely independently of desktop environments, cloud-based Key Management Systems, or platform-specific keychains.22

### **AES-256-GCM Encryption Architecture**

The credential store relies on an isolated SQLite database acting as an encrypted vault. The Advanced Encryption Standard operating in Galois/Counter Mode (AES-256-GCM) provides authenticated encryption. This stream cipher approach guarantees both data confidentiality and authenticity; alterations to the encrypted ciphertext are immediately detected via the authentication tag, neutralizing tampering attempts.22  
Key derivation is executed via the Password-Based Key Derivation Function 2 (PBKDF2) utilizing a SHA-256 HMAC.23 The user's master passphrase generates a 256-bit encryption key combined with a cryptographically secure, randomly generated 128-bit salt.  
The encryption payload encapsulates the initialization vector (IV), the salt, and the encrypted ciphertext. During initialization, the application requests the master passphrase. This can be supplied via an interactive secure terminal prompt or explicitly defined via an environmental variable (HOARD\_VAULT\_KEY) for headless server operations. The derived cryptographic key is held securely in memory for the duration of the execution process and explicitly wiped upon application termination.

### **Global Configuration and CLI Interactions**

Credentials are fundamentally tied to the user's local operating environment, not the individual archaeological site repository. Consequently, the SQLite vault resides in the global application directory at \~/.config/hoard/credentials.db. This rigid separation guarantees that committing an archaeological project directory to version control cannot inadvertently leak a .env file containing valid API tokens.  
The system features a dedicated Command Line Interface module for secret lifecycle management. Users execute commands such as hoard keys set anthropic which securely prompts for the API key, encrypts the string in memory, and commits it to the global SQLite table. The CLI also facilitates key rotation, list operations, and vault initialization. To accommodate diverse institutional environments, the schema supports multiple keys per provider, delineated by profile tags. A user might configure separate accounts via hoard keys set openai \--profile university-lab and hoard keys set openai \--profile personal, passing the desired profile string in the YAML configuration.

### **Prompt Sanitization and In-Memory Handling**

A fundamental architectural stricture requires that API keys are injected exclusively at the deepest transport layer of the HTTP client implementation. Application state objects, context dictionaries, and error exception payloads never contain plaintext credentials. Furthermore, application telemetry and terminal logs are subjected to an automated sanitization middleware. A regex-based interception pass monitors all outgoing terminal logs and file writes, ensuring that any string resembling a high-entropy bearer token is actively redacted and replaced with \`\`, effectively nullifying accidental key leakage in diagnostic outputs or stack traces.

## **Local-First Architecture and Privacy Safeguards**

The foundational value proposition of the HOARD platform is absolute data sovereignty. Transitioning to a hybrid inference model must not compromise this tenet under any circumstances. Archaeological data inherently possesses extreme geographic and cultural sensitivity. The dissemination of precise coordinate data, unredacted trench photography, and localized artifact distributions dramatically escalates the risk of terrestrial looting.25 Grey literature reports often contain comprehensive site methodologies, structural evaluations, and heritage assessments that must remain strictly embargoed prior to formal publication and review by local Historic Environment Records (HER).2

### **Privacy Tiers and Data Sanitization**

To mitigate the exposure of sensitive heritage data to third-party language models, the hybrid architecture enforces a strict Privacy Tiering system. These configuration tiers dictate the classification of data permitted to traverse external network boundaries, operating independently of the provider routing heuristics.  
**Strict Local Tier:** This tier acts as the ultimate safeguard, essentially air-gapping the inference application. When invoked via the \--offline CLI flag or enforced through the YAML configuration, the routing engine terminates all network requests directed at external IP addresses. In this mode, the application defaults entirely to the Ollama backend or the llama-cpp-python fallback. If the local hardware cannot support the memory requirements of the active phase, the system gracefully aborts and saves state, rather than silently compromising the air-gap to complete the task.  
**Sanitized Cloud Tier:** This intermediate tier permits the transmission of textual context sheets to cloud APIs but actively intercepts high-risk spatial identifiers and visual assets. Prior to serialization, textual inputs are passed through a rapid local Named Entity Recognition (NER) pipeline and regex heuristic. This localized processor masks specific coordinate systems (e.g., OSGB36 grid references, precise latitude/longitude pairs) and explicitly named geographical landmarks. Crucially, Phase 2 photo captioning is strictly prohibited from utilizing cloud vision endpoints in this tier; all field images remain entirely on-device to eliminate the risk of visual site identification via satellite comparison.25  
**Full Hybrid Tier:** This tier permits unrestricted data flow to designated cloud endpoints. This configuration is exclusively reserved for institutional users operating under stringent Enterprise Agreements with AI providers (such as Microsoft Azure OpenAI or Google Cloud Vertex AI) that explicitly guarantee zero data retention and prohibit the utilization of user prompts for foundational model training.29

### **Audit Trailing and Custom Endpoint Orchestration**

Transparency regarding data transit is critical for organizational compliance and ethical accountability in archaeology. The system implements a cryptographic audit log embedded within the metadata of every generated site report. The log records precise telemetry regarding which data segments were processed locally versus remotely. Entries specify the timestamp, phase identifier, provider target, model version, and exact token payload size. A representative audit entry reads: \[Phase 3\] 112,847 tokens transmitted to Anthropic (claude-3-5-sonnet-20241022). Cost: $0.33. Data Classification: Sanitized Text.  
Furthermore, institutional users and large heritage agencies frequently leverage self-hosted inference infrastructure to maintain data custody while utilizing high-performance data centers. The ModelProvider interface natively supports custom base URLs. The configuration schema allows organizations to override the canonical OpenAI or Ollama endpoint addresses with internal IP routing, redirecting requests to internal instances of vLLM or Text Generation Inference (TGI) servers running securely behind a corporate Virtual Private Network.

## **Hardware-Aware Offline Model Tier System**

The disparity in computing environments across archaeological teams presents a significant engineering challenge. Field archaeologists may utilize fanless laptops with unified memory, while lab-based researchers may have access to desktop workstations equipped with dual 24 GB VRAM accelerators. A static model configuration guarantees either out-of-memory crashes for the former or underutilization of resources for the latter. The system implements an automatic profiling sequence to determine hardware viability and dynamically map the pipeline phases to the optimal local model tier.

### **VRAM Detection and Auto-Profiling**

Upon initialization, the application executes a hardware diagnostic sequence to gauge available physical resources. Relying on heavy tensor frameworks like PyTorch strictly for VRAM detection introduces unacceptable initialization overhead.30 Instead, the profiling module utilizes lightweight system bindings. On systems equipped with NVIDIA hardware, the application executes a subprocess call to nvidia-smi using \--query-gpu=memory.free \--format=csv, immediately parsing the available megabytes.32 Alternatively, the pynvml package interfaces directly with the NVIDIA Management Library, allowing precise programmatic access to memory states via nvmlDeviceGetMemoryInfo.33  
Based on the detected VRAM thresholds, the system automatically assigns the environment to a predefined execution tier.

| Tier Classification | VRAM Threshold | Phase 1 (Digitization) | Phase 2 (Vision) | Phase 3 (Synthesis) | Phase 4 (Refinement) |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Ultra-light** | Zero GPU | Cloud Endpoint Fallback | Cloud Endpoint Fallback | Cloud Endpoint Fallback | Cloud Endpoint Fallback |
| **Budget** | 6 GB | GLM-OCR (2.2 GB) | Qwen3-VL-4B (2.8 GB) | Qwen3.5-4B (2.8 GB) | Gemma 4-E2B (2.1 GB) |
| **Standard** | 8-12 GB | GLM-OCR (2.2 GB) | Qwen3-VL-8B (5.5 GB) | Qwen3.5-4B (2.8 GB) | Gemma 4-E2B (2.1 GB) |
| **Performance** | 16-24 GB | NuExtract3 (4.5 GB) | PaliGemma 2 (8 GB) | Qwen3-8B (5.5 GB) | Gemma 4-9B (5.5 GB) |

For the Budget tier, models are strictly constrained to fit within 6 GB limits. The application forcefully evicts models from VRAM sequentially, setting keep\_alive=0 on Ollama completion requests to ensure subsequent phases do not trigger out-of-memory cascades. The Standard tier lifts visual comprehension constraints, allowing the superior spatial understanding of Qwen3-VL-8B. The Performance tier scales to high-parameter architectures for exceptional local processing. Users can manually override the auto-detected tier via the YAML configuration file. If a user forces the Performance Tier on 8 GB hardware, the system logs a high-severity warning regarding imminent memory swapping but proceeds, allowing OS-level unified memory algorithms (such as Apple Silicon architecture) to handle swap operations.

### **NuExtract3 Integration via Custom Chat Handlers**

The deployment of NuExtract3 inside the Performance Tier introduces a significant technical complexity. NuExtract3 demonstrates unprecedented accuracy in unifying document extraction and OCR.10 However, the model requires a specialized prompt structure defined by empty JSON templates.12 Because NuExtract3 is distributed primarily in heavily quantized GGUF formats 34, the llama-cpp-python binding acts as the optimal execution host, eliminating the requirement for a local Ollama registry entry.  
Native llama-cpp-python lacks a default conversational wrapper for NuExtract3's proprietary prompt topology.36 Supplying raw text inputs using standard chatml formats results in erratic outputs or total failure to comply with the extraction schema.35 To resolve this, the abstraction layer registers a custom chat format handler dynamically. The application utilizes the @register\_chat\_format decorator native to the llama\_cpp.llama\_chat\_format module.39  
This injection middleware intercepts the template\_format defined in the InferenceRequest, extracts the empty JSON structure from the system prompt, and wraps the user text. It strictly formats the prompt according to NuExtract's required \<|input|\>\\n\#\#\# Template:\\n...\\n\#\#\# Text:\\n...\\n\<|output|\> topology.42 This dynamic formatting permits HOARD to seamlessly switch between GLM-OCR via Ollama and NuExtract3 via llama-cpp-python natively, without mutating the core application logic responsible for Phase 1 execution.

## **Configuration and Migration Pathway**

The configuration schema utilizes a highly structured YAML file located at \~/.config/hoard/config.yaml. This file dictates the entire operational behavior of the abstraction layer, defining global modes, per-phase overrides, and privacy constraints.

YAML  
system:  
  routing\_mode: quality \# Options: manual, auto, quality  
  latency\_budget\_seconds: 45  
  privacy\_tier: sanitized\_cloud \# Options: strict\_local, sanitized\_cloud, full\_hybrid  
  hardware\_tier: auto \# Options: auto, ultra\_light, budget, standard, performance

phases:  
  phase1:  
    primary:  
      provider: llama\_cpp  
      model: nuextract3  
      path: /models/NuExtract3-Q4\_K\_M.gguf  
    fallback:  
      provider: ollama  
      model: glm-4-9b-chat  
  phase3:  
    primary:  
      provider: anthropic  
      model: claude-3-5-sonnet-20241022  
      profile: default  
    fallback:  
      provider: google  
      model: gemini-2.5-flash

The integration of the multi-provider layer follows an incremental, non-destructive migration strategy. Phase one of the migration involves refactoring the core HOARD pipeline to interface exclusively with the generic ModelProvider protocol, initially utilizing only a single LocalOllamaProvider class to mimic current behavior identically. Phase two introduces the hardware auto-profiling module and the YAML configuration parser. Phase three integrates the CloudProvider implementations and the associated cryptographic vault. This phased deployment ensures that existing archaeological project processing remains entirely undisturbed during the architectural transition.

## **Financial Impact and Cost Analysis**

The financial efficiency of integrating cloud endpoints is highly relevant for independent archaeologists, freelance specialists, and smaller institutional units lacking the capital for dedicated inference hardware. While local inference incurs zero immediate operational token cost, the initial hardware expenditure, electrical overhead, and rapid depreciation of GPU technology present steep financial barriers. Utilizing high-efficiency cloud models drastically reduces the fiscal impact per site report, often proving cheaper than the physical depreciation of a workstation over a single report's drafting timeframe.  
A standard archaeological grey literature report typically encompasses roughly 50 context sheets, equating to a total processing payload of approximately 380,000 input tokens and 120,000 output tokens distributed across the four phases. The phase breakdowns dictate that Phase 1 (digitization) consumes roughly 50,000 input/output tokens, Phase 2 (vision) digests 100,000 input tokens via image parsing, Phase 3 (synthesis) ingests the massive 200,000 token context string, and Phase 4 (refinement) operates on a 30,000 token iterative loop.

| Provider Configuration | Input Cost per 1M | Output Cost per 1M | Estimated Cost (50-Context Report) | Prose Quality Yield |
| :---- | :---- | :---- | :---- | :---- |
| **Fully Local (Ollama)** | $0.00 | $0.00 | $1.95 (Hardware Amortization Equivalent) | Baseline |
| **Gemini 2.5 Flash-Lite** | $0.10 16 | $0.40 16 | \~$0.086 | Moderate |
| **GPT-4o-mini** | $0.15 18 | $0.60 18 | \~$0.129 | High |
| **Gemini 2.5 Flash** | $0.30 6 | $2.50 6 | \~$0.414 | High |
| **Claude 3.5 Haiku** | $0.80 44 | $4.00 44 | \~$0.784 | High |
| **Claude 3.5 Sonnet** | $3.00 7 | $15.00 7 | \~$2.940 | Premium |

The data confirms the economic viability of the hybrid model. Utilizing budget-oriented cloud endpoints like Gemini 2.5 Flash-Lite or GPT-4o-mini reduces operational costs to mere cents per report, a fraction of the local hardware amortization threshold, while simultaneously elevating prose structure, logical synthesis, and processing speed.7 Even employing advanced mid-tier models like Claude 3.5 Haiku 20 or Gemini 2.5 Flash 6 presents an economical pathway, generating publication-ready synthesis for less than a single US dollar per site. The capacity to switch between these financial tiers dynamically allows project managers to align computational expenditure directly with project funding levels.  
The architectural overhaul of the HOARD platform from a rigidly localized system into a multi-provider hybrid engine represents a pivotal evolution. By instituting a robust, type-safe provider interface with dynamic context and schema normalization, the system circumvents the intrinsic limitations of consumer-grade hardware. It simultaneously preserves the essential requirement of absolute data sovereignty through strict routing heuristics, explicit privacy tiers, and offline-first hardware profiling. The integration of AES-256-GCM cryptography guarantees that external endpoint deployment never compromises internal security paradigms, while bespoke format handlers enable the seamless execution of highly specialized extraction models like NuExtract3. This specification ensures that archaeological research teams can leverage the bleeding edge of natural language reasoning without relinquishing control over sensitive heritage data.

#### **Works cited**

1. Internet Archaeol 17\. Falkingham. \- Internet Archaeology, accessed June 8, 2026, [https://intarch.ac.uk/journal/issue17/5/gf1-4to1-5-5.html](https://intarch.ac.uk/journal/issue17/5/gf1-4to1-5-5.html)  
2. Assessing The Research Potential of Grey Literature in the study of Roman England \- Data Catalogue, accessed June 8, 2026, [https://archaeologydataservice.ac.uk/data-catalogue/resource/f325bfbd590f0b3f32c5f68f122201edae73fd9768281dd4e92675339858fc3a](https://archaeologydataservice.ac.uk/data-catalogue/resource/f325bfbd590f0b3f32c5f68f122201edae73fd9768281dd4e92675339858fc3a)  
3. Evaluating the Future for Grey Literature \- White Rose eTheses Online, accessed June 8, 2026, [https://etheses.whiterose.ac.uk/id/eprint/27061/1/Full%20Document%20Nicola%20Thorpe%20PhD%20Thesis%20with%20corrections.pdf](https://etheses.whiterose.ac.uk/id/eprint/27061/1/Full%20Document%20Nicola%20Thorpe%20PhD%20Thesis%20with%20corrections.pdf)  
4. Getting Started \- LiteLLM, accessed June 8, 2026, [https://docs.litellm.ai/docs/](https://docs.litellm.ai/docs/)  
5. GitHub \- BerriAI/litellm: Python SDK, Proxy Server (AI Gateway) to call 100+ LLM APIs in OpenAI (or native) format, with cost tracking, guardrails, loadbalancing and logging. \[Bedrock, Azure, OpenAI, VertexAI, Cohere, Anthropic, Sagemaker, HuggingFace, VLLM, NVIDIA NIM\], accessed June 8, 2026, [https://github.com/BerriAI/litellm/](https://github.com/BerriAI/litellm/)  
6. Gemini 2.5 Flash API Pricing 2026 \- Costs, Performance & Providers \- Price Per Token, accessed June 8, 2026, [https://pricepertoken.com/pricing-page/model/google-gemini-2.5-flash](https://pricepertoken.com/pricing-page/model/google-gemini-2.5-flash)  
7. Every Claude Model, Compared: Versions, Pricing & Which to Use \- TeamAI, accessed June 8, 2026, [https://teamai.com/blog/large-language-models-llms/understanding-different-claude-models/](https://teamai.com/blog/large-language-models-llms/understanding-different-claude-models/)  
8. Structured Outputs (JSON Mode) \- LiteLLM, accessed June 8, 2026, [https://docs.litellm.ai/docs/completion/json\_mode](https://docs.litellm.ai/docs/completion/json_mode)  
9. Anthropic \- LiteLLM, accessed June 8, 2026, [https://docs.litellm.ai/docs/providers/anthropic](https://docs.litellm.ai/docs/providers/anthropic)  
10. Blog \- NuMind, accessed June 8, 2026, [https://numind.ai/blog](https://numind.ai/blog)  
11. numind/NuExtract3 \- Hugging Face, accessed June 8, 2026, [https://huggingface.co/numind/NuExtract3](https://huggingface.co/numind/NuExtract3)  
12. NuExtract: A Foundation Model for Structured Extraction \- NuMind, accessed June 8, 2026, [https://numind.ai/blog/nuextract-a-foundation-model-for-structured-extraction](https://numind.ai/blog/nuextract-a-foundation-model-for-structured-extraction)  
13. numindai/nuextract \- GitHub, accessed June 8, 2026, [https://github.com/numindai/nuextract](https://github.com/numindai/nuextract)  
14. Ollama chat endpoint parameters \- Medium, accessed June 8, 2026, [https://medium.com/@laurentkubaski/ollama-chat-endpoint-parameters-21a7ac1252e5](https://medium.com/@laurentkubaski/ollama-chat-endpoint-parameters-21a7ac1252e5)  
15. GPT-4o-mini \- API Pricing & Benchmarks | OpenRouter, accessed June 8, 2026, [https://openrouter.ai/openai/gpt-4o-mini](https://openrouter.ai/openai/gpt-4o-mini)  
16. Google Gemini API Pricing 2026: Complete Cost Guide per 1M Tokens \- Metacto, accessed June 8, 2026, [https://www.metacto.com/blogs/the-true-cost-of-google-gemini-a-guide-to-api-pricing-and-integration](https://www.metacto.com/blogs/the-true-cost-of-google-gemini-a-guide-to-api-pricing-and-integration)  
17. Gemini Developer API pricing, accessed June 8, 2026, [https://ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing)  
18. accessed June 8, 2026, [https://pricepertoken.com/pricing-page/model/openai-gpt-4o-mini\#:\~:text=GPT%204o%20mini%20was%20released,of%20up%20to%20128K%20tokens.](https://pricepertoken.com/pricing-page/model/openai-gpt-4o-mini#:~:text=GPT%204o%20mini%20was%20released,of%20up%20to%20128K%20tokens.)  
19. Claude 3.5 Sonnet Model Card \- PromptHub, accessed June 8, 2026, [https://www.prompthub.us/models/claude-3-5-sonnet](https://www.prompthub.us/models/claude-3-5-sonnet)  
20. Claude 3.5 vs GPT 4o: Which LLM Reigns Supreme? \- PromptLayer Blog, accessed June 8, 2026, [https://blog.promptlayer.com/big-differences-claude-3-5-vs-gpt-4o/](https://blog.promptlayer.com/big-differences-claude-3-5-vs-gpt-4o/)  
21. GPT 4o mini API Pricing 2026 \- Costs, Performance & Providers \- Price Per Token, accessed June 8, 2026, [https://pricepertoken.com/pricing-page/model/openai-gpt-4o-mini](https://pricepertoken.com/pricing-page/model/openai-gpt-4o-mini)  
22. AES GCM (Python) with PBKDF2 \- ASecuritySite.com, accessed June 8, 2026, [https://asecuritysite.com/aes/aes\_gcm2](https://asecuritysite.com/aes/aes_gcm2)  
23. AES-GCM encryption and decryption for Python, Java, and Typescript \- Medium, accessed June 8, 2026, [https://medium.com/@bh03051999/aes-gcm-encryption-and-decryption-for-python-java-and-typescript-562dcaa96c22](https://medium.com/@bh03051999/aes-gcm-encryption-and-decryption-for-python-java-and-typescript-562dcaa96c22)  
24. AES Encrypt / Decrypt \- Examples | Practical Cryptography for Developers, accessed June 8, 2026, [https://cryptobook.nakov.com/symmetric-key-ciphers/aes-encrypt-decrypt-examples](https://cryptobook.nakov.com/symmetric-key-ciphers/aes-encrypt-decrypt-examples)  
25. Satellite-Based Detection of Looted Archaeological Sites Using Machine Learning \- arXiv, accessed June 8, 2026, [https://arxiv.org/html/2602.19608v1](https://arxiv.org/html/2602.19608v1)  
26. Ethics and Best Practices for Mapping Archaeological Sites \- Cambridge University Press & Assessment, accessed June 8, 2026, [https://www.cambridge.org/core/journals/advances-in-archaeological-practice/article/ethics-and-best-practices-for-mapping-archaeological-sites/A7338404A56B73BB282C4A28B3B7264A](https://www.cambridge.org/core/journals/advances-in-archaeological-practice/article/ethics-and-best-practices-for-mapping-archaeological-sites/A7338404A56B73BB282C4A28B3B7264A)  
27. Satellite Imagery for the Investigation of Looted Archaeological Sites \- Trafficking Culture, accessed June 8, 2026, [https://traffickingculture.org/encyclopedia/theory-and-method/use-of-satellite-imagery-for-the-investigation-of-looted-archaeological-sites/](https://traffickingculture.org/encyclopedia/theory-and-method/use-of-satellite-imagery-for-the-investigation-of-looted-archaeological-sites/)  
28. Algorithmic Identification of Looted Archaeological Sites from Space \- Frontiers, accessed June 8, 2026, [https://www.frontiersin.org/journals/ict/articles/10.3389/fict.2017.00004/full](https://www.frontiersin.org/journals/ict/articles/10.3389/fict.2017.00004/full)  
29. Azure OpenAI Service \- Pricing, accessed June 8, 2026, [https://azure.microsoft.com/en-us/pricing/details/azure-openai/](https://azure.microsoft.com/en-us/pricing/details/azure-openai/)  
30. Tracking GPU Memory Usage | K \- Kannan Kumar, accessed June 8, 2026, [https://kannankumar.github.io/data-diary/jupyter/deep-learning/2020/04/22/Tracking\_GPU\_Memory\_Usage.html](https://kannankumar.github.io/data-diary/jupyter/deep-learning/2020/04/22/Tracking_GPU_Memory_Usage.html)  
31. How to check the GPU memory being used? \- PyTorch Forums, accessed June 8, 2026, [https://discuss.pytorch.org/t/how-to-check-the-gpu-memory-being-used/131220](https://discuss.pytorch.org/t/how-to-check-the-gpu-memory-being-used/131220)  
32. python \- how to programmatically determine available GPU memory with tensorflow?, accessed June 8, 2026, [https://stackoverflow.com/questions/59567226/how-to-programmatically-determine-available-gpu-memory-with-tensorflow](https://stackoverflow.com/questions/59567226/how-to-programmatically-determine-available-gpu-memory-with-tensorflow)  
33. How to Accurately Measure VRAM Usage \- Skyld, accessed June 8, 2026, [https://skyld.io/vram-profiler](https://skyld.io/vram-profiler)  
34. MaziyarPanahi/NuExtract-1.5-smol-GGUF \- Hugging Face, accessed June 8, 2026, [https://huggingface.co/MaziyarPanahi/NuExtract-1.5-smol-GGUF](https://huggingface.co/MaziyarPanahi/NuExtract-1.5-smol-GGUF)  
35. numind/NuExtract-2.0-4B-GGUF \- Hugging Face, accessed June 8, 2026, [https://huggingface.co/numind/NuExtract-2.0-4B-GGUF](https://huggingface.co/numind/NuExtract-2.0-4B-GGUF)  
36. Python bindings for llama.cpp \- GitHub, accessed June 8, 2026, [https://github.com/abetlen/llama-cpp-python](https://github.com/abetlen/llama-cpp-python)  
37. Gemma 4 tool calls returned as raw native tokens in \`content\` instead of \`tool\_calls\` · Issue \#2227 · abetlen/llama-cpp-python \- GitHub, accessed June 8, 2026, [https://github.com/abetlen/llama-cpp-python/issues/2227](https://github.com/abetlen/llama-cpp-python/issues/2227)  
38. LiquidAI/LFM2-VL-1.6B-GGUF · Proposed colab doesn't give reliable results., accessed June 8, 2026, [https://huggingface.co/LiquidAI/LFM2-VL-1.6B-GGUF/discussions/2](https://huggingface.co/LiquidAI/LFM2-VL-1.6B-GGUF/discussions/2)  
39. llama-cpp-python/llama\_cpp/llama\_chat\_format.py at main \- GitHub, accessed June 8, 2026, [https://github.com/AmpereComputingAI/llama-cpp-python/blob/main/llama\_cpp/llama\_chat\_format.py](https://github.com/AmpereComputingAI/llama-cpp-python/blob/main/llama_cpp/llama_chat_format.py)  
40. llama-cpp-python/llama\_cpp/llama\_chat\_format.py at main \- GitHub, accessed June 8, 2026, [https://github.com/abetlen/llama-cpp-python/blob/main/llama\_cpp/llama\_chat\_format.py](https://github.com/abetlen/llama-cpp-python/blob/main/llama_cpp/llama_chat_format.py)  
41. deepseek chat\_format template · Issue \#969 · abetlen/llama-cpp-python \- GitHub, accessed June 8, 2026, [https://github.com/abetlen/llama-cpp-python/issues/969](https://github.com/abetlen/llama-cpp-python/issues/969)  
42. SLM For Template Extraction With Ollama — The NuExtract model of SLMs that are fine-tuned for templated data extraction | John Maeda's Blog, accessed June 8, 2026, [https://maeda.pm/2024/11/16/slm-for-template-extraction-with-ollama-the-nuextract-model-of-slms-that-are-fine-tuned-for-templated-data-extraction/](https://maeda.pm/2024/11/16/slm-for-template-extraction-with-ollama-the-nuextract-model-of-slms-that-are-fine-tuned-for-templated-data-extraction/)  
43. QuantFactory/NuExtract-1.5-smol-GGUF \- Hugging Face, accessed June 8, 2026, [https://huggingface.co/QuantFactory/NuExtract-1.5-smol-GGUF](https://huggingface.co/QuantFactory/NuExtract-1.5-smol-GGUF)  
44. Claude 3.5 Haiku \- API Pricing & Benchmarks \- OpenRouter, accessed June 8, 2026, [https://openrouter.ai/anthropic/claude-3.5-haiku](https://openrouter.ai/anthropic/claude-3.5-haiku)