# **Architectural Viability of Graphical Interfaces for the HOARD Heritage Pipeline**

The core tension impeding the broader adoption of the Heritage Observation And Report Drafter (HOARD) is the structural conflict between its headless, programmatic Command Line Interface (CLI) architecture and the operational realities of its target demographic: commercial field archaeologists who rely exclusively on graphical interfaces and lack the technical proficiency to manage Python environments. Exhaustive analysis indicates that developing a net-new graphical user interface or web wrapper introduces an unsustainable maintenance burden for a solo developer and fractures the ecosystem. The single most important finding of this investigation is that embedding HOARD as a processing engine within the existing PyQt6-based Trowel application offers the lowest marginal cost, permanently resolves the installation bootstrapping paradox via pre-existing binary bundling, and consolidates the heritage science ecosystem into a unified, accessible workspace.

## **The Operating Environment of the Commercial Archaeologist**

To establish an effective intervention strategy, it is necessary to critically analyze the operational context of the target persona and the technical hurdles that currently prevent adoption. The HOARD application operates within a highly specific, compliance-driven professional niche. It automates the drafting of "grey literature"—the unpublished but vital archaeological reports, such as Cultural Heritage Management Plans (CHMPs), mandated by statutory authorities.1 In jurisdictions such as Victoria, Australia, CHMPs are strictly regulated documents that require significant manual compilation of stratigraphic context sheets, artefact analyses, and geospatial interpretations.3 Commercial field directors and heritage consultants manage these high-stakes compliance documents under strict commercial timeframes, often operating from temporary site offices or directly from the field.  
These professionals possess profound domain expertise and routinely utilize sophisticated spatial software such as QGIS alongside standard commercial CRM suites and complex spreadsheet applications.1 However, their computational environment is almost universally localized to locked-down Windows or macOS machines devoid of integrated development environments, dedicated Python runtimes, or package management utilities.8 This professional cohort exhibits strong terminal avoidance. For this user, the command prompt is not merely an inconvenience; it represents a hard operational barrier. They do not utilize shell scripts, they are unfamiliar with environment variables, and they cannot independently troubleshoot dynamic link library (DLL) pathing errors.  
Consequently, any solution attempting to broaden the reach of the HOARD pipeline must acknowledge that the user is not a developer, nor are they a student willing to invest hours in environment configuration. They manage field teams ranging from two to ten individuals and are incentivized entirely by workflow efficiency and compliance accuracy. The software must accommodate their existing mental models, which revolve around native executable files, double-click initialization, visual progress indicators, and standard drag-and-drop file interactions.

## **The Accessibility Calculus of the Hardware Tier System**

A critical pre-existing lever for accessibility within the HOARD architecture is the automated hardware tier detection system. Heritage professionals frequently operate on lightweight laptops deployed to field sites, which categorically lack the Video Random Access Memory (VRAM) required for localized Large Language Model (LLM) inference. The implementation of the hardware tier system fundamentally alters the adoption viability of the software.  
The application auto-detects hardware on its first run and routes the AI-assisted pipeline accordingly.

| Hardware Tier | Local VRAM Requirement | AI Backend Routing Protocol | Accessibility Impact for Target Persona |
| :---- | :---- | :---- | :---- |
| Ultra-light | 0 GB (CPU only) | Cloud API-driven (OpenAI, Anthropic Claude, Google Gemini) | **Transformative:** Enables full pipeline execution on standard commercial field laptops without specialized hardware. |
| Budget | 6 GB | Hybrid: Local (Compact Ollama models) \+ API failover | Low: Requires a mid-tier gaming laptop, uncommon in standard corporate IT provisioning. |
| Standard | 8–12 GB | Full local pipeline via mid-tier Ollama models | None: Exceeds the specifications of standard commercial hardware deployed in the field. |
| Performance | 16–24 GB | High-end local models | None: Exclusively applicable to dedicated data science workstations. |

By routing inference tasks entirely through cloud providers and bypassing local Ollama instances, the ultra-light tier eliminates the need for expensive GPU hardware. Consequently, the non-technical Windows user is no longer constrained by compute limitations; they are solely constrained by the interface and the installation process. If the accessibility barriers of the CLI can be resolved, the ultra-light tier ensures the application is immediately usable by the entire target demographic. The existence of this tier shifts the engineering priority entirely away from hardware optimization and squarely onto user experience and distribution strategy.

## **The Bootstrapping Paradox and Distribution Mechanics**

The foundational barrier to HOARD adoption is the bootstrapping paradox. The current distribution mechanism, executed via the command pip install hoard-erd, presupposes a functional Python installation, correct PATH configurations, and familiarity with package management.9 A non-technical user who finds a terminal window confronting will invariably fail to execute the installation command, rendering any terminal-based enhancements—such as progressive disclosure wizards or a Textual-based Terminal User Interface (TUI)—operationally moot.  
The installation problem is a distinct barrier from the interface problem, and any successful GUI strategy must inherently solve the distribution problem. A polished interface is useless if the user cannot launch it. To deliver a standalone application, the Python codebase must be bundled into a native executable that encapsulates the Python interpreter and all dependencies.  
However, bundling complex data science applications introduces profound engineering challenges. When utilizing packagers like PyInstaller, libraries that dynamically load their submodules, such as Pandas, must be explicitly declared using the collect\_submodules hook (hiddenimports \= collect\_submodules('pandas.\_libs')) to prevent ImportError exceptions at runtime.10 Furthermore, the hoard-erd package relies heavily on the wand library for ImageMagick bindings to process field photographs and scanned context sheets.9 PyInstaller natively struggles to locate ImageMagick dynamic link libraries (coders and filters) on Windows architectures. The build specification must be manually engineered to extract registry keys or environment variables (MAGICK\_HOME), ensuring the DLLs are packaged into the application's internal directory and the execution path is dynamically updated at runtime.13  
Alternative packagers present different trade-offs. Briefcase, part of the BeeWare project, offers sophisticated native wrappers but enforces strict limitations, such as requiring purely integer-based MSI versioning and disallowing PEP-440 compliant tags like 1.2.3b3.14 The Astral python-build-standalone toolchain provides pre-compiled Python distributions for various architectures but leaves the burden of creating user-friendly launcher scripts to the developer.17 Resolving this packaging complexity is a prerequisite for any GUI solution, heavily penalizing approaches that require the solo developer to construct a new distribution pipeline from scratch.

## **Evaluation Rubric and Ranked Approaches**

The following ranked evaluation scores each architectural pathway based on the constraints of a solo developer managing the ecosystem. The primary weighted criteria are the solo maintenance burden (minimizing codebase divergence and active upkeep), the effort required to reach a Minimum Viable Product (MVP), and the absolute necessity of solving the cold-start bootstrapping paradox. Secondary criteria include mitigating core dependency bloat, maximizing demographic reach, ensuring the security of the credential vault, and leveraging existing tools.

| Rank | Approach | Combined Score | Rationale |
| :---- | :---- | :---- | :---- |
| **1** | **Integration with Existing Desktop Tools (Trowel)** | **Highest** | Delivers the lowest marginal cost by capitalizing on existing PyInstaller distribution, bidirectional JSON Inter-Process Communication (IPC), and shared templates. Solves the cold-start problem flawlessly without requiring a net-new user interface codebase. |
| **2** | **Web-Based Wrapper (FastAPI \+ HTMX)** | **High** | Eliminates complex JavaScript build steps while providing a rich, asynchronous local interface; however, it necessitates a complex PyInstaller configuration to serve a multi-threaded web server as a standalone executable. |
| **3** | **Tauri Desktop Shell (Sidecar)** | **Moderate** | Provides a premium native application feel and handles OS-level installers natively, but introduces a parallel UI codebase and highly complex Rust-to-Python IPC maintenance overhead. |
| **4** | **QGIS Plugin Integration** | **Moderate** | Offers excellent domain alignment for GIS users, but forces dependency on the notoriously fragile QGIS Python environment and alienates users who draft reports outside of spatial software. |
| **5** | **TUI Enhancement (Textual)** | **Low** | Requires the user to open a terminal and successfully execute pip installation commands, fundamentally failing to solve the bootstrapping paradox for the target persona. |
| **6** | **Guided Onboarding / Profiles** | **Low** | Highly useful as a supplementary mechanism for power users, but insufficient as a primary intervention for a demographic that exhibits strict terminal avoidance. |

## **Detailed Write-up: Top Option 1 \- Integration with Trowel (PyQt6)**

The mathematically optimal and strategically superior pathway is the integration of the HOARD pipeline directly into Trowel, an existing premium desktop application within the heritage science ecosystem developed in PyQt6.18 Trowel operates as a digital finishing tool for archaeological data, allowing users to interact with synthetic datasets, context sheets, and spatial data via a familiar desktop GUI.18 Most importantly, Trowel and HOARD already share jurisdiction templates and utilize a proven bidirectional JSON schema for data exchange.18

### **The User Narrative**

From the perspective of the target user—the commercial field archaeologist—the experience is entirely frictionless and devoid of terminal interactions. The user navigates to the project repository and downloads a standard standalone executable (Trowel.exe for Windows or Trowel.dmg for macOS).18 Upon launching the application with a double-click, they are presented with the standard Trowel desktop GUI, which they already use for basic compliance tasks.  
The user imports their context sheets, spatial data, and site photographs into the Trowel workspace. Within the existing interface menu, a new dedicated tab labeled "AI Report Drafting (HOARD)" is prominently available. The user clicks "Initialize Pipeline" and selects their required jurisdiction template from a dropdown menu. If it is their first run, a secure settings dialog prompts them to input their OpenAI or Anthropic API keys. The user then clicks "Run Full Pipeline." The GUI temporarily locks the immediate workspace and displays a detailed, color-coded progress bar for each of the six HOARD phases. When the pipeline flags an item for human review—such as low-confidence OCR on a context sheet or a spatial mismatch—the Rich TUI dashboard components previously used by HOARD are surfaced seamlessly as native PyQt6 modal dialog boxes, allowing the user to Accept, Edit, or Defer the anomaly. Once complete, the publication-ready grey literature report is saved directly to their local directory.

### **Solving the Cold-Start Problem**

This approach entirely circumvents the bootstrapping paradox by hitchhiking on an established distribution vehicle. Trowel is already packaged as a standalone executable using PyInstaller, meaning a Python interpreter does not need to be installed on the host machine.18 Continuous Integration pipelines via GitHub Actions already handle the cross-platform builds (make build-windows, make build-macos).18 By adding hoard-erd to Trowel's dependency manifest, the entire HOARD pipeline is bundled directly into the executable archive. The user never sees a Python installation prompt.

### **Architectural Modifications to HOARD**

To facilitate this integration, specific architectural boundaries within HOARD must be adjusted to serve as a headless engine rather than a master controller.

1. **Subprocess Execution and Threading:** HOARD must be invoked programmatically from within Trowel. Instead of utilizing the heritage-cli wrapper 20, Trowel's PyQt6 QThread workers will import HOARD's core engine modules directly. Running HOARD in a separate worker thread is critical to prevent the heavy AI-inference calculations and file processing from blocking Trowel's main GUI thread, which would result in the application appearing frozen to the user.  
2. **State Management via File-Based IPC:** The existing hoard\_import.py and hoard\_export.py bidirectional JSON scripts 18 will be repurposed as the primary Inter-Process Communication (IPC) mechanism. Trowel will serialize its current .trowel project state to a temporary JSON directory, which HOARD will ingest for Phase 1 processing, adhering strictly to the constraint that the CLI remains the API.  
3. **UI Bridging and Signal Emission:** The terminal-based Rich TUI review dashboard currently used by HOARD must be suppressed when invoked via Trowel. HOARD will require the implementation of a \--gui-mode argument. When this flag is passed, HOARD suppresses standard console output and instead emits structured JSON logs via standard output (stdout). Trowel will consume these JSON logs in real-time, mapping them to PyQt signals to update its native progress bars and populate Qt dialogs for phase reviews.

### **Dependency Impact**

The dependency footprint of hoard-erd will be absorbed entirely into Trowel's build process.18 This prevents the base pip install hoard-erd command from suffering any bloat. However, the Trowel PyInstaller .spec file will require substantial modification to accommodate HOARD's heavy data science dependencies. The developer must implement PyInstaller hooks for Pandas 10 and manually configure the binary collection for Wand and the underlying ImageMagick libraries.12

### **Minimum Viable Product (MVP) Definition**

The MVP for this integration would consist of:

* A single "Run HOARD Pipeline" button within the Trowel interface.  
* Support for the "Ultra-light" cloud-only tier, bypassing the need to bundle local Ollama executables into the initial Trowel distribution.  
* A basic PyQt6 progress bar mapping to the JSON log outputs of the six HOARD phases.  
* A fallback mechanism where flagged review items pause the pipeline and present a simple HTML preview or Qt text box of the anomaly for user intervention.

### **Estimated Effort and Maintenance Risk**

The effort to achieve this MVP is estimated at 2 to 3 developer-weeks. Since the core JSON IPC and shared templates are already functioning and structurally aligned 18, the primary engineering labor involves bridging the HOARD progress emitter to the PyQt6 signal/slot mechanism and stabilizing the PyInstaller build matrix.  
The maintenance risk is remarkably low, fulfilling the critical constraint of solo maintainability. The developer avoids the fragmentation of building a bespoke HOARD wrapper. They maintain one cohesive CLI engine (HOARD) and one cohesive GUI (Trowel), allowing enhancements to the core engine to immediately propagate to the GUI without requiring parallel UI updates.

## **Detailed Write-up: Top Option 2 \- Web-Based Wrapper (FastAPI \+ HTMX)**

If deep integration with Trowel is deemed undesirable due to a desire to maintain strict tool boundary constraints, the secondary optimal approach is deploying a local web server utilizing FastAPI and HTMX. This paradigm leverages hypermedia-driven server-side rendering to provide a responsive, modern interface without the massive overhead of JavaScript build steps (Node.js, Webpack, npm) or the maintenance of separate frontend single-page application codebases like React or Svelte.21

### **The User Narrative**

The user downloads a packaged standalone launcher named HOARD\_Desktop. Upon double-clicking the application, a lightweight ASGI server boots invisibly in the background, and the user's default web browser automatically opens a new tab to http://localhost:8765. The browser displays a clean, intuitive, offline web dashboard. The user securely unlocks their credential vault via a password prompt on the screen. They drag and drop their field records (CSV, Excel, images) directly into the browser window.  
The user clicks a distinct "Start Pipeline" button. Through HTMX, the browser seamlessly polls the local server, dynamically swapping HTML fragments to show real-time progress. As the pipeline progresses, a terminal emulation window built natively in HTML streams the log outputs. When human review is required, a modal overlay appears in the browser, rendering the flagged image or text anomaly and providing buttons to Accept or Defer. Upon completion, the browser provides a secure download link for the generated grey literature reports, ensuring the data never leaves the local machine.

### **Solving the Cold-Start Problem**

Solving the bootstrapping paradox for a web application requires bundling the web server into a standalone executable. This can be achieved using PyInstaller in \--onedir mode.23 The developer must write a master entry-point script that initiates the uvicorn ASGI server on a local port, daemonizes the process, and utilizes Python's native webbrowser.open() module to launch the interface. This ensures the user never touches a terminal; they simply launch an executable that orchestrates the local web environment.

### **Architectural Modifications to HOARD**

1. **FastAPI Routing and Endpoints:** A new module, hoard.serve, must be created. The core CLI commands must be mapped to FastAPI asynchronous endpoint routes. For example, a POST /api/run-phase-1 endpoint will asynchronously execute the equivalent of hoard run phase1 via the internal Python API.  
2. **HTMX Integration:** The fastapi-htmx package 25 can be utilized to streamline the architecture. By using decorators (e.g., @htmx("index")), the endpoints can directly render and return Jinja2 HTML templates rather than JSON payloads.21 This allows HTMX attributes like hx-post and hx-swap="outerHTML" on the client side to dynamically update the UI without writing custom JavaScript logic.21  
3. **Server-Sent Events (SSE) for Progress Emulation:** Real-time terminal output and progress bars must be streamed to the browser to replicate the CLI experience. This requires implementing Server-Sent Events within FastAPI. HTMX natively supports this via the hx-ext="sse" extension, allowing the browser to subscribe to a continuous stream of pipeline logs without relying on resource-intensive JavaScript polling loops.26

### **Dependency Impact**

This approach introduces fastapi, uvicorn, jinja2, python-multipart, and fastapi-htmx as core dependencies for the web wrapper.21 To preserve HOARD's minimal core footprint, these web-specific libraries must be strictly isolated as optional extras in the pyproject.toml file, installable only via pip install hoard\[web\]. The base CLI installation must remain unaffected.

### **Minimum Viable Product (MVP) Definition**

The MVP for the FastAPI/HTMX wrapper would consist of:

* A basic PyInstaller executable that launches Uvicorn and opens the browser.  
* A single-page HTML interface containing a configuration form for hardware tiers and file upload inputs.  
* FastAPI routes covering the execution of all six phases sequentially.  
* A rudimentary SSE stream that dumps the raw HOARD terminal output into a scrolling \<pre\> tag in the browser, providing visibility into the pipeline's status.

### **Estimated Effort and Maintenance Risk**

The MVP requires approximately 4 to 5 developer-weeks. Designing an accessible, responsive web interface using standard CSS, establishing reliable SSE streams for the terminal emulation, and wrestling with PyInstaller to successfully bundle a multi-threaded ASGI server alongside HOARD's existing heavy data science dependencies presents a moderate to high engineering challenge.  
The maintenance risk is classified as medium. While the HTMX approach brilliantly eliminates frontend JavaScript toolchain rot and avoids the complexities of a detached Svelte/React repository, the solo developer must still maintain a parallel suite of HTML/Jinja2 templates that mirror the functionality of the CLI. Any new feature added to the CLI must be manually integrated into the web routing and HTML interface, creating a persistent dual-maintenance tax.

## **Evaluation of Remaining Options**

### **Tauri Desktop Shell (Sidecar Integration)**

Tauri leverages a Rust backend and a web frontend to create highly performant, lightweight native desktop applications.27 Given the developer's existing experience with Tauri in the ecosystem (StratiGraph, Cache & Carry), wrapping HOARD as a Tauri application is theoretically attractive. The implementation would utilize Tauri's "sidecar" architecture, which allows external binaries (like a PyInstaller-compiled HOARD CLI executable) to be bundled directly into the application archive and executed via the Rust Command API.28 This provides an unparalleled native UX and solves the cold-start problem flawlessly via standard operating system installers (.msi, .dmg).31 However, it ranks lower due to the immense maintenance burden. The developer would be tasked with maintaining a complex Rust/Svelte UI codebase that duplicates the entire logic of the CLI. Furthermore, the sidecar payload mapping—ensuring Python binaries exist for all $TARGET\_TRIPLE architectures, such as x86\_64-pc-windows-msvc and aarch64-apple-darwin 28—introduces significant continuous integration bloat and cross-compilation overhead for a solo maintainer.

### **QGIS Plugin Integration**

Given that the target demographic relies heavily on QGIS for spatial data management and site map generation, embedding HOARD directly into the GIS environment presents profound domain synergy.7 QGIS includes a robust internal Python environment and a processing framework (qgis\_process) capable of running standalone algorithms.33 A custom plugin could present a native PyQt UI panel within the QGIS workspace, allowing users to select spatial layers and push them directly into the HOARD pipeline.34 However, this approach is severely handicapped by distribution complexities. QGIS tightly controls its internal Python environment; injecting external libraries with compiled C-extensions (like Pandas, OpenCV, or ImageMagick bindings) into the QGIS runtime frequently results in unresolvable dependency conflicts across different OS installations. More critically, this approach inherently alienates a significant subset of the target persona—those heritage consultants who draft reports using proprietary CRM software or standard CAD tools, rather than dedicated spatial software.

### **TUI Enhancement (Textual)**

Expanding the existing Rich-based terminal interface into a full-scale Terminal User Interface utilizing the Textual framework would theoretically provide an excellent, mouse-navigable dashboard within the terminal window. It would allow for interactive file pickers, visual project trees, and one-click phase execution without adding the bloat of a local web framework. However, this approach explicitly fails the primary constraint of the evaluation rubric: the cold-start paradox. A highly polished, asynchronous TUI remains fundamentally inaccessible if the user is intimidated by the prospect of opening the Windows Command Prompt and lacks the environment variables required to execute pip install hoard\[tui\]. For the target persona, the terminal window itself is the psychological and technical barrier, not merely the text inside it.

### **Configuration Profiles and Guided Onboarding**

Developing an interactive hoard wizard and establishing configuration profiles (hoard init \--quick) reduces cognitive load by utilizing smart defaults, executing automated dependency checks (hoard doctor), and bypassing complex argument flags. These features represent excellent software engineering hygiene and should be implemented as a baseline improvement to the core CLI architecture regardless of GUI development. However, they function strictly as secondary optimizations. As standalone solutions, they do not resolve the terminal avoidance of the target user base and do not constitute an alternative to a graphical interface. A non-technical user is unlikely to successfully execute hoard wizard if they cannot install the package in the first instance.

## **Cryptographic Security and the Credential Vault**

The HOARD pipeline requires the management of highly sensitive API keys (OpenAI, Anthropic) for cloud routing in the ultra-light and budget hardware tiers. Currently, these credentials are secured via an AES-256-GCM encrypted vault utilizing PBKDF2 key derivation. Expanding the interface to serve non-technical users introduces novel attack surfaces that must be rigorously secured.  
If the Trowel integration (Top Option 1\) is selected, memory safety is generally preserved, as the PyQt6 application operates entirely within the local user's operating system permission boundary. The master password can be stored securely in the native system keychain (Windows Credential Manager or macOS Keychain) and injected into the subprocess environment variables temporarily, ensuring the keys are never written to disk in plain text.  
If the FastAPI web wrapper (Top Option 2\) is selected, security protocols must be strictly enforced to prevent local network exploitation. The ASGI web server must be explicitly configured to bind exclusively to the loopback interface (127.0.0.1 or localhost), decisively denying external network traffic (0.0.0.0). The master password used to decrypt the vault must not be stored in browser cookies or localStorage. Instead, an ephemeral session token generated upon local browser unlock should facilitate decryption in memory on the server side, ensuring that if the browser context is compromised, the at-rest AES-encrypted vault remains cryptographically secure.

## **Supplementary Documentation Requirements**

To maximize the efficacy of the top-ranked solution (Trowel Integration), the software release must be accompanied by highly targeted, domain-specific documentation tailored exclusively to the commercial archaeologist. The documentation must aggressively avoid software development terminology, functioning instead as a workflow integration guide.  
The accompanying collateral must include:

1. **A Visual Quickstart Guide:** A step-by-step PDF or web page demonstrating the exact UI flow from loading a raw context sheet CSV to generating the final Microsoft Word (.docx) grey literature report within the Trowel interface.  
2. **A "No-Code" Guarantee Statement:** Prominent messaging assuring users that the installation and execution of the application require no programming knowledge, API configuration (beyond copy-pasting an OpenAI/Anthropic key into a settings box), or terminal access whatsoever.  
3. **Jurisdiction Template Mapping:** A clear visual map demonstrating how the user's specific state or regional guidelines (e.g., Heritage Victoria formatting requirements for Cultural Heritage Management Plans) are automatically applied by the HOARD engine within the Trowel interface, ensuring immediate compliance utility.  
4. **Hardware Tier Explanation:** A non-technical summary explaining the ultra-light tier, ensuring users understand they can utilize the advanced AI features on standard corporate laptops without requiring expensive GPU hardware.

#### **Works cited**

1. ACKNOWLEDGEMENT OF PLACES WITH SHARED HERITAGE VALUES, accessed June 14, 2026, [https://assets.heritagecouncil.vic.gov.au/assets/SharedValues-AnnotatedBibliography.pdf](https://assets.heritagecouncil.vic.gov.au/assets/SharedValues-AnnotatedBibliography.pdf)  
2. Submission Cover Sheet \- ACT Legislative Assembly, accessed June 14, 2026, [https://www.parliament.act.gov.au/\_\_data/assets/pdf\_file/0020/2204435/Submission-025-Australasian-Society-for-Historical-Archaeology.pdf](https://www.parliament.act.gov.au/__data/assets/pdf_file/0020/2204435/Submission-025-Australasian-Society-for-Historical-Archaeology.pdf)  
3. Cultural heritage management plan process | firstpeoplesrelations.vic.gov.au, accessed June 14, 2026, [https://www.firstpeoplesrelations.vic.gov.au/processes-protect-aboriginal-cultural-heritage-victoria/cultural-heritage-management-plan-process](https://www.firstpeoplesrelations.vic.gov.au/processes-protect-aboriginal-cultural-heritage-victoria/cultural-heritage-management-plan-process)  
4. Cultural Heritage Management Plans | firstpeoplesrelations.vic.gov.au, accessed June 14, 2026, [https://www.firstpeoplesrelations.vic.gov.au/cultural-heritage-management-plans](https://www.firstpeoplesrelations.vic.gov.au/cultural-heritage-management-plans)  
5. CULTURAL HERITAGE MANAGEMENT PLAN DECLARATION \- Glenelg Shire Council, accessed June 14, 2026, [https://www.glenelg.vic.gov.au/files/assets/public/our-services/planning-and-building/planning-documents/cultural-heritage-management-plan-form-updated-sept-2022.pdf](https://www.glenelg.vic.gov.au/files/assets/public/our-services/planning-and-building/planning-documents/cultural-heritage-management-plan-form-updated-sept-2022.pdf)  
6. Vic Heritage CHMP template \- Knox City Council, accessed June 14, 2026, [https://www.knox.vic.gov.au/sites/default/files/2024-11/Advertising%20documents%20-%20CHMP%20March%202020%20original%20application%20-%201161%20Burwood%20Highway%20Upper%20Ferntree%20Gully%20-%20P%202020%206347.pdf](https://www.knox.vic.gov.au/sites/default/files/2024-11/Advertising%20documents%20-%20CHMP%20March%202020%20original%20application%20-%201161%20Burwood%20Highway%20Upper%20Ferntree%20Gully%20-%20P%202020%206347.pdf)  
7. 25.3. QGIS Python console, accessed June 14, 2026, [https://docs.qgis.org/latest/en/docs/user\_manual/plugins/python\_console.html](https://docs.qgis.org/latest/en/docs/user_manual/plugins/python_console.html)  
8. My "Linux-like" MacOS Setup \- heywoodlh, accessed June 14, 2026, [https://heywoodlh.io/linux-macos-setup](https://heywoodlh.io/linux-macos-setup)  
9. hoard-erd \- piwheels, accessed June 14, 2026, [https://www.piwheels.org/project/hoard-erd/](https://www.piwheels.org/project/hoard-erd/)  
10. PyInstaller with Pandas — Problems, solutions, and workflow with code examples \- Medium, accessed June 14, 2026, [https://medium.com/@lironsoffer/pyinstaller-with-pandas-problems-solutions-and-workflow-with-code-examples-c72973e1e23f](https://medium.com/@lironsoffer/pyinstaller-with-pandas-problems-solutions-and-workflow-with-code-examples-c72973e1e23f)  
11. Access list of imported modules from collect\_submodules in hiddenimports from PyInstaller, accessed June 14, 2026, [https://stackoverflow.com/questions/64287326/access-list-of-imported-modules-from-collect-submodules-in-hiddenimports-from-py](https://stackoverflow.com/questions/64287326/access-list-of-imported-modules-from-collect-submodules-in-hiddenimports-from-py)  
12. Integrate ImageMagick with your application : r/learnpython \- Reddit, accessed June 14, 2026, [https://www.reddit.com/r/learnpython/comments/gnhyd3/integrate\_imagemagick\_with\_your\_application/](https://www.reddit.com/r/learnpython/comments/gnhyd3/integrate_imagemagick_with_your_application/)  
13. python \- PyInstaller \+ Wand (ImageMagick) \- missing dependencies \- Stack Overflow, accessed June 14, 2026, [https://stackoverflow.com/questions/42004835/pyinstaller-wand-imagemagick-missing-dependencies](https://stackoverflow.com/questions/42004835/pyinstaller-wand-imagemagick-missing-dependencies)  
14. Briefcase Documentation, accessed June 14, 2026, [https://briefcase.beeware.org/\_/downloads/en/v0.3.25/pdf/](https://briefcase.beeware.org/_/downloads/en/v0.3.25/pdf/)  
15. Qt for Python & Briefcase \- Qt Documentation, accessed June 14, 2026, [https://doc.qt.io/qtforpython-6/deployment/deployment-briefcase.html](https://doc.qt.io/qtforpython-6/deployment/deployment-briefcase.html)  
16. Briefcase, accessed June 14, 2026, [https://briefcase.beeware.org/](https://briefcase.beeware.org/)  
17. astral-sh/python-build-standalone: Produce redistributable builds of Python \- GitHub, accessed June 14, 2026, [https://github.com/astral-sh/python-build-standalone](https://github.com/astral-sh/python-build-standalone)  
18. trowel 0.3.0 on PyPI \- Libraries.io \- security & maintenance data for open source software, accessed June 14, 2026, [https://libraries.io/pypi/trowel](https://libraries.io/pypi/trowel)  
19. Making Python code into an executable app on Mac and Windows? : r/learnpython \- Reddit, accessed June 14, 2026, [https://www.reddit.com/r/learnpython/comments/afjoup/making\_python\_code\_into\_an\_executable\_app\_on\_mac/](https://www.reddit.com/r/learnpython/comments/afjoup/making_python_code_into_an_executable_app_on_mac/)  
20. heritage-cli \- piwheels, accessed June 14, 2026, [https://www.piwheels.org/project/heritage-cli](https://www.piwheels.org/project/heritage-cli)  
21. Using HTMX with FastAPI \- TestDriven.io, accessed June 14, 2026, [https://testdriven.io/blog/fastapi-htmx/](https://testdriven.io/blog/fastapi-htmx/)  
22. FastAPI \+ HTMX: The No-Build Full-Stack \- Blake Crosley, accessed June 14, 2026, [https://blakecrosley.com/guides/fastapi-htmx](https://blakecrosley.com/guides/fastapi-htmx)  
23. How can I make a Python script standalone executable to run without any dependency?, accessed June 14, 2026, [https://stackoverflow.com/questions/5458048/how-can-i-make-a-python-script-standalone-executable-to-run-without-any-dependen](https://stackoverflow.com/questions/5458048/how-can-i-make-a-python-script-standalone-executable-to-run-without-any-dependen)  
24. Using PyInstaller, accessed June 14, 2026, [https://pyinstaller.org/en/v5.13.1/usage.html](https://pyinstaller.org/en/v5.13.1/usage.html)  
25. maces/fastapi-htmx \- GitHub, accessed June 14, 2026, [https://github.com/maces/fastapi-htmx](https://github.com/maces/fastapi-htmx)  
26. Fullstack App with FastAPI and HTMX | Full Tutorial \- YouTube, accessed June 14, 2026, [https://www.youtube.com/watch?v=sT3WSkMyCXA](https://www.youtube.com/watch?v=sT3WSkMyCXA)  
27. Making a desktop application in HTMX \- Reddit, accessed June 14, 2026, [https://www.reddit.com/r/htmx/comments/1aqx8ze/making\_a\_desktop\_application\_in\_htmx/](https://www.reddit.com/r/htmx/comments/1aqx8ze/making_a_desktop_application_in_htmx/)  
28. Embedding External Binaries \- Tauri, accessed June 14, 2026, [https://v2.tauri.app/develop/sidecar/](https://v2.tauri.app/develop/sidecar/)  
29. Embedding External Binaries | Tauri v1, accessed June 14, 2026, [https://tauri.app/v1/guides/building/sidecar](https://tauri.app/v1/guides/building/sidecar)  
30. How to embed Python for sidecar · tauri-apps · Discussion \#2759 \- GitHub, accessed June 14, 2026, [https://github.com/orgs/tauri-apps/discussions/2759](https://github.com/orgs/tauri-apps/discussions/2759)  
31. macOS Application Bundle \- Tauri, accessed June 14, 2026, [https://v2.tauri.app/distribute/macos-application-bundle/](https://v2.tauri.app/distribute/macos-application-bundle/)  
32. Running and Scheduling QGIS Processing Jobs, accessed June 14, 2026, [https://www.qgistutorials.com/en/docs/running\_qgis\_jobs.html](https://www.qgistutorials.com/en/docs/running_qgis_jobs.html)  
33. 23.8. Using processing from the command line — QGIS Documentation documentation, accessed June 14, 2026, [https://docs.qgis.org/latest/en/docs/user\_manual/processing/standalone.html](https://docs.qgis.org/latest/en/docs/user_manual/processing/standalone.html)  
34. Running simple Python script for QGIS from outside \- GIS Stackexchange, accessed June 14, 2026, [https://gis.stackexchange.com/questions/29580/running-simple-python-script-for-qgis-from-outside](https://gis.stackexchange.com/questions/29580/running-simple-python-script-for-qgis-from-outside)  
35. Installing QGIS plugin from command line or Python \- GIS StackExchange, accessed June 14, 2026, [https://gis.stackexchange.com/questions/356517/installing-qgis-plugin-from-command-line-or-python](https://gis.stackexchange.com/questions/356517/installing-qgis-plugin-from-command-line-or-python)