# **Architectural Blueprint for Local VLM Orchestration: Integrating llama.cpp Router Mode into Python CLI Pipelines**

The operational deployment of multiple multi-billion parameter Vision-Language Models (VLMs) within a heavily constrained 6 GB VRAM budget represents a complex resource allocation and systems engineering challenge. The HOARD pipeline, invoked via the erd run \--project \<id\> command-line interface, necessitates a sequential execution architecture where multiple AI models are instantiated, queried, and subsequently evicted without exceeding strict hardware limitations. Extensive architectural analysis indicates that the llama.cpp HTTP server, running in its native multi-model router mode, is the most robust and highly optimized orchestration engine for this pipeline paradigm.  
By leveraging the \--models-max 1 constraint alongside Least Recently Used (LRU) eviction algorithms, the native C++ llama-server allows the HOARD pipeline to treat a limited GPU memory pool as an ephemeral cache.1 When the Python CLI requests a model not currently residing in VRAM, the server automatically flushes the existing CUDA context and loads the newly requested model from non-volatile storage via memory mapping (mmap), handling the swap completely transparently to the calling Python client.2  
This comprehensive research report details the precise integration mechanics required to embed this architecture into the Python-based HOARD pipeline. It covers native binary deployment methodologies, Python process orchestration and daemonization, multimodal directory structuring, OpenAI-compatible API interactions, and strict VRAM-conscious GGUF quantization matrices for the specified 4B parameter vision-language models.

## **1\. Engine Compilation and Subsystem Discovery**

The foundation of the HOARD orchestration layer relies on the correct installation, optimization, and discovery of the llama.cpp backend engine. A common anti-pattern in Python-based local language model tooling is the reliance on direct Python bindings, such as the llama-cpp-python package, to host the inference engine within the same process space as the orchestrator. While suitable for isolated, single-model execution scripts, Python bindings introduce Global Interpreter Lock (GIL) contention, unnecessary memory overhead from the Python runtime, and severely complicate the usage of the highly optimized C++ router mode for multi-model orchestration.2 Consequently, the HOARD pipeline must interact exclusively with the standalone, compiled llama-server C++ binary running as a discrete daemonized process.

### **Compilation and Installation on Ubuntu 24 with CUDA**

For Ubuntu 24 environments equipped with NVIDIA hardware, relying on pre-compiled release binaries or compiling directly from source using CMake is strictly recommended over Python-based package managers like pip or conda.5 Compiling from source guarantees that the binary is linked against the exact CUDA toolkit version present on the host operating system, preventing highly detrimental driver mismatch errors that often plague local AI deployments. The Ubuntu 24 ecosystem relies on modern NVIDIA proprietary drivers (e.g., version 550 or newer) and the corresponding CUDA toolkit (e.g., version 12.4 or 12.8), which must be precisely matched during the ggml backend compilation phase.6  
The optimal installation sequence for an Ubuntu 24 environment requires the installation of the essential build toolchain, followed by native compilation using the hardware-acceleration flags. By cloning the official repository and invoking CMake with the GGML\_CUDA=ON flag, the compiler builds a localized binary optimized for the host's specific GPU architecture architecture.6

Bash  
\# Update local package indices and install required build toolchains  
sudo apt update && sudo apt install \-y build-essential libcurl4-openssl-dev cmake git

\# Clone the official llama.cpp repository  
git clone https://github.com/ggml-org/llama.cpp.git  
cd llama.cpp

\# Configure the build environment for NVIDIA CUDA acceleration  
cmake \-B build \-DGGML\_CUDA=ON

\# Compile the project utilizing all available CPU cores for speed  
cmake \--build build \--config Release \-j $(nproc) \-t llama-server

This compilation sequence generates the highly optimized llama-server executable within the ./build/bin/ directory. Alternatively, for end-users who do not possess a complete C++ toolchain or who wish to avoid source compilation, the official llama.cpp GitHub releases page provides pre-compiled ubuntu-cuda archives that can be downloaded and extracted directly.8

### **Robust Binary Discovery Mechanisms for the HOARD CLI**

Because the HOARD pipeline is designed to function as an independent CLI tool (erd), it must operate seamlessly even if the end-user has not installed llama.cpp in a standard POSIX location, or if multiple conflicting versions exist across the system. Relying purely on a standard environment PATH lookup is fundamentally insufficient for highly distributed CLI tools that depend on specific backend capabilities like the modern router mode.  
To ensure resilience, the CLI orchestrator must implement a robust, multi-tiered discovery mechanism to locate the llama-server executable. This mechanism is defined by a strict hierarchy of fallbacks. The primary layer of this hierarchy is a user-configured path. By checking an explicit path defined in the HOARD project configuration file (such as a local hoard.toml) or a global dotfile (\~/.config/hoard/config.toml), the application grants the user ultimate override authority.9 This is particularly useful for advanced users who compile custom forks of llama.cpp with experimental tensor operations.  
If a user override is not present, the secondary layer relies on a bundled or application-specific path. The HOARD CLI should maintain a dedicated backend directory, such as \~/.local/share/hoard/bin/llama-server. The CLI framework can include a dedicated initialization command (e.g., erd install-backend) that automatically securely downloads the correct pre-compiled CUDA binary archive from the official GitHub releases page, extracts it, and places it into this isolated path.7 This ensures the CLI provides a frictionless out-of-the-box experience without modifying the user's global system state.  
The tertiary and final layer is a standard system PATH lookup. By utilizing the POSIX which llama-server command (or Python's shutil.which), the CLI can detect globally installed instances that may have been provisioned by system package managers, Homebrew, or system administrators.8

### **Protocol Selection and API Client Wrapping**

For transmitting network requests from the Python modules to the llama-server backend, the official openai Python package represents the most robust, cleanest, and industry-standard wrapping solution.11 Because the llama-server natively exposes representational state transfer (REST) endpoints that perfectly mirror the OpenAI API specification, specifically the /v1/chat/completions route, utilizing the official client eliminates vast amounts of boilerplate code.4  
If the pipeline were to use a generic HTTP library such as httpx or requests, the developers would be forced to manually construct authorization headers, manage complex nested JSON serialization, and implement low-level HTTP retry logic and exponential backoffs.13 The openai package natively handles these concerns. Furthermore, the openai client natively supports the highly specific nested dictionary structures required for base64-encoded image payloads, which is an absolute necessity for querying the multimodal vision models utilized throughout the GPU-dependent phases of the HOARD pipeline.11

## **2\. Process Daemonization and Health Telemetry**

The llama-server must operate as a daemonized child process tightly bound to the execution lifecycle of the erd CLI orchestrator. Given that the pipeline relies on several sequential phases, the server must be initialized prior to Phase 1 and cleanly terminated after Phase 4 completes, or immediately upon a fatal crash within the Python execution context.

### **The Mechanics of Subprocess Management**

Subprocess management within a Python execution environment requires meticulous attention to POSIX signals and process group dynamics. If the erd CLI is prematurely terminated by the user via a SIGINT (Ctrl+C keystroke) or encounters an unhandled runtime exception, the child llama-server process might become orphaned. An orphaned inference server will indefinitely hold the 6 GB VRAM allocation in the GPU, entirely breaking subsequent runs of the pipeline and forcing the user to manually intervene with kill commands. To successfully mitigate this risk, the Python orchestrator must utilize process groups via os.setsid during the initialization of the subprocess, ensuring that termination signals can be broadcast to the entire process tree. Additionally, the orchestrator must register termination hooks using the Python atexit module, guaranteeing that cleanup routines are executed regardless of how the Python interpreter exits.

### **Health Polling and State Machine Telemetry**

When the llama-server executable is launched in router mode, the internal HTTP socket binds to the designated port almost instantaneously. However, the server is not immediately ready to process complex inference requests; it must first scan the model directories, build internal state maps, and optionally preload default weights.2  
To facilitate precise state tracking, the llama.cpp server exposes a dedicated telemetry endpoint at /health.14 When the server is initializing, or when it is actively flushing the CUDA context to swap a new model into VRAM during an LRU eviction, this endpoint returns an HTTP 503 Service Unavailable status code. Accompanying this status code is a JSON payload structured as {"error": {"code": 503, "message": "Loading model", "type": "unavailable\_error"}}.4  
Once the system achieves stability and is fully ready to receive and execute API calls, it transitions to returning an HTTP 200 OK status code with the JSON payload {"status": "ok"}.15 The Python orchestrator must implement a robust polling mechanism against this endpoint, querying it at regular intervals until the HTTP 200 response is detected, thereby preventing premature API calls that could result in connection resets or socket timeouts.17

### **Implementation of the Orchestrator Class**

Below is the exhaustive architectural implementation of the LlamaCppServer orchestrator class. It is designed to handle the multi-tiered binary discovery, robust subprocess lifecycle management, rigorous health polling, and intelligent port conflict resolution.

Python  
import os  
import time  
import shutil  
import atexit  
import socket  
import logging  
import subprocess  
import requests

\# Configure a module-level logger for backend orchestration telemetry  
logger \= logging.getLogger("hoard.backend")

class LlamaCppServer:  
    """  
    Orchestrates the lifecycle of the llama-server C++ binary in router mode.  
    Handles discovery, daemonization, health polling, and clean termination.  
    """  
    def \_\_init\_\_(  
        self,   
        models\_dir: str \= "./hoard\_models",   
        host: str \= "127.0.0.1",   
        port: int \= 8765,  
        binary\_path\_override: str | None \= None  
    ):  
        self.models\_dir \= os.path.abspath(models\_dir)  
        self.host \= host  
        self.port \= port  
        self.base\_url \= f"http://{self.host}:{self.port}"  
        self.process: subprocess.Popen | None \= None  
          
        \# Execute the multi-tiered binary discovery hierarchy  
        self.binary\_path \= self.\_discover\_binary(binary\_path\_override)  
        if not self.binary\_path:  
            raise FileNotFoundError(  
                "Critical Error: Could not locate the 'llama-server' binary. "  
                "Ensure it is installed in your PATH or configured in HOARD."  
            )

    def \_discover\_binary(self, override: str | None) \-\> str | None:  
        """  
        Executes the hierarchical discovery logic to locate the executable.  
        """  
        \# Tier 1: Explicit user configuration override  
        if override and os.path.isfile(override) and os.access(override, os.X\_OK):  
            return override  
          
        \# Tier 2: Application-specific local storage fallback  
        local\_bin \= os.path.expanduser("\~/.local/share/hoard/bin/llama-server")  
        if os.path.isfile(local\_bin) and os.access(local\_bin, os.X\_OK):  
            return local\_bin  
              
        \# Tier 3: Global system PATH lookup  
        return shutil.which("llama-server")

    def \_is\_port\_in\_use(self) \-\> bool:  
        """  
        Performs a socket connection test to determine if the target port is bound.  
        """  
        with socket.socket(socket.AF\_INET, socket.SOCK\_STREAM) as s:  
            return s.connect\_ex((self.host, self.port)) \== 0

    def start(self):  
        """  
        Initializes the llama.cpp server in the optimized multi-model router mode.  
        """  
        \# Port conflict resolution logic  
        if self.\_is\_port\_in\_use():  
            logger.warning(f"Network Port {self.port} is currently bound.")  
            \# Verify if the bound process is a healthy llama-server instance  
            if self.is\_healthy():  
                logger.info("Existing llama-server detected and healthy. Proceeding with reuse.")  
                return  
            else:  
                raise RuntimeError(  
                    f"Port {self.port} is occupied by an unknown process or an unresponsive server."  
                )

        \# Guarantee the existence of the model directory structure  
        os.makedirs(self.models\_dir, exist\_ok=True)

        \# Construct the command array with strict resource boundaries  
        cmd \=

        logger.info(f"Executing server daemon: {' '.join(cmd)}")  
          
        \# Redirect standard output and error streams to a discrete log file.  
        \# This prevents the CLI's standard output from being polluted by C++ inference logs.  
        self.log\_file \= open("hoard\_llama\_server.log", "w")  
        self.process \= subprocess.Popen(  
            cmd,  
            stdout=self.log\_file,  
            stderr=subprocess.STDOUT,  
            preexec\_fn=os.setsid \# Isolate the process group for clean POSIX termination  
        )

        \# Register a safety hook to guarantee VRAM cleanup upon unexpected interpreter exit  
        atexit.register(self.stop)  
          
        \# Block execution until the engine is fully operational  
        self.\_wait\_for\_health()

    def is\_healthy(self) \-\> bool:  
        """  
        Queries the telemetry endpoint to assess server readiness and state.  
        """  
        try:  
            \# Use a brief timeout to prevent hanging during the polling phase  
            response \= requests.get(f"{self.base\_url}/health", timeout=2)  
            \# HTTP 200 implies readiness. HTTP 503 implies active model swapping/loading.  
            if response.status\_code \== 200 and response.json().get("status") \== "ok":  
                return True  
        except requests.RequestException:  
            \# Catch connection resets or timeouts occurring during initial socket bind  
            pass  
        return False

    def \_wait\_for\_health(self, timeout\_seconds: int \= 45):  
        """  
        Executes a polling loop, blocking the pipeline until the server confirms readiness.  
        """  
        logger.info("Initiating health polling sequence for llama-server...")  
        start\_time \= time.time()  
          
        while time.time() \- start\_time \< timeout\_seconds:  
            \# Check if the child process has crashed prematurely  
            if self.process and self.process.poll() is not None:  
                raise RuntimeError(  
                    f"Fatal Error: llama-server crashed during initialization with exit code {self.process.returncode}."  
                )  
                  
            if self.is\_healthy():  
                logger.info("llama-server telemetry reports healthy status. Engine ready.")  
                return  
                  
            time.sleep(1) \# Yield execution briefly before the next poll  
              
        raise TimeoutError(  
            f"llama-server failed to report a healthy status within {timeout\_seconds} seconds."  
        )

    def stop(self):  
        """  
        Executes a clean shutdown sequence, terminating the server and flushing VRAM.  
        """  
        if self.process and self.process.poll() is None:  
            logger.info("Broadcasting termination signals to llama-server process group...")  
            try:  
                \# Transmit SIGTERM to the entire isolated process group  
                os.killpg(os.getpgid(self.process.pid), 15)  
                self.process.wait(timeout=5)  
            except subprocess.TimeoutExpired:  
                logger.warning("Graceful shutdown failed. Escalating to SIGKILL.")  
                os.killpg(os.getpgid(self.process.pid), 9)  
            except Exception as e:  
                logger.error(f"Unexpected exception during shutdown sequence: {e}")  
            finally:  
                self.process \= None  
                  
        if hasattr(self, 'log\_file') and not self.log\_file.closed:  
            self.log\_file.close()  
              
        \# Unregister the hook to prevent memory leaks if start/stop are invoked repeatedly  
        atexit.unregister(self.stop)

## **3\. VRAM Economics and Quantization Matrices**

The constraint of operating entirely within a 6 GB VRAM budget necessitates rigorous mathematical planning regarding tensor quantization and memory allocation. Large Language Models define their memory footprint primarily through the raw size of their parameter weights, followed by the memory required to maintain the Key-Value (KV) cache for the context window, and finally the overhead of the CUDA execution context itself.  
A standard 4-billion parameter model, if loaded in unquantized 16-bit floating-point format (F16), requires roughly 8 GB of VRAM solely for the parameter weights, instantly triggering an Out-Of-Memory (OOM) fatal error on a 6 GB GPU.18 To resolve this, the models must undergo block-wise quantization. By applying the Q4\_K\_M quantization matrix—a format that blends 4-bit and 6-bit quantization depending on the sensitivity of the specific tensor layers—the model's weight footprint is aggressively compressed to approximately 2.5 GB with statistically negligible degradation in inference reasoning capabilities.18  
When allocating the strict 6 GB budget for the multimodal phases of the HOARD pipeline, the architectural breakdown is structured as follows:

| Resource Component | Memory Format | Estimated VRAM Allocation | Notes |
| :---- | :---- | :---- | :---- |
| **Language Model Weights** | Q4\_K\_M (4.5 bits/weight) | \~2.50 GB | Highly compressed base tensors. |
| **Multimodal Projector** | F16 (16 bits/weight) | \~0.85 GB | Maintained in high precision to preserve spatial visual acuity. |
| **KV Cache** | F16 (at 8192 tokens) | \~0.60 GB | Stores attention keys/values for the context window. |
| **CUDA / OS Overhead** | N/A | \~0.50 GB | Display driver and PyTorch/CUDA runtime overhead. |
| **Total System Consumption** |  | **\~4.45 GB** |  |

This precise allocation leaves a secure operating margin of approximately 1.55 GB. This margin acts as a critical buffer, protecting the underlying operating system from kernel panics and preventing OOM failures during particularly complex generation sequences where transient memory spikes may occur. It is highly advised to maintain the multimodal projector weights in full F16 precision rather than quantizing them, as quantizing the visual embeddings drastically degrades optical character recognition and fine-detail visual grounding, which are essential for the pipeline's performance.19

## **4\. Multimodal Directory Topologies and Router Configuration**

The configuration of the \--models-dir parameter during the server startup sequence dictates exactly how the router engine discovers, categorizes, and identifies the available AI models.2 For a strictly text-based operational deployment, placing all .gguf files into a single flat directory is entirely sufficient. The router engine simply scans the directory upon initialization, registers each model, and derives the API model name directly from the file name on disk (e.g., the file qwen3-4b.gguf becomes accessible via the API as "qwen3-4b.gguf").2

### **The Strict Nested Subdirectory Requirement**

However, the HOARD pipeline utilizes highly advanced multimodal vision models, including Qwen3-VL, Gemma 4-E2B, and Chandra OCR 2\. These sophisticated architectures require two distinct, separate GGUF weight files to operate within the llama.cpp inference ecosystem:

1. **The Base Language Model**: The causal text-generation weights (e.g., Qwen3VL-4B-Instruct-Q4\_K\_M.gguf).  
2. **The Multimodal Projector (mmproj)**: A discrete file containing the Vision Transformer (ViT) or CLIP encoder, alongside the complex linear projection layers that map the visual image embeddings directly into the language model's latent vector space (e.g., mmproj-F16.gguf).22

If a specific model architecture requires an mmproj file for image ingestion, the llama-server auto-discovery engine imposes a strict structural constraint: the model components must be isolated within their own discrete, nested subdirectory.4 If these files are placed in a flat folder alongside other models, the C++ server cannot accurately map the vision projector to its corresponding language model, resulting in immediate multimodal inference failures.

### **Recommended hoard\_models/ Topology**

To guarantee deterministic model discovery and cleanly separate the conflicting projector files, the hoard\_models/ directory must be structured according to the following tree layout:  
hoard\_models/  
│  
├── Qwen3-4B-Thinking/  
│ └── Qwen3-4B-Thinking-2507-Q4\_K\_M.gguf  
│  
├── Qwen3-VL-4B-Instruct/  
│ ├── Qwen3VL-4B-Instruct-Q4\_K\_M.gguf  
│ └── mmproj-F16.gguf  
│  
├── Gemma-4-E2B/  
│ ├── gemma-4-E2B-it-Q4\_K\_M.gguf  
│ └── mmproj-F16.gguf  
│  
└── Chandra-OCR-2/  
├── chandra-ocr-2.Q4\_K\_M.gguf  
└── mmproj-f16.gguf

### **Deterministic Naming via Router Presets (models.ini)**

While relying on automatic directory discovery allows the API caller to request a model by supplying its path (e.g., passing "Qwen3-VL-4B-Instruct/Qwen3VL-4B-Instruct-Q4\_K\_M.gguf" to the client), this heavily couples the Python application code to highly specific file names. If a systems administrator later decides to download a different quantization variant (e.g., Q5\_K\_M), all hardcoded API calls throughout the HOARD CLI will fail.  
To elegantly abstract the underlying file paths from the application logic, llama-server supports a highly advanced \--models-preset configuration paradigm.4 By passing a specifically formatted models.ini file in place of, or alongside, the standard \--models-dir flag, the HOARD pipeline can define strict, permanent API aliases that never change, regardless of the underlying files.2  
An optimal models.ini implementation for the HOARD pipeline:

Ini, TOML  
\[vision-agent\]  
model \=./hoard\_models/Qwen3-VL-4B-Instruct/Qwen3VL-4B-Instruct-Q4\_K\_M.gguf  
mmproj \=./hoard\_models/Qwen3-VL-4B-Instruct/mmproj-F16.gguf  
ctx-size \= 8192  
n-gpu-layers \= 99

\[ocr-agent\]  
model \=./hoard\_models/Chandra-OCR-2/chandra-ocr-2.Q4\_K\_M.gguf  
mmproj \=./hoard\_models/Chandra-OCR-2/mmproj-f16.gguf  
ctx-size \= 4096  
n-gpu-layers \= 99

\[thinking-agent\]  
model \=./hoard\_models/Qwen3-4B-Thinking/Qwen3-4B-Thinking-2507\-Q4\_K\_M.gguf  
ctx-size \= 16384  
n-gpu-layers \= 99

By utilizing this preset architecture, the Python orchestrator simply issues an API request for the model named "vision-agent", and the internal router engine seamlessly resolves the underlying file paths, applies the specific context size limits, and ensures the correct vision projector is loaded.2 The official documentation detailing these configuration formats can be found in the([https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)).4

## **5\. API Invocation and Client-Side Orchestration**

With the router engine operating reliably under the \--models-max 1 constraint, only one model occupies the 6 GB VRAM budget at any specific millisecond.

### **Transparent Model Switching Dynamics**

When the Python CLI submits an HTTP POST request targeting an AI model that is not currently residing in the active memory space, the llama-server initiates a highly optimized LRU eviction protocol.1 The internal sequence of operations unfolds as follows:

1. The incoming HTTP request is intercepted and placed into the server's execution queue, keeping the TCP connection alive.  
2. The server immediately halts inference on the currently active model. It issues commands to flush the active CUDA tensors, instantly reclaiming the 4.45 GB VRAM footprint.1  
3. The server executes system-level mmap calls to map the newly requested .gguf target files from disk into system RAM, and rapidly offloads the computation layers across the PCIe bus into the GPU's VRAM.  
4. Once the new CUDA context is verified and established, the server pulls the pending HTTP request from the queue, processes the prompt, and begins streaming the response payload back to the client.2

For the Python application issuing the request, this complex swapping architecture is completely transparent. The developers are not required to manage manual /models/load or /models/unload API endpoints.2 The sole observable consequence of this swap is an increase in initial latency; the Time To First Token (TTFT) on a swap request is delayed by the physical time required to transfer gigabytes of tensor weights from the NVMe storage drive to the GPU (typically ranging from 1 to 4 seconds depending on PCIe bandwidth). Any subsequent requests directed to that same model occur instantaneously.2

### **Implementation of the Inference Caller**

The following Python function demonstrates how to securely request both standard text and highly complex multimodal visual completions using the official openai client package.

Python  
import base64  
from openai import OpenAI  
from openai import APIConnectionError, APIStatusError

def encode\_image(image\_path: str) \-\> str:  
    """  
    Reads a binary image file from disk and encodes it into a compliant base64 string.  
    """  
    with open(image\_path, "rb") as image\_file:  
        return base64.b64encode(image\_file.read()).decode('utf-8')

def call\_llama\_model(  
    model\_alias: str,   
    messages: list\[dict\],   
    image\_path: str | None \= None,  
    port: int \= 8765  
) \-\> str:  
    """  
    Transmits an inference request to the local llama.cpp router engine.  
      
    Args:  
        model\_alias: The string alias defined in models.ini (e.g., "vision-agent").  
        messages: The dialogue history formatted to OpenAI specifications.  
        image\_path: An optional absolute path to an image file for visual inference.  
        port: The local network port bound by the daemonized server.  
    """  
    \# Instantiate the client, overriding the default cloud URL to target localhost  
    client \= OpenAI(  
        base\_url=f"http://127.0.0.1:{port}/v1",  
        \# The API key is entirely ignored by the local server but is a mandatory   
        \# validation parameter for the Python SDK instantiation.  
        api\_key="sk-hoard-local-auth"   
    )

    \# Inject visual data into the prompt payload if an image is provided  
    if image\_path:  
        base64\_image \= encode\_image(image\_path)  
          
        \# According to the strict OpenAI multimodal specification, messages containing   
        \# images require the 'content' field to be constructed as a list of dictionaries.  
        last\_message \= messages\[-1\]  
        if last\_message\["role"\] \== "user":  
            original\_text \= last\_message.get("content", "")  
            last\_message\["content"\] \= \[  
                {  
                    "type": "text",   
                    "text": original\_text  
                },  
                {  
                    "type": "image\_url",  
                    "image\_url": {  
                        "url": f"data:image/jpeg;base64,{base64\_image}"  
                    }  
                }  
            \]

    try:  
        \# Execute the network API call. The 'model' parameter directs the router.  
        response \= client.chat.completions.create(  
            model=model\_alias,  
            messages=messages,  
            temperature=0.2, \# Low temperature forces highly deterministic analytical outputs  
            max\_tokens=1024,  
        )  
        return response.choices.message.content  
          
    except APIConnectionError as e:  
        raise RuntimeError(f"Failed to connect to the local inference engine: {e}")  
    except APIStatusError as e:  
        raise RuntimeError(f"Inference engine returned an error state: {e.status\_code} \- {e.response}")

## **6\. Internal Multimodal Processing Mechanisms**

The capability to process and analyze dense visual data alongside contextual text prompts is a defining characteristic of modern AI pipelines. Within the internal architecture of llama.cpp, visual processing is not an inherent, built-in property of the core causal language engine. Instead, it relies entirely on the external tensor definitions provided by the multi-modal projector file (mmproj).

### **How llama.cpp Translates Vision via the OpenAI Protocol**

When the call\_llama\_model function transmits a request containing a data:image/jpeg;base64 string payload 11, the underlying llama-server HTTP handler detects the presence of visual data. Before passing the textual prompt to the primary causal language model, the server detours the base64 payload through the separate mmproj tensor network.29  
The projector decodes the image, slices it into spatial patches, processes it through the Vision Transformer (ViT) or CLIP backbone, and ultimately generates highly dense vector embeddings that represent the spatial relationships and semantic contents of the image.22 These resulting visual embeddings are then seamlessly interleaved directly into the standard token embedding sequence of the user's text prompt. To the causal language model itself, the image simply appears as a highly dense, abstract sequence of standard text tokens.18  
If the mmproj file is missing, misconfigured, or accidentally omitted from the models.ini preset, the server will either aggressively reject the multimodal request with an HTTP 400 error or silently strip the image payload, degrading the operation to pure text completion. Therefore, strictly adhering to the mmproj directory structure and preset formatting defined in Section 4 is of paramount importance to the stability of the HOARD pipeline.

## **7\. Procurement Strategy for Pipeline Agents**

To finalize the pipeline architecture, the exact GGUF files must be procured from validated repositories. The models selected for the HOARD pipeline each serve highly specific operational purposes, ranging from complex mathematical reasoning to dense document optical character recognition.

### **Recommended GGUF Downloads and Taxonomy**

The following table provides the precise HuggingFace repositories and quantization filenames required to populate the hoard\_models/ directory securely within the 6 GB VRAM budget.

| Operational Agent | Base Model Target | GGUF Quantization Target | Validated HuggingFace Repository | Precise Filename Pattern |
| :---- | :---- | :---- | :---- | :---- |
| **Document OCR Extraction** | Chandra OCR 2 | Q4\_K\_M (\~3.07 GB) | prithivMLmods/chandra-ocr-2-GGUF 32 | chandra-ocr-2.Q4\_K\_M.gguf |
|  | *Visual Projector* | F16 (\~676 MB) |  | chandra-ocr-2.mmproj-f16.gguf 31 |
| **Visual Spatial Analytics** | Qwen3-VL-4B-Instruct | Q4\_K\_M (\~2.5 GB) | Qwen/Qwen3-VL-4B-Instruct-GGUF 18 | Qwen3VL-4B-Instruct-Q4\_K\_M.gguf |
|  | *Visual Projector* | F16 (\~839 MB) | unsloth/Qwen3-VL-4B-Instruct-GGUF 22 | mmproj-F16.gguf |
| **Pure Logic & Reasoning** | Qwen3-4B-Thinking-2507 | Q4\_K\_M (\~2.5 GB) | bartowski/Qwen\_Qwen3-4B-Thinking-2507-GGUF 20 | Qwen3-4B-Thinking-2507-Q4\_K\_M.gguf |
|  | *Visual Projector* | *N/A (Text Only Architecture)* |  |  |
| **Edge Vision (Alternative)** | Gemma 4-E2B | Q4\_K\_M (\~2.0 GB) | unsloth/gemma-4-E2B-it-GGUF 35 | gemma-4-E2B-it-Q4\_K\_M.gguf |
|  | *Visual Projector* | F16 (\~987 MB) |  | mmproj-F16.gguf 36 |

### **The Florence-2 Architectural Incompatibility**

The system requirements specifically queried the potential deployment of Florence-2-large via the GGUF format as a fallback vision model. Extensive architectural investigation confirms that **the Florence-2 model family is inherently incompatible with the llama.cpp ecosystem** at this time, and no valid GGUF quantization files exist for it.38  
Unlike Qwen3, Gemma, and Mistral architectures—which universally rely on a standard *Causal Decoder-Only* text generation architecture augmented with an external CLIP vision projection—Microsoft's Florence-2 utilizes a pure Sequence-to-Sequence (Encoder-Decoder) architecture combined with a highly specialized hierarchical DaViT (Dual Attention Vision Transformer) backbone.41 The ggml tensor library, which serves as the foundational mathematics backend for llama.cpp, currently lacks the requisite computation graphs to parse DaViT mechanisms and dual-encoder cross-attention routing protocols.40  
**Fallback Architectures and Resolution Strategies:**  
For the HOARD pipeline, there are two distinct, viable engineering paths to resolve the Florence-2 limitation:

1. **Direct Python Execution (Transformers/vLLM)**: If Florence-2's specific task performance metrics (such as precise semantic segmentation bounding boxes or panoptic segmentation) are absolutely essential to a specific phase of the pipeline, the orchestrator must load the model natively in Python using the transformers library, leveraging standard PyTorch and FlashAttention kernels.44 Because Florence-2-large is a highly efficient 0.77B parameter model, it natively consumes less than 2 GB of VRAM in pure F16 precision.38 However, integrating this into the pipeline requires strict, manual VRAM management within the Python CLI. The pipeline must instantiate the PyTorch model, execute the inference generation, explicitly call del model, and invoke the garbage collector alongside torch.cuda.empty\_cache() *before* initializing the LlamaCppServer to ensure the 6 GB hardware budget is fully restored.  
2. **Architectural Substitution via Chandra OCR**: If the operational objective for the phase in question is standard visual grounding, text bounding, optical character recognition, and dense document layout parsing, the HOARD pipeline should completely abandon Florence-2 and rely entirely on the **Chandra OCR 2** model. Chandra OCR 2 is heavily specialized for complex layout extraction, HTML/Markdown structural conversion, and dense multilingual document reading. It natively matches or exceeds Florence-2's core document extraction metrics while maintaining perfect, flawless compatibility with the llama.cpp GGUF paradigm and the existing router infrastructure.24 This allows the entire pipeline to remain unified under a single backend engine.

## **8\. Conclusion**

Implementing the highly sequential HOARD AI pipeline within a strict 6 GB VRAM budget is a highly achievable engineering goal through the strategic, optimized deployment of the standalone llama-server in router mode. By abstracting models via a centralized models.ini configuration matrix and orchestrating the underlying C++ binary via a robust, daemonized Python subprocess class equipped with health telemetry, the pipeline benefits from seamless LRU memory eviction.  
This architecture empowers the CLI to iteratively cycle through highly capable, domain-specific 4B parameter models—such as the spatial analytics engine in Qwen3-VL and the structural extraction engine in Chandra OCR—using standard, frictionless OpenAI API calls. Provided that the multimodal projectors (mmproj) are accurately mapped into nested subdirectories in full precision, and the Florence-2 architectural incompatibilities are bypassed in favor of native causal models, the resulting system guarantees a low-overhead, highly deterministic, and scalable local AI orchestration environment.

#### **Works cited**

1. Unload All llama.cpp Router Models Without Restarting | by Rost Glukhov \- Medium, accessed May 20, 2026, [https://medium.com/@rosgluk/https-www-glukhov-org-llm-hosting-llama-cpp-unload-llama-cpp-router-models-ae44fa14fd6f](https://medium.com/@rosgluk/https-www-glukhov-org-llm-hosting-llama-cpp-unload-llama-cpp-router-models-ae44fa14fd6f)  
2. New in llama.cpp: Model Management \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/blog/ggml-org/model-management-in-llamacpp](https://huggingface.co/blog/ggml-org/model-management-in-llamacpp)  
3. 2.2.2 Backend: llama.cpp · av/harbor Wiki \- GitHub, accessed May 20, 2026, [https://github.com/av/harbor/wiki/2.2.2-Backend:-llama.cpp](https://github.com/av/harbor/wiki/2.2.2-Backend:-llama.cpp)  
4. llama.cpp/tools/server/README.md at master · ggml-org/llama.cpp · GitHub, accessed May 20, 2026, [https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)  
5. Running Local LLMs on Ubuntu with NVIDIA GPU using llama.cpp | by Ederson Corbari, accessed May 20, 2026, [https://ecorbari.medium.com/running-local-llms-on-ubuntu-with-nvidia-gpu-using-llama-cpp-2ec2e010c040](https://ecorbari.medium.com/running-local-llms-on-ubuntu-with-nvidia-gpu-using-llama-cpp-2ec2e010c040)  
6. Llama.cpp CUDA Setup \- Running into Issues \- Is it Worth the Effort? : r/LocalLLaMA \- Reddit, accessed May 20, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1k903ov/llamacpp\_cuda\_setup\_running\_into\_issues\_is\_it/](https://www.reddit.com/r/LocalLLaMA/comments/1k903ov/llamacpp_cuda_setup_running_into_issues_is_it/)  
7. Engineer's Guide to Local LLMs with LLaMA.cpp on Linux \- DEV Community, accessed May 20, 2026, [https://dev.to/avatsaev/pro-developers-guide-to-local-llms-with-llamacpp-qwen-coder-qwencode-on-linux-15h](https://dev.to/avatsaev/pro-developers-guide-to-local-llms-with-llamacpp-qwen-coder-qwencode-on-linux-15h)  
8. ggml-org/llama.cpp: LLM inference in C/C++ \- GitHub, accessed May 20, 2026, [https://github.com/ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)  
9. Managing Instances \- Llamactl Documentation, accessed May 20, 2026, [https://llamactl.org/dev/managing-instances/](https://llamactl.org/dev/managing-instances/)  
10. lmstudio-community/gemma-4-E2B-it-GGUF \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/lmstudio-community/gemma-4-E2B-it-GGUF](https://huggingface.co/lmstudio-community/gemma-4-E2B-it-GGUF)  
11. llama.cpp \- LFM Docs\! \- Liquid AI, accessed May 20, 2026, [https://docs.liquid.ai/deployment/on-device/llama-cpp](https://docs.liquid.ai/deployment/on-device/llama-cpp)  
12. Working with Llama.cpp Embeddings | Software.Land, accessed May 20, 2026, [https://software.land/working-with-llama-cpp-embeddings/](https://software.land/working-with-llama-cpp-embeddings/)  
13. Llama.cpp Server | Guides \- Clore.ai, accessed May 20, 2026, [https://docs.clore.ai/guides/language-models/llamacpp-server](https://docs.clore.ai/guides/language-models/llamacpp-server)  
14. I Built a Local AI Coding Assistant — Here's What Actually Works \- Medium, accessed May 20, 2026, [https://medium.com/@rosgluk/i-built-a-local-ai-coding-assistant-heres-what-actually-works-1dd9cffe7d54](https://medium.com/@rosgluk/i-built-a-local-ai-coding-assistant-heres-what-actually-works-1dd9cffe7d54)  
15. examples/server/README.md · 5fac4d57643b1de8e9ab746f14d2fc4e319ae0c2 · aigc/llama.cpp, accessed May 20, 2026, [https://cnb.cool/aigc/llama.cpp/-/blob/5fac4d57643b1de8e9ab746f14d2fc4e319ae0c2/examples/server/README.md](https://cnb.cool/aigc/llama.cpp/-/blob/5fac4d57643b1de8e9ab746f14d2fc4e319ae0c2/examples/server/README.md)  
16. Don't bundle all responses together in llama-server in the logs, accessed May 20, 2026, [https://github.com/simonw/llm-llama-server/issues/2](https://github.com/simonw/llm-llama-server/issues/2)  
17. On-demand local LLMs with systemd socket activation \- jistr.com, accessed May 20, 2026, [https://www.jistr.com/blog/2025-09-05-on-demand-local-llm-with-systemd-socket-activation/](https://www.jistr.com/blog/2025-09-05-on-demand-local-llm-with-systemd-socket-activation/)  
18. Qwen/Qwen3-VL-4B-Instruct-GGUF \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF)  
19. mradermacher/Qwen3-VL-4B-Instruct-abliterated-GGUF \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/mradermacher/Qwen3-VL-4B-Instruct-abliterated-GGUF](https://huggingface.co/mradermacher/Qwen3-VL-4B-Instruct-abliterated-GGUF)  
20. lmstudio-community/Qwen3-4B-Thinking-2507-GGUF \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/lmstudio-community/Qwen3-4B-Thinking-2507-GGUF](https://huggingface.co/lmstudio-community/Qwen3-4B-Thinking-2507-GGUF)  
21. noctrex/Chandra-OCR-GGUF \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/noctrex/Chandra-OCR-GGUF](https://huggingface.co/noctrex/Chandra-OCR-GGUF)  
22. mmproj-BF16.gguf · unsloth/Qwen3-VL-4B-Instruct-GGUF at ca2827b6c72b3e50bcf5532813b8a2c708ae4857 \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/unsloth/Qwen3-VL-4B-Instruct-GGUF/blob/ca2827b6c72b3e50bcf5532813b8a2c708ae4857/mmproj-BF16.gguf](https://huggingface.co/unsloth/Qwen3-VL-4B-Instruct-GGUF/blob/ca2827b6c72b3e50bcf5532813b8a2c708ae4857/mmproj-BF16.gguf)  
23. ComfyUI-QwenVL custom node: Integrates the Qwen-VL series, including Qwen2.5-VL and the latest Qwen3-VL, with GGUF support for advanced multimodal AI in text generation, image understanding, and video analysis. · GitHub, accessed May 20, 2026, [https://github.com/1038lab/ComfyUI-QwenVL](https://github.com/1038lab/ComfyUI-QwenVL)  
24. fredrezones55/chandra-ocr-2:patch \- Ollama, accessed May 20, 2026, [https://ollama.com/fredrezones55/chandra-ocr-2:patch](https://ollama.com/fredrezones55/chandra-ocr-2:patch)  
25. Misc. bug: While using models-dir both web and api show all the gguf parts as models · Issue \#19960 · ggml-org/llama.cpp \- GitHub, accessed May 20, 2026, [https://github.com/ggml-org/llama.cpp/issues/19960](https://github.com/ggml-org/llama.cpp/issues/19960)  
26. Misc. bug: llama-server \--models-preset creates an unexpected "default" model entry · Issue \#22364 · ggml-org/llama.cpp \- GitHub, accessed May 20, 2026, [https://github.com/ggml-org/llama.cpp/issues/22364](https://github.com/ggml-org/llama.cpp/issues/22364)  
27. Llama-Server Router Mode \- Dynamic Model Switching Without Restarts \- Rost Glukhov, accessed May 20, 2026, [https://www.glukhov.org/llm-hosting/llama-cpp/llama-server-router-mode/](https://www.glukhov.org/llm-hosting/llama-cpp/llama-server-router-mode/)  
28. Deploying Gemma 4 Multimodal on Snowflake: Text and Image Inference with llama.cpp and SPCS | by Adrian Lee Xinhan | Apr, 2026, accessed May 20, 2026, [https://adrianleexinhan.medium.com/deploying-gemma-4-multimodal-on-snowflake-text-and-image-inference-with-llama-cpp-and-spcs-76eec0a6d444](https://adrianleexinhan.medium.com/deploying-gemma-4-multimodal-on-snowflake-text-and-image-inference-with-llama-cpp-and-spcs-76eec0a6d444)  
29. guide : using llama-ui — the new WebUI of llama.cpp \#16938 \- GitHub, accessed May 20, 2026, [https://github.com/ggml-org/llama.cpp/discussions/16938](https://github.com/ggml-org/llama.cpp/discussions/16938)  
30. Qwen 3.5 is multimodal. Here is how to enable image understanding in opencode with llama cpp : r/LocalLLaMA \- Reddit, accessed May 20, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1rgxr0v/qwen\_35\_is\_multimodal\_here\_is\_how\_to\_enable\_image/](https://www.reddit.com/r/LocalLLaMA/comments/1rgxr0v/qwen_35_is_multimodal_here_is_how_to_enable_image/)  
31. chandra-ocr-2.mmproj-f16.gguf \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/prithivMLmods/chandra-ocr-2-GGUF/blob/main/chandra-ocr-2.mmproj-f16.gguf](https://huggingface.co/prithivMLmods/chandra-ocr-2-GGUF/blob/main/chandra-ocr-2.mmproj-f16.gguf)  
32. prithivMLmods/chandra-ocr-2-GGUF \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/prithivMLmods/chandra-ocr-2-GGUF](https://huggingface.co/prithivMLmods/chandra-ocr-2-GGUF)  
33. mmproj-F32.gguf · unsloth/Qwen3-VL-4B-Instruct-GGUF at main \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/unsloth/Qwen3-VL-4B-Instruct-GGUF/blob/main/mmproj-F32.gguf](https://huggingface.co/unsloth/Qwen3-VL-4B-Instruct-GGUF/blob/main/mmproj-F32.gguf)  
34. bartowski/Qwen\_Qwen3-4B-Thinking-2507-GGUF \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/bartowski/Qwen\_Qwen3-4B-Thinking-2507-GGUF](https://huggingface.co/bartowski/Qwen_Qwen3-4B-Thinking-2507-GGUF)  
35. unsloth/gemma-4-E2B-it-GGUF \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF](https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF)  
36. mmproj-BF16.gguf · unsloth/gemma-4-E2B-it-GGUF at 693864e73eb76cb7f0b67087dfc97f66625c18de \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/blob/693864e73eb76cb7f0b67087dfc97f66625c18de/mmproj-BF16.gguf](https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/blob/693864e73eb76cb7f0b67087dfc97f66625c18de/mmproj-BF16.gguf)  
37. mmproj-F16.gguf · unsloth/gemma-4-E2B-it-GGUF at main \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/blob/main/mmproj-F16.gguf](https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/blob/main/mmproj-F16.gguf)  
38. With Florence-2 just out, I'd like to know what kind of specs are needed for vision models? I run llama3 8gb on LM Studio alright, but compatibility guess is showing I can't get Florence-2 \- how big are the files? I really can't tell : r/LocalLLaMA \- Reddit, accessed May 20, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1djn6om/with\_florence2\_just\_out\_id\_like\_to\_know\_what\_kind/](https://www.reddit.com/r/LocalLLaMA/comments/1djn6om/with_florence2_just_out_id_like_to_know_what_kind/)  
39. Run Florence — 2 model on Colab (free) \- Raj Hammeer S. Hada \- Medium, accessed May 20, 2026, [https://medium.com/@hammeerraj/run-florence-2-model-on-colab-free-800b4e4e8b17](https://medium.com/@hammeerraj/run-florence-2-model-on-colab-free-800b4e4e8b17)  
40. Feature Request: Support for Florence-2 Vision Models · Issue \#8012 · ggml-org/llama.cpp, accessed May 20, 2026, [https://github.com/ggml-org/llama.cpp/issues/8012](https://github.com/ggml-org/llama.cpp/issues/8012)  
41. microsoft/Florence-2-large \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/microsoft/Florence-2-large](https://huggingface.co/microsoft/Florence-2-large)  
42. Microsoft releases Florence-2 vision foundation models (MIT license) \- Reddit, accessed May 20, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1diz8en/microsoft\_releases\_florence2\_vision\_foundation/](https://www.reddit.com/r/LocalLLaMA/comments/1diz8en/microsoft_releases_florence2_vision_foundation/)  
43. microsoft/Florence-2-large · Discussions \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/microsoft/Florence-2-large/discussions?p=1\&status=open](https://huggingface.co/microsoft/Florence-2-large/discussions?p=1&status=open)  
44. Florence2 Inference \- vLLM, accessed May 20, 2026, [https://docs.vllm.ai/en/v0.7.2/getting\_started/examples/florence2\_inference.html](https://docs.vllm.ai/en/v0.7.2/getting_started/examples/florence2_inference.html)  
45. Kijai released a Comfy node for Florence 2\! I'm getting MUCH faster captioning performance than with MoonDream 2 on Windows, it's only a bit slower than the WD-VIT-3 tagger model per image on my hardware. : r/StableDiffusion \- Reddit, accessed May 20, 2026, [https://www.reddit.com/r/StableDiffusion/comments/1dk01sq/kijai\_released\_a\_comfy\_node\_for\_florence\_2\_im/](https://www.reddit.com/r/StableDiffusion/comments/1dk01sq/kijai_released_a_comfy_node_for_florence_2_im/)  
46. \[Benchmarks\] Microsoft's small Florence-2 models are excellent for Visual Question Answering (VQA): On-par and beating all LLaVA-1.6 variants. \- Reddit, accessed May 20, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1dl232x/benchmarks\_microsofts\_small\_florence2\_models\_are/](https://www.reddit.com/r/LocalLLaMA/comments/1dl232x/benchmarks_microsofts_small_florence2_models_are/)  
47. prithivMLmods/chandra-OCR-GGUF \- Hugging Face, accessed May 20, 2026, [https://huggingface.co/prithivMLmods/chandra-OCR-GGUF](https://huggingface.co/prithivMLmods/chandra-OCR-GGUF)