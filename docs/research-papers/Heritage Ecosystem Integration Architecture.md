# **HOARD — Ecosystem Integration Architecture**

## **Executive Architectural Synthesis**

The transition of the Heritage Observation And Report Drafter (HOARD) from a standalone artificial intelligence pipeline into a foundational node within a broader heritage science open-source ecosystem necessitates a paradigm shift in software architecture. The current landscape is characterized by a suite of highly specialized, domain-specific applications—including StratiGraph for Harris Matrix visualization, Trowel for desktop reporting, Libby for radiocarbon calibration, Cache & Carry for vocabulary management, and several other tools in varying stages of maturity. While these tools excel in their isolated functions, the absence of a unified data contract, orchestration layer, and standardized inter-process communication protocol has led to severe schema drift and redundant integration efforts.  
The core architectural challenge is the design of a highly interoperable ecosystem that strictly adheres to the constraints of its operating environment: it must be entirely offline-first, optimized for consumer-grade hardware, independent of background server dependencies, and maintainable by a single developer working with constrained resources. This report provides an exhaustive, systemic blueprint for resolving these challenges. It addresses the formulation of a shared data model across Python, Rust, and TypeScript environments; the orchestration of multi-stage analytical pipelines; the integration of a unified, AI-compatible vocabulary service; and the abstraction of command-line interfaces. By systematically resolving these four operational pillars, the ecosystem can achieve seamless data mobility, allowing archaeological field data to flow from raw digitization through topological validation, chronometric calibration, and ultimately to synthesized compliance reporting without user friction.

## **Shared Data Model Design**

The fundamental prerequisite for any cross-project interoperability is the establishment of a unified, versioned data model that guarantees strict serialization contracts across the entire software suite. Without a centralized schema registry or runtime dependencies, this data model must be deterministically generable across the ecosystem's diverse technological stack, which includes Python, Rust, and TypeScript.

### **Protocol and Schema Generation Strategy**

The ecosystem requires an Interface Definition Language (IDL) capable of acting as a single source of truth while emitting native type bindings for all participant languages. An analysis of available serialization protocols—including Protocol Buffers, FlatBuffers, and Cap'n Proto—reveals that their binary nature and reliance on compiled stubs introduce unnecessary complexity for file-based interoperability and hinder human-readable debugging of archaeological data sets.1  
The optimal strategic approach utilizes TypeSpec, a domain-specific language developed to facilitate design-first schema creation utilizing a lightweight, TypeScript-like syntax.1 TypeSpec compiles directly into JSON Schema Draft 2020-12, which serves as the universal transport contract for the ecosystem.1 JSON Schema Draft 2020-12 provides expressive validation constraints and is natively supported by modern type generators. Instead of relying on a centralized registry or a shared runtime library, each project will independently compile the necessary subset of native types from this shared JSON Schema during its local build step.  
In the Python environment (powering HOARD, Trowel, Dibble, and Fritts), the datamodel-code-generator library will be integrated into the build pipeline. This utility parses OpenAPI and JSON Schema specifications, converting complex constructs like $ref, allOf, and oneOf into native Pydantic V2 models.5 This ensures strict runtime validation and zero-cost serialization into Python dictionaries. For the Rust stack (driving DIG, Cache & Carry, and the StratiGraph backend), the typify procedural macro crate will be deployed within build.rs scripts.8 Typify translates JSON Schema objects into Rust struct definitions, arrays into Vec\<T\> or HashSet\<T\>, and oneOf constructs into Rust enum types, leveraging the serde framework for high-performance deserialization.8 Concurrently, the native TypeSpec compiler will emit strict TypeScript interfaces for front-end applications like StratiGraph, Libby, and Cartulary.1 This decentralized compilation strategy entirely eliminates runtime schema dependencies, allowing each binary to operate autonomously.

### **Minimal Shared Type Hierarchy**

The data model must encompass the core ontological entities of archaeological fieldwork. The Frictionless Data Harris Matrix Data Package (HMDP) provides a theoretical foundation for representing stratigraphic data as lightweight tabular structures, separating context metadata from observational relationships.11 Expanding upon this logic, the core JSON Schema hierarchy will implement the following minimal shared types:

| Entity Type | Primary Consumers | Sub-types / Core Properties |
| :---- | :---- | :---- |
| SiteMetadata | All Projects | project\_id, jurisdiction, coordinate\_system, epsg\_code, director. |
| StratigraphicUnit | HOARD, StratiGraph, Trowel | unit\_id, type (positive/negative), description, dimensions, interpretation. |
| StratigraphicRelationship | HOARD, StratiGraph, Trowel | source\_id, target\_id, relationship\_type (e.g., *earlier\_than*, *cuts*, *fills*). |
| Find | HOARD, Trowel, Dibble | find\_id, context\_id, material\_class, typology, quantification (count/weight). |
| Sample | HOARD, Libby, IsoMap | sample\_id, context\_id, type (C14, environmental), volume. |
| Chronology | Libby, HOARD, Fritts | sample\_id, lab\_code, uncal\_bp, error, calibrated\_ranges (HPD/SPD). |
| DigitalAsset | HOARD, Trowel, DIG | asset\_id, file\_path, asset\_type (photo, drawing, geophysics\_grid). |

Cross-referencing between these entities is critical. Deeply nested objects (e.g., embedding a full StratigraphicUnit inside a Find object) generate severe data duplication and synchronization issues. Consequently, cross-referencing will exclusively utilize typed string Universally Unique Identifiers (UUIDs). A Find object will contain a context\_id string matching the UUID of the corresponding StratigraphicUnit. This relational architecture prevents redundant nesting, perfectly aligns with relational database structures should a project wish to ingest the JSON into SQLite, and drastically simplifies the topological computation of the Harris Matrix.11

### **Schema Evolution and Compatibility**

The inevitability of schema evolution—such as HOARD introducing a new soil\_compaction field to the ContextSheet in version 2 while StratiGraph continues to operate on version 1—must be managed through strict adherence to the robustness principle (Postel's Law).  
Compatibility is maintained by utilizing the JSON Schema additionalProperties: true directive. When typify processes an object schema lacking defined properties or allowing additional ones, it falls back to parsing unknown fields into a HashMap\<String, serde\_json::Value\>, allowing the Rust application to gracefully ingest, ignore, or pass through unmapped data.8 Similarly, Pydantic V2 models generated by datamodel-code-generator will be configured with model\_config \= ConfigDict(extra='allow'). This forward/backward compatibility strategy ensures that a localized update to one tool's data model does not trigger cascading deserialization failures across the ecosystem.

### **Inter-Process Communication (IPC) Protocol**

The constraint for consumer-hardware compatibility without background services dictates the IPC strategy. While memory-mapped files or Unix domain sockets provide sub-millisecond latency, they introduce severe cross-platform compatibility issues (particularly on Windows) and require applications to be concurrently executing.  
Therefore, file-based IPC is unequivocally the superior approach for this ecosystem. The shared data model will be serialized as standard .json files within a designated workspace directory. The location of this workspace will be determined dynamically using standard platform directory libraries (platformdirs for Python, directories for Rust), adhering strictly to the XDG Base Directory Specification.16 Data will be written to $XDG\_DATA\_HOME/heritage/workspaces/{project\_id}/, establishing a deterministic, inspectable, and highly durable state exchange mechanism.

### **Deliverables for Question 1**

**1\. Recommendation:** Implement TypeSpec as the single source of truth for data modeling. Compile the .tsp files into JSON Schema Draft 2020-12, and utilize datamodel-code-generator (Python), typify (Rust), and the native compiler (TypeScript) to generate native, statically typed objects during the respective build processes of each ecosystem project. Inter-process communication will rely entirely on file drops within XDG-compliant workspace directories.  
**2\. Architecture Diagram:**

Code snippet  
graph TD  
    A \--\>|TypeSpec Compiler| B  
    B \--\>|datamodel-code-generator| C  
    B \--\>|typify macro| D  
    B \--\>|TypeSpec Native| E  
      
    C \--\>|Serialize/Deserialize| F{XDG Workspace Storage}  
    D \--\>|Serialize/Deserialize| F  
    E \--\>|Serialize/Deserialize| F

**3\. Concrete Implementation Plan:**

1. Initialize a new, standalone GitHub repository named heritage-types.  
2. Author the core domain models in TypeSpec (main.tsp), covering SiteMetadata, StratigraphicUnit, Find, Sample, and Chronology.  
3. Configure the TypeSpec compiler via tspconfig.yaml to emit a bundled schema-v1.json utilizing the @typespec/json-schema emitter.1  
4. Publish heritage-types to npm (for TypeScript consumption) and as a raw repository for submodule inclusion in Rust/Python projects.  
5. In the HOARD Python project, add datamodel-code-generator to the pyproject.toml dev-dependencies and configure a Makefile command to auto-generate hoard/models/heritage\_core.py prior to packaging.19  
6. In the StratiGraph Rust backend, add typify to Cargo.toml dependencies and configure a build.rs script to invoke import\_types\!("schema-v1.json").8

**4\. Schema Fragments:**  
The foundational TypeSpec model (main.tsp) establishes the exact structural constraints required for JSON generation:

Code snippet  
import "@typespec/json-schema";  
using JsonSchema;

@jsonSchema  
namespace HeritageCore;

@description("Base archaeological context unit")  
model StratigraphicUnit {  
  @format("uuid")  
  @description("Unique internal identifier")  
  id: string;  
    
  @description("Alphanumeric context identifier assigned in the field")  
  unit\_code: string;  
    
  @description("Defines if the unit is a deposit (positive) or cut (negative)")  
  unit\_type: UnitType;  
    
  @description("Free-text archaeological interpretation")  
  interpretation?: string;  
    
  @description("Array of UUIDs representing associated finds")  
  find\_ids?: string;  
}

enum UnitType {  
  Positive: "positive",  
  Negative: "negative"  
}

@description("A chronometric sample taken from a stratigraphic unit")  
model Sample {  
  @format("uuid")  
  id: string;  
    
  @format("uuid")  
  @description("The stratigraphic unit this sample was extracted from")  
  context\_id: string;  
    
  @description("The analytical target of the sample")  
  sample\_type: SampleType;  
}

enum SampleType {  
  Radiocarbon: "C14",  
  Environmental: "environmental",  
  Isotopic: "isotope"  
}

**5\. Migration Path:**  
The migration will be executed incrementally. First, the heritage-types repository is published. HOARD and StratiGraph, which currently share a manually synced JSON file, will be refactored to pull from heritage-types simultaneously. Trowel will temporarily maintain its legacy hoard\_import.py script, which will be updated to map the incoming standard schema to its internal Pandas dataframes. Once the core pipeline is stable, Trowel and Libby will fully adopt the native code generators, deprecating their internal mapping modules.  
**6\. Risk Assessment:**  
The primary risk associated with this architecture is the potential for silent data loss if an application aggressively sanitizes unknown fields during a read/write cycle. If Trowel reads a StratigraphicUnit containing a new field generated by HOARD, and Trowel subsequently re-serializes that object to disk without preserving the unmapped fields via typify's fallback mechanisms, the data is destroyed. To mitigate this, comprehensive unit tests must be implemented in the build pipeline of each project. These tests will inject mock JSON payloads containing extraneous fields, assert that the application successfully parses the known data, and explicitly verify that the extraneous fields survive a complete read-modify-write cycle.

## **Cross-Project Pipeline Orchestration**

Transforming the ecosystem from a collection of isolated utilities into a seamless, end-to-end processing pipeline requires a robust orchestration layer. An archaeologist must be capable of initiating a workflow where field photographs are triaged, digitized, topologically validated, specialist-analyzed, and synthesized into a final report without manual data shuffling.

### **Orchestration Paradigm: Choreography over Orchestration**

Enterprise data pipelines frequently rely on centralized orchestration engines (e.g., Apache Airflow, AWS Step Functions) operating continuously in the background.20 However, the constraints of the heritage ecosystem—consumer hardware, offline environments, and single-developer maintenance—render daemon-based orchestration unviable. The architecture must instead rely on a local, choreography-based saga pattern implemented via a persistent finite state machine.22  
Rather than extending HOARD's specific hoard run command, the orchestration logic warrants a dedicated meta-command interface: heritage run. This orchestrator operates as a transient execution script. It reads a declarative pipeline definition (e.g., a pipeline.yaml outlining the Directed Acyclic Graph of dependencies), determines the required sequence of independent executables, and invokes them as sequential or parallel subprocesses. The orchestrator delegates the actual data processing to the sibling projects, merely acting as the traffic controller routing execution flags to the respective binaries.

### **State Management and Resumability**

Pipeline state will be serialized into a unified EcosystemState ledger (pipeline\_state.json), stored locally within the project workspace ($XDG\_DATA\_HOME/heritage/workspaces/{project\_id}/). This file functions as the immutable ledger of the workflow's progress.  
When the orchestrator invokes a process, it monitors the exit code of the subprocess. A standard pipeline state file will log the execution status of each node in the DAG. By treating the workflow as a persistent state machine written to disk, resumability is natively supported. If the pipeline is interrupted—due to a system reboot, a crash, or manual intervention—re-running heritage run \--project X will parse pipeline\_state.json, identify the last successful node, and resume execution from the pending stages, effectively guaranteeing an idempotent execution environment.20

### **Cross-Project Data Flow**

The transport mechanism for data flow between pipeline stages relies strictly on the file-based workspace utilizing the shared data models defined in Question 1\. The flow operates via sequential read/write operations against the single source of truth:

1. **Extraction:** The orchestrator invokes HOARD Phase 1\. HOARD digitizes context sheets and writes the initial contexts.json, relationships.json, and samples.json to the workspace.  
2. **Topological Validation:** The orchestrator invokes StratiGraph via a headless CLI command (stratigraph validate \--workspace {workspace\_path}). StratiGraph ingests contexts.json and relationships.json. It computes the Harris Matrix using graph theory protocols.11 If cycles are detected, it writes an errors.json flag; if the stratigraphy is physically viable, it writes a matrix\_valid.json flag back to the workspace.  
3. **Specialist Analysis:** The orchestrator identifies pending radiocarbon data and invokes Libby (libby calibrate \--workspace {workspace\_path}). Libby parses only samples.json (ignoring contexts), performs atmospheric calibration on the ![][image1] data utilizing the iosacal library, and writes a newly generated calibrated\_dates.json file.  
4. **Synthesis:** Following the completion of specialist modules, the orchestrator triggers HOARD Phase 3\. HOARD ingests the validated matrix and calibrated chronologies, utilizing them as structured, high-fidelity context for the LLM generation prompts, ensuring the synthesized report is geochronologically accurate.

### **Failure Model and Graceful Degradation**

In a decentralized ecosystem where users independently install applications via package managers, the orchestrator must anticipate missing binaries or local execution failures. The failure model employs a deterministic fallback mechanism based on node criticality.  
If a critical validation node fails (e.g., StratiGraph detects a cyclical error in the stratigraphic sequence preventing further chronological modeling), the pipeline enters a BLOCKED state. The orchestrator emits an error to stderr and pauses execution, instructing the user to open the StratiGraph GUI to manually resolve the cyclic graph anomaly.  
Conversely, if an optional analysis tool (e.g., Dibble for lithic classification or Fritts for dendrochronology) is absent from the host machine, the orchestrator invokes graceful degradation. The pipeline skips the missing dependency, marks the node as SKIPPED in the state ledger, emits a non-fatal warning to stdout, and instructs downstream consumers (HOARD Phase 3\) to insert standardized placeholders such as \`\` into the final draft. This ensures the user receives a partially complete grey literature report, preserving productivity despite environmental deficiencies.

### **Unified Jurisdiction Templates**

The current fragmentation of jurisdiction templates—14 for HOARD, 19 for Trowel, with partial overlap—represents severe technical debt. Resolving this requires a shared cross-project template format stored in a globally accessible configuration directory.16  
Templates will be centralized in $XDG\_CONFIG\_HOME/heritage/templates/. Each jurisdiction (e.g., *Wessex\_Archaeology\_Standard* or *Historic\_England\_Guidelines*) will be encapsulated in a subdirectory containing a metadata.json (defining target region and required fields), a structure.yaml (defining document hierarchy), and a series of Jinja2 (.j2) layout files. Both HOARD (via its Python Jinja2 engine) and Trowel (utilizing PyQt6 and Jinja2) will parse these templates. If Trowel requires specific GUI-rendering instructions that HOARD does not need, these will be encapsulated within a trowel\_extensions block in the template's JSON metadata. HOARD will safely ignore these extensions during headless generation.

### **Deliverables for Question 2**

**1\. Recommendation:** Implement a lightweight, choreography-based local orchestrator as a new meta-CLI tool (heritage run). Utilize the XDG workspace directory for file-based state exchange, and maintain a JSON-based finite state machine ledger to ensure idempotency and resumability. Unify jurisdiction templates in a centralized configuration directory utilizing Jinja2.  
**2\. Architecture Diagram:**

Code snippet  
graph TD  
    A \--\>|heritage run| B(Orchestrator: heritage-cli)  
      
    B \--\>|Subprocess Exec| C  
    C \--\>|Write JSON Data| D{XDG Workspace Storage}  
      
    D \--\>|Read Contexts| E  
    E \--\>|Write Validation State| D  
      
    D \--\>|Read Samples| F\[Libby CLI\]  
    F \--\>|Write Calibrated Dates| D  
      
    D \--\>|Read Lithic Specs| G  
    G \--\>|Write Tool Typologies| D  
      
    D \--\>|Read Aggregated Data| H  
    H \--\>|Render via Jinja2| I

**3\. Concrete Implementation Plan:**

1. Develop the Python orchestration module (heritage\_orchestrator.py) utilizing the networkx library to define and traverse the DAG of tool dependencies.  
2. Implement the state machine ledger, capable of reading and writing pipeline\_state.json.  
3. Establish the subprocess execution wrappers using Python's subprocess.run(), capturing stdout/stderr and exit codes to determine node success or failure.  
4. Migrate all existing HOARD and Trowel templates into the new structured format within the $XDG\_CONFIG\_HOME/heritage/templates/ directory.  
5. Refactor HOARD and Trowel to point their respective Jinja2 environment loaders to this new global directory.

**4\. Schema Fragments:**  
The pipeline\_state.json schema captures the deterministic status of the workflow:

JSON  
{  
  "$schema": "https://json-schema.org/draft/2020-12/schema",  
  "title": "EcosystemState",  
  "type": "object",  
  "properties": {  
    "project\_id": { "type": "string" },  
    "last\_updated": { "type": "string", "format": "date-time" },  
    "nodes": {  
      "type": "array",  
      "items": {  
        "type": "object",  
        "properties": {  
          "stage\_id": { "type": "string" },  
          "tool\_binary": { "type": "string" },  
          "status": {   
            "type": "string",   
            "enum":   
          },  
          "artifacts\_produced": { "type": "array", "items": { "type": "string" } },  
          "error\_log": { "type": "string" }  
        },  
        "required": \["stage\_id", "tool\_binary", "status"\]  
      }  
    }  
  }  
}

**5\. Migration Path:**  
The orchestrator can be introduced without breaking existing workflows. Users can continue to manually execute hoard run or open Trowel independently. The heritage run meta-command will initially support only a subset of the DAG (e.g., HOARD \-\> StratiGraph \-\> HOARD). Once this pipeline is verified, integration wrappers for Libby and Dibble will be added to the orchestrator's DAG registry, incrementally expanding the automated pipeline capabilities.  
**6\. Risk Assessment:**  
The primary risk associated with this architecture is race conditions during file I/O operations if the orchestrator attempts parallel execution of nodes that read/write to the same files in the workspace. To mitigate this, the orchestrator's DAG evaluation must strictly enforce synchronous, blocking execution for nodes sharing data dependencies. The orchestrator will utilize OS-level file-locking mechanisms (e.g., the filelock Python library) to guarantee that a downstream tool cannot ingest a JSON file until the upstream provider has fully flushed its buffer to disk and released the lock.

## **Unified Vocabulary Service**

Standardization of terminology is a pervasive bottleneck in archaeological data processing, essential for cross-site synthesis and compliance with regional archives. The Cache & Carry application presently provides a highly performant, sub-millisecond offline lookup interface for the Getty Art & Architecture Thesaurus (AAT), the Union List of Artist Names (ULAN), and the Thesaurus of Geographic Names (TGN) via an embedded SQLite database. Exposing this functionality universally across Python, Rust, and TypeScript environments without introducing network complexities dictates a specialized architectural approach.

### **Model Context Protocol (MCP) over Stdio**

The optimal architectural strategy is to isolate Cache & Carry as a standalone Model Context Protocol (MCP) server communicating over standard input/output (stdio) streams.25  
MCP defines a standardized JSON-RPC 2.0 interface engineered specifically to expose local "Tools" and "Resources" to AI applications and downstream clients.29 Implementing MCP achieves critical systemic goals. Primarily, utilizing stdio transport eliminates network overhead. Unlike REST or GraphQL APIs operating over HTTP, stdio transport does not require opening local network ports, thereby neutralizing firewall interventions and port-collision vulnerabilities common on restrictive enterprise or consumer hardware.30  
Furthermore, official MCP SDKs exist natively for Python, TypeScript, and Rust. This allows HOARD, StratiGraph, and Trowel to effortlessly instantiate the Cache & Carry MCP binary as a subprocess and query it asynchronously.25 Most significantly, because HOARD relies extensively on Large Language Models (LLMs) via Ollama, exposing the vocabulary service as a standardized MCP tool empowers the LLM to autonomously query the Getty vocabulary during Phase 1 (digitization) and Phase 4 (compliance) without requiring complex, hardcoded intermediary parsing logic.28 The LLM recognizes the available MCP tool schema and executes queries organically.

### **Query Interface and Normalization Backend**

The Cache & Carry MCP server will expose a discrete set of executable tools to its clients.30 The core API specification for the vocabulary tool mimics a standard semantic search interface, prioritizing rapid keyword resolution. Full SPARQL compatibility is unnecessary computational overhead for local offline clients and will not be implemented.  
The MCP server handles initialization requests, provides a list of available tools, and executes JSON-RPC calls formatted to MCP specifications.31 During HOARD Phase 1, the AI pipeline extracts raw, free-text material identifiers from Optical Character Recognition (OCR) processed context sheets. Currently, HOARD stores these idiosyncratic strings verbatim. With the MCP vocabulary service integrated, HOARD acts as an MCP Client. When the LLM extracts the term "flint," it invokes the exposed search\_vocabulary MCP tool. The server executes a highly optimized SQLite Full-Text Search (FTS5) query and returns the standardized entity object. HOARD then embeds the precise URI (e.g., Flint/Chert (AAT: 300011754)) directly into the contexts.json shared data model, ensuring downstream topological and spatial analyses operate on normalized strings.

### **Period Thesauri and Material Hierarchies**

Handling archaeological periods presents a distinct data modeling challenge compared to material classes. Periods are intrinsically hierarchical and strictly geographically bound; the transition from the Bronze Age to the Iron Age occurs at radically different temporal bounds in the Mediterranean basin compared to Northern Europe.  
To accommodate this ontological complexity, the Cache & Carry SQLite schema will model period data utilizing the Simple Knowledge Organization System (SKOS) ontology parameters.35 The JSON-RPC response for a period query will be enriched to include geographic bounding box data or standard regional codes.  
Concurrently, the vocabulary service will absorb unit normalisation responsibilities. A dedicated MCP tool (normalize\_units) will be exposed. When HOARD parses "15cm" or "1/2 inch" from a context sheet, the client queries the normalisation tool, which utilizes algorithmic conversion to standardize all lengths to meters (e.g., 0.15m) and all weights to grams within the resulting JSON structures. This entirely eliminates the maintenance burden of hardcoded regex parsers duplicated across the sibling projects.

### **Deliverables for Question 3**

**1\. Recommendation:** Refactor the Cache & Carry SQLite engine into a standalone MCP server communicating exclusively via stdio. Expose minimal JSON-RPC tools for vocabulary search, SKOS-compliant period resolution, and unit normalisation. Utilize the official Python and Rust MCP SDKs within client applications (HOARD, Trowel) to invoke these standardizing tools during data ingestion and synthesis.  
**2\. Architecture Diagram:**

Code snippet  
sequenceDiagram  
    participant LLM as HOARD AI Pipeline (Client)  
    participant SDK as Python MCP SDK  
    participant SubProcess as stdio Pipe  
    participant Server as Cache & Carry (MCP Server)  
    participant SQLite as Local Getty Database

    LLM-\>\>SDK: Tool call: search\_vocabulary(term="flint")  
    SDK-\>\>SubProcess: JSON-RPC 2.0 Request  
    SubProcess-\>\>Server: Route Request  
    Server-\>\>SQLite: FTS5 Query  
    SQLite--\>\>Server: Result Row  
    Server--\>\>SubProcess: JSON-RPC Response  
    SubProcess--\>\>SDK: Parse payload  
    SDK--\>\>LLM: {"id": "AAT:300011754", "label": "Flint/Chert"}

**3\. Concrete Implementation Plan:**

1. In the Cache & Carry Rust repository, integrate the rmcp and mcp-rs crates.31  
2. Implement the MCP server logic within src/bin/mcp\_server.rs, configuring the stdio transport layer and registering the search\_vocabulary and normalize\_units tools.  
3. In the HOARD Python project, install the mcp SDK package.27  
4. Modify HOARD Phase 1 to instantiate the Cache & Carry binary as an MCP client subprocess during initialization.  
5. Inject the MCP tool definitions into the Ollama system prompt, allowing the LLM to autonomously trigger normalisation queries during OCR extraction.28

**4\. Schema Fragments:**  
The MCP tool definition exposed by the server to the client:

JSON  
{  
  "name": "search\_vocabulary",  
  "description": "Queries the offline Getty vocabulary database for material or object standardization.",  
  "inputSchema": {  
    "type": "object",  
    "properties": {  
      "term": { "type": "string", "description": "The raw string to search." },  
      "vocabulary": {   
        "type": "string",   
        "enum":   
      },  
      "limit": { "type": "integer", "default": 5 }  
    },  
    "required": \["term", "vocabulary"\]  
  }  
}

**5\. Migration Path:**  
Trowel's existing vocab\_terms.py module, which currently connects directly to the SQLite database, will be refactored to utilize the MCP Python SDK. HOARD will incrementally adopt the MCP server; initially utilizing it as a deterministic post-processing step on the JSON data, before transitioning to full, autonomous LLM tool-calling once the stdio pipeline latency is profiled and optimized.  
**6\. Risk Assessment:** The primary risk encountered in this phase concerns asynchronous request blocking. Communicating with a subprocess over stdio streams can cause the host application to hang if the MCP server fails to flush its output buffers or encounters a deadlock during complex SQLite queries. To mitigate this, the client-side implementation utilizing the Python and Rust MCP SDKs must enforce strict, non-blocking asynchronous timeouts.31 If the Cache & Carry server fails to respond within 500 milliseconds, the client will abort the tool call, fall back to utilizing the raw, un-normalized string, and log a timeout warning. This ensures the primary data extraction pipeline is never permanently stalled by a secondary normalisation process.

## **Cross-Project CLI Command Design**

The usability of the heritage science ecosystem relies heavily on a cohesive command-line interface. Requiring field archaeologists or specialists to install and memorize disparate CLI paradigms and argument structures across independent tools (hoard run, trowel open, stratigraph import) creates unnecessary cognitive friction and impedes adoption. Abstracting these operations into a unified interface is a critical usability requirement.

### **Python Meta-Package and Entry Points Architecture**

To preserve the autonomy of the individual projects while providing a unified user experience, the architecture relies on a Python meta-package utilizing the standard entry\_points specification.36 Rather than compiling the ecosystem into a massive monolithic binary, a new lightweight repository, heritage-cli, will act as an intelligent routing wrapper.  
This meta-package utilizes the console\_scripts directive defined within its pyproject.toml.36 When heritage-cli is installed via standard Python package managers (e.g., pip or uv), the installer generates a global executable named heritage.  
For the underlying CLI framework, Typer is selected over Click. While Click provides low-level customization, Typer leverages Pydantic for automatic type-hint parsing, generates help documentation dynamically, and drastically reduces boilerplate code, aligning seamlessly with the ecosystem's existing Python tools.38 The Typer application constructs a nested command tree that intercepts user commands and maps them to the respective sub-project executables:

| Unified Command | Discovered Subprocess Execution |
| :---- | :---- |
| heritage run \--project X \--phase 1 | hoard run \--project X \--phase 1 (Unchanged routing) |
| heritage calibrate \--project X | libby \--workspace X (Invokes the Libby binary) |
| heritage lithics \--project X | dibble process \--input X (Executes Dibble module) |
| heritage review \--project X | trowel open \--project X (Launches PyQt6 desktop GUI) |
| heritage matrix \--project X | stratigraph import \--data X (Launches Tauri application) |

### **Plugin Discoverability**

The meta-package will not enforce strict installation dependencies on all ecosystem tools; a user analyzing stable isotopic data has no need to install the GPR processing tool (DIG). Therefore, the CLI requires a dynamic plugin architecture.  
Utilizing Python's importlib.metadata.entry\_points 36, the heritage CLI dynamically probes the host environment's $PATH and local site-packages upon invocation. A dedicated command, heritage tools list, will invoke this probe. Utilizing the Rich Python library for advanced terminal formatting 39, the CLI outputs a styled table detailing which sibling executables are currently installed, their version parity, and their operational status. If a user executes heritage calibrate without Libby installed, the Typer router gracefully catches the missing entry point and provides instructions for installing the required dependency.

### **Centralized Configuration Management**

Cross-project parameterization must be centralized. Dispersing isolated .yaml or .json configuration files across multiple hidden application directories violates clean system design. The ecosystem will converge on a single config.toml file, located deterministically using the platformdirs library.16  
The path resolves cleanly according to XDG specifications 18:

* **Linux/macOS:** \~/.config/heritage/config.toml (or $XDG\_CONFIG\_HOME/heritage/config.toml)  
* **Windows:** %APPDATA%\\heritage\\config.toml

This file contains global parameters (e.g., default LLM endpoints, path to the offline Cache & Carry SQLite database, default jurisdiction templates) alongside project-specific namespaces (e.g., \[tools.hoard\], \[tools.libby\]). Upon execution, the heritage CLI parses this configuration file and injects the variables directly into the underlying subprocess environments via standard OS environment variables (e.g., HERITAGE\_DEFAULT\_JURISDICTION="Wessex"). This guarantees a unified, immutable execution context regardless of which ecosystem tool is actively performing operations.

### **Deliverables for Question 4**

**1\. Recommendation:** Implement heritage-cli as a standalone Python meta-package utilizing Typer. Leverage importlib.metadata.entry\_points for dynamic tool discovery without enforcing strict dependencies. Centralize configuration within a single XDG-compliant config.toml file, injecting parameters into subprocesses via environment variables.  
**2\. Architecture Diagram:**

Code snippet  
graph TD  
    A \--\>|Type: heritage calibrate| B  
    B \--\>|Parse config.toml| C{Environment Variables}  
    B \--\>|importlib Probe| D{Is 'libby' installed?}  
      
    D \--\>|Yes| E\[Execute: subprocess.run('libby \--workspace')\]  
    D \--\>|No| F  
      
    E \--\> C  
    E \--\>|Write Data| G

**3\. Concrete Implementation Plan:**

1. Create the heritage-cli repository and initialize a pyproject.toml file defining the console\_scripts entry point.37  
2. Develop the main.py utilizing the typer and rich libraries to construct the foundational command tree (e.g., run, review, matrix, tools list).39  
3. Implement the configuration parsing module utilizing platformdirs and tomllib (built-in for Python 3.11+) to locate and ingest config.toml.  
4. Implement the dynamic subprocess routing logic, mapping unified arguments to the specific flags expected by the sibling binaries.  
5. Update the documentation of all sibling projects to reflect the unified CLI as the primary interaction method, while maintaining instructions for isolated execution.

**4\. Schema Fragments:**  
The pyproject.toml fragment defining the meta-package entry point:

Ini, TOML  
\[build-system\]  
requires \= \["flit\_core\<4"\]  
build-backend \= "flit\_core.buildapi"

\[project\]  
name \= "heritage-cli"  
version \= "1.0.0"  
description \= "Unified CLI router for the heritage science open-source ecosystem"  
requires-python \= "\>=3.11"  
dependencies \= \[  
    "typer\>=0.9.0",  
    "rich\>=13.0.0",  
    "platformdirs\>=4.0.0"  
\]

\[project.scripts\]  
heritage \= "heritage\_cli.main:app"

**5\. Migration Path:**  
The deployment of heritage-cli acts as an overlay. Because the sibling projects remain untouched as independent binaries, the introduction of the meta-package is completely non-destructive. Users who prefer to invoke hoard run directly may continue to do so indefinitely. Over time, as the orchestration capabilities of heritage run become more sophisticated, users will naturally migrate to the unified interface for ease of use.  
**6\. Risk Assessment:**  
A prominent risk with meta-CLI routing involves the obfuscation of subprocess error logs. If heritage lithics invokes Dibble, and Dibble crashes with a deeply nested Python traceback or Rust panic, the Typer router might truncate or swallow the stderr stream, making it impossible for the user to debug the underlying analytical failure. To mitigate this, the subprocess invocation logic must be engineered to explicitly pass through standard output and standard error streams seamlessly to the parent terminal without buffering. For fatal subprocess exits, the router will dump a complete crash\_report.log into the XDG workspace directory, ensuring diagnostic fidelity is preserved.

## **Conclusion**

The structural unification of the HOARD ecosystem represents a necessary evolution from a suite of disparate analytical utilities into a highly cohesive, robust heritage science platform. By establishing a language-agnostic data model governed by TypeSpec and JSON Schema Draft 2020-12, the architecture entirely neutralizes schema drift while facilitating zero-cost native type generation across Python, Rust, and TypeScript. File-based Inter-Process Communication within strictly defined XDG workspace directories ensures the ecosystem remains entirely offline, satisfying the fundamental operational constraints of remote archaeological deployments.  
The introduction of a choreography-based saga orchestration engine, managed through a unified heritage Python meta-CLI, dramatically reduces user friction. This permits the seamless, idempotent end-to-end processing of complex field data without manual intervention. Furthermore, isolating the Cache & Carry SQLite database as an MCP server operating over local standard input/output provides an immensely powerful, AI-compatible vocabulary normalizer without incurring any network overhead or firewall complications.  
Executing this comprehensive architectural blueprint definitively addresses the systemic integration gaps. It transforms a collection of independent applications into a scalable, resilient, and standardized open-source ecosystem, fundamentally enhancing the efficiency and rigorousness of archaeological data synthesis and compliance reporting.

#### **Works cited**

1. typespec.io, accessed June 8, 2026, [https://typespec.io/](https://typespec.io/)  
2. How to create OpenAPI and SDKs with TypeSpec \- Speakeasy, accessed June 8, 2026, [https://www.speakeasy.com/openapi/frameworks/typespec](https://www.speakeasy.com/openapi/frameworks/typespec)  
3. Is anyone using typespec since 1.0 release? "Accidental rant" : r/typescript \- Reddit, accessed June 8, 2026, [https://www.reddit.com/r/typescript/comments/1m7zi9m/is\_anyone\_using\_typespec\_since\_10\_release/](https://www.reddit.com/r/typescript/comments/1m7zi9m/is_anyone_using_typespec_since_10_release/)  
4. SEP-1613: Establish JSON Schema 2020-12 as Default Dialect for MCP \- GitHub, accessed June 8, 2026, [https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1613](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1613)  
5. datamodel-code-generator | Pydantic Docs, accessed June 8, 2026, [https://pydantic.dev/docs/validation/latest/integrations/dev-tools/datamodel\_code\_generator/](https://pydantic.dev/docs/validation/latest/integrations/dev-tools/datamodel_code_generator/)  
6. GitHub \- koxudaxi/datamodel-code-generator: Python data model generator (Pydantic, dataclasses, TypedDict, msgspec) from OpenAPI, JSON Schema, GraphQL, and raw data (JSON/YAML/CSV)., accessed June 8, 2026, [https://github.com/koxudaxi/datamodel-code-generator](https://github.com/koxudaxi/datamodel-code-generator)  
7. datamodel-code-generator \- PyPI, accessed June 8, 2026, [https://pypi.org/project/datamodel-code-generator/0.33.0/](https://pypi.org/project/datamodel-code-generator/0.33.0/)  
8. GitHub \- oxidecomputer/typify: compiler from JSON Schema into idiomatic Rust types, accessed June 8, 2026, [https://github.com/oxidecomputer/typify](https://github.com/oxidecomputer/typify)  
9. Jusduil/rust-typify: JSON Schema \-\> Rust type converter \- GitHub, accessed June 8, 2026, [https://github.com/Jusduil/rust-typify](https://github.com/Jusduil/rust-typify)  
10. typify \- Rust \- Docs.rs, accessed June 8, 2026, [https://docs.rs/typify](https://docs.rs/typify)  
11. Harris Matrix Data Package \- IOSA.it, accessed June 8, 2026, [https://www.iosa.it/specs/harris-matrix-data-package/](https://www.iosa.it/specs/harris-matrix-data-package/)  
12. Harris Matrix Data Package: version 2022 of the hmdp tool with new features for the creation of stratigraphy data packages \- ArcheoFOSS, accessed June 8, 2026, [https://www.archeofoss.org/2022/abstracts/archaeological-stratigraphy/costa](https://www.archeofoss.org/2022/abstracts/archaeological-stratigraphy/costa)  
13. 34.1 \- ARCHEOLOGIA E CALCOLATORI, accessed June 8, 2026, [https://www.archcalc.cnr.it/indice/issues/AC\_34.1.pdf](https://www.archcalc.cnr.it/indice/issues/AC_34.1.pdf)  
14. The Matrix: Connecting Time and Space in archaeological stratigraphic records and archives, accessed June 8, 2026, [https://intarch.ac.uk/journal/issue55/8/ia.55.8.pdf](https://intarch.ac.uk/journal/issue55/8/ia.55.8.pdf)  
15. Stratigraphic Units beyond Archaeological Contexts \- IRIS CNR, accessed June 8, 2026, [https://iris.cnr.it/bitstream/20.500.14243/536635/1/gch20241263.pdf](https://iris.cnr.it/bitstream/20.500.14243/536635/1/gch20241263.pdf)  
16. Python: Getting AppData folder in a cross-platform way \- Stack Overflow, accessed June 8, 2026, [https://stackoverflow.com/questions/19078969/python-getting-appdata-folder-in-a-cross-platform-way](https://stackoverflow.com/questions/19078969/python-getting-appdata-folder-in-a-cross-platform-way)  
17. Suggestions for improvements · Issue \#4841 · kuzudb/kuzu \- GitHub, accessed June 8, 2026, [https://github.com/kuzudb/kuzu/issues/4841](https://github.com/kuzudb/kuzu/issues/4841)  
18. macOS dotfiles should not go in \~/Library/Application Support \- rebecca®, accessed June 8, 2026, [https://becca.ooo/blog/macos-dotfiles/](https://becca.ooo/blog/macos-dotfiles/)  
19. datamodel-code-generator \- GitHub Pages, accessed June 8, 2026, [https://koxudaxi.github.io/datamodel-code-generator/](https://koxudaxi.github.io/datamodel-code-generator/)  
20. Data Pipeline Orchestration Tools: Top 6 Solutions in 2026 \- Dagster, accessed June 8, 2026, [https://dagster.io/learn/data-pipeline-orchestration-tools](https://dagster.io/learn/data-pipeline-orchestration-tools)  
21. ETL orchestration using the Amazon Redshift Data API and AWS Step Functions with AWS SDK integration | AWS Big Data Blog, accessed June 8, 2026, [https://aws.amazon.com/blogs/big-data/etl-orchestration-using-the-amazon-redshift-data-api-and-aws-step-functions-with-aws-sdk-integration/](https://aws.amazon.com/blogs/big-data/etl-orchestration-using-the-amazon-redshift-data-api-and-aws-step-functions-with-aws-sdk-integration/)  
22. How to Test Step Functions State Machine Locally \- Cevo, accessed June 8, 2026, [https://cevo.com.au/post/how-to-test-step-functions-state-machine-locally/](https://cevo.com.au/post/how-to-test-step-functions-state-machine-locally/)  
23. Pattern: Saga \- Microservices.io, accessed June 8, 2026, [https://microservices.io/patterns/data/saga.html](https://microservices.io/patterns/data/saga.html)  
24. The Matrix: Using Archaeological Stratigraphic Data | Historic England, accessed June 8, 2026, [https://historicengland.org.uk/whats-new/research/back-issues/the-matrix-using-archaeological-stratigraphic-data/](https://historicengland.org.uk/whats-new/research/back-issues/the-matrix-using-archaeological-stratigraphic-data/)  
25. The official TypeScript SDK for Model Context Protocol servers and clients \- GitHub, accessed June 8, 2026, [https://github.com/modelcontextprotocol/typescript-sdk](https://github.com/modelcontextprotocol/typescript-sdk)  
26. mcp-proxy-tool \- crates.io: Rust Package Registry, accessed June 8, 2026, [https://crates.io/crates/mcp-proxy-tool](https://crates.io/crates/mcp-proxy-tool)  
27. modelcontextprotocol/python-sdk: The official Python SDK for Model Context Protocol servers and clients \- GitHub, accessed June 8, 2026, [https://github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)  
28. What is the Model Context Protocol (MCP)? \- Databricks, accessed June 8, 2026, [https://www.databricks.com/blog/what-is-model-context-protocol](https://www.databricks.com/blog/what-is-model-context-protocol)  
29. Resources \- Model Context Protocol, accessed June 8, 2026, [https://modelcontextprotocol.io/specification/2025-06-18/server/resources](https://modelcontextprotocol.io/specification/2025-06-18/server/resources)  
30. Architecture overview \- Model Context Protocol, accessed June 8, 2026, [https://modelcontextprotocol.io/docs/learn/architecture](https://modelcontextprotocol.io/docs/learn/architecture)  
31. MCP Server Stdio in Rust: Making Documentation Accessible to AI | by Carlo C. | Medium, accessed June 8, 2026, [https://autognosi.medium.com/mcp-server-stdio-in-rust-making-documentation-accessible-to-ai-5f42c717742f](https://autognosi.medium.com/mcp-server-stdio-in-rust-making-documentation-accessible-to-ai-5f42c717742f)  
32. Announcing mcp-protocol-sdk: A New Rust SDK for AI Tool Calling (Model Context Protocol), accessed June 8, 2026, [https://www.reddit.com/r/rust/comments/1lepymv/announcing\_mcpprotocolsdk\_a\_new\_rust\_sdk\_for\_ai/](https://www.reddit.com/r/rust/comments/1lepymv/announcing_mcpprotocolsdk_a_new_rust_sdk_for_ai/)  
33. What Is the Model Context Protocol (MCP) and How It Works \- Descope, accessed June 8, 2026, [https://www.descope.com/learn/post/mcp](https://www.descope.com/learn/post/mcp)  
34. What is Model Context Protocol (MCP)? A guide | Google Cloud, accessed June 8, 2026, [https://cloud.google.com/discover/what-is-model-context-protocol](https://cloud.google.com/discover/what-is-model-context-protocol)  
35. A metadata schema for documenting material samples from multiple domains \- Semantic Web Journal, accessed June 8, 2026, [https://www.semantic-web-journal.net/system/files/swj3785.pdf](https://www.semantic-web-journal.net/system/files/swj3785.pdf)  
36. Entry points specification \- Python Packaging User Guide, accessed June 8, 2026, [https://packaging.python.org/specifications/entry-points/](https://packaging.python.org/specifications/entry-points/)  
37. Packaging Entry Points — Click Documentation (8.4.x), accessed June 8, 2026, [https://click.palletsprojects.com/en/stable/entry-points/](https://click.palletsprojects.com/en/stable/entry-points/)  
38. \[FEATURE\] Adding Typer to custom package using entry points · Issue \#34 \- GitHub, accessed June 8, 2026, [https://github.com/fastapi/typer/issues/34](https://github.com/fastapi/typer/issues/34)  
39. How to Build CLI Applications with Click and Typer \- OneUptime, accessed June 8, 2026, [https://oneuptime.com/blog/post/2025-07-02-python-cli-click-typer/view](https://oneuptime.com/blog/post/2025-07-02-python-cli-click-typer/view)  
40. Python & Beyond — 5 \- Kevin Tewouda \- Medium, accessed June 8, 2026, [https://lewoudar.medium.com/python-beyond-5-0bd129410645](https://lewoudar.medium.com/python-beyond-5-0bd129410645)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAZCAYAAABQDyyRAAABIUlEQVR4Xu2VsUsCYRjGX6HJCoQQxEbHHBqaahYahUAQJAt0EhpdwlWh/oGm2tocglqaW6JoCpccpUb/gAZ7Xt5DXh/SHL5ukPvBjzue9+PuuY/jTmRFyMISh449DkKzBY85jDiDbxyGZl6BHOzDLg9CM6/ANSzAHg8WkYYtOILn8BBuwwp8h1X4OV1taIE6ZQ9wMzpfuoC2HcBvuE4z5QBOIj2/FfA7slSBIvwSu3iDZp5XsYIeLXBCWcf5FB13ZlYQuq1680seELfwnjItcEqZ54YDZlfs5m0exMWFWIE8D+LiDn5wGCfPYh+Mv9D341926QiO4QYPHC9wn8NQrIm9A1cwRTNFfzZNDkPzKFZCn7QGM7AsVmro1iUkJCSsFj+RHS4X+W+IewAAAABJRU5ErkJggg==>