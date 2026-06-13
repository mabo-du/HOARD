# HOARD — Multi-Provider AI Abstraction Layer

## Project Context (for the AI researcher)

**HOARD** (Heritage Observation And Report Drafter) is a fully local, multi-stage AI pipeline that converts archaeological field data into near-publication-ready grey literature reports. Currently all GPU inference goes through **Ollama** at `http://localhost:11434` using four models:

| Phase | Task | Current Model | VRAM |
|-------|------|---------------|------|
| 1 | Document digitisation | GLM-OCR (0.9B) via Ollama | ~2.2 GB |
| 2 | Photo captioning | Qwen3-VL-8B via Ollama | ~5.5 GB |
| 3 | Synthesis & drafting | Qwen3.5-4B via Ollama | ~2.8 GB |
| 4 | Compliance refinement | Gemma 4-E2B via Ollama | ~2.1 GB |

### The Problem

HOARD was designed for **fully local operation on consumer GPUs**, but this has proven too restrictive:

1. **Archaeologists work in varied environments** — not always at the dig site with a GPU-equipped machine. They may be in a café, university library, or museum without GPU access.
2. **Cloud quality gap** — The cloud-llm-blockers research found that cloud models (Gemini 2.5 Flash-Lite at $0.10/M tokens) produce notably better prose than local 4B models. The cost analysis showed cloud is actually **40× cheaper** when accounting for hardware depreciation ($0.047/site cloud vs $1.95/site local).
3. **Inconsistent hardware** — HOARD targets 6 GB VRAM, but many archaeologists have laptops with no GPU at all, or high-end workstations with 24 GB. Supporting multiple tiers requires provider abstraction.
4. **NuExtract3 integration blocked** — NuExtract3 (ideal for structured field data extraction) is not available via Ollama and requires custom llama.cpp setup. A cloud fallback (Gemini Flash-Lite for extraction) solves this.

### Previous Research Already Completed

An earlier deep research prompt (`cloud-llm-blockers.md`) investigated:
- Cloud provider architecture via a `ModelProvider` interface with `LocalOllamaProvider` and cloud implementations
- Phase-specific cloud recommendations (Azure Document Intelligence + Gemini Flash-Lite for Phase 1)
- Cost analysis (local: $1.95/site vs cloud: $0.047/site for budget models)
- ADS grey literature access blockers (OAI-PMH workaround proposed)
- NuExtract3 deployment paths (GGUF via llama.cpp or numind Python SDK)

However, this research was **preliminary** — it identified the architectural direction but did not produce concrete implementation designs.

### What Has Changed Since That Research

- HOARD's actual implementation uses **GLM-OCR + Qwen3-VL + Qwen3.5-4B + Gemma 4-E2B** (not the design doc's original model selections)
- The NuExtract3 structured extraction issue has been diagnosed in detail (`nuextract3-structured-mode.md`) — it requires a custom `chat_format_handler` for `llama-cpp-python`
- **Simmer** (sibling project at `/home/mark/Projects/simmer`) has a production-tested multi-provider AI client supporting 10 providers including Ollama, OpenAI, Anthropic, Google, Cohere, LM Studio, vLLM, and custom endpoints
- The research established that cloud is genuinely cheaper for sporadic archaeological use

### Related Ecosystem Projects

Simmer's AI client at `~/Projects/simmer` is the most comprehensive multi-provider abstraction in this ecosystem. It supports OpenAI, Anthropic, Google Gemini, Cohere, DeepSeek, Ollama, LM Studio, vLLM, OpenRouter, and custom endpoints. It has per-provider retry logic, streaming, and AES-256-GCM key storage.

**Kryptis** (`~/Projects/kryptis`) provides a standalone AES-256-GCM local credential vault that multiple projects could share.

---

## Research Questions

### Q1: Provider Abstraction Interface Design

Design a `ModelProvider` interface that HOARD's four GPU phases can use interchangeably with local (Ollama/llama.cpp) and cloud (OpenAI, Anthropic, Google Gemini, OpenRouter) backends.

**Current HOARD inference calls** (what the abstraction must support):
- **Phase 1 (GLM-OCR)**: Ollama chat completion with `format` parameter for JSON schema, `keep_alive=0` for VRAM eviction, temperature=0
- **Phase 2 (Qwen3-VL-8B)**: Ollama chat completion with image input (base64-encoded PNG), temperature=0.1
- **Phase 3 (Qwen3.5-4B)**: Ollama chat completion with large context (up to 70K chars), temperature=0.3, `keep_alive=-1` for thinking mode capture
- **Phase 4 (Gemma 4-E2B)**: Ollama chat completion with `format` for structured JSON section output, temperature=0

**Key design questions:**

1. Should the abstraction be a **thin interface** (each provider wraps the identical call pattern) or a **full abstraction layer** with provider-specific features (streaming, thinking mode, tool use, structured output)?

2. How should **structured output** work across providers?
   - Ollama: `format` parameter with JSON schema
   - OpenAI: `response_format` parameter with `json_schema` or `json_object`
   - Anthropic: `tool_use` with a single tool definition
   - Google Gemini: `response_mime_type: "application/json"` with `response_schema`

3. How should **vision/image inputs** work?
   - Ollama: `images: [base64]` in the message
   - OpenAI: Content parts with `image_url`
   - Anthropic: `source` block with base64 or media type
   - Google: Inline data parts

4. How should **context window management** work? Local models have 32K-262K context; cloud models offer 200K-2M. When should chunk-and-merge (current Phase 3 approach) be bypassed because the selected provider has enough context?

5. Should the abstraction include a **cost tracker** that logs per-phase token usage and estimated cost across all providers?

**Reference existing implementations to analyze:**
- Simmer's AI client (`~/Projects/simmer`) — multi-provider abstraction in TypeScript/Rust
- LangChain's provider abstraction (well-known reference, but often criticised as over-abstracted)
- LiteLLM (Python, covers 100+ providers) — would this be a better fit than a custom interface?
- `llama-cpp-python` — already loads NuExtract3 directly; could be the local-only fallback

### Q2: Provider Selection Heuristics

HOARD currently uses fixed models per phase. With multi-provider support, the user could configure provider per phase or let the system choose.

**Design a provider selection mechanism with these modes:**

1. **Manual mode** — user configures per-phase provider in `~/.config/hoard/config.yaml`:
   ```yaml
   phase3:
     provider: anthropic
     model: claude-sonnet-4-20250514
     temperature: 0.3
   phase4:
     provider: ollama
     model: gemma4:latest
   ```

2. **Auto mode** — system selects based on availability:
   - Check Ollama for requested model → if unavailable, try next configured provider
   - If no GPU detected, skip local providers automatically
   - If network unavailable, skip cloud providers automatically

3. **Quality mode** — use cloud for prose-heavy phases (3, 4) and local for extraction phases (1, 2):
   - Phase 1: local GLM-OCR (cheap, fast, deterministic) OR Gemini Flash-Lite if no GPU
   - Phase 2: local Qwen3-VL (spatial understanding is critical) OR Gemini 2.5 Flash if no GPU
   - Phase 3: cloud Claude/Gemini (better prose quality) OR local Qwen3.5-4B if offline
   - Phase 4: cloud (better compliance understanding) OR local Gemma 4-E2B if offline

**Questions:**
- How should provider availability be checked? (Ollama health endpoint, network connectivity test, GPU detection)
- Should there be a **latency budget** — e.g., "never wait more than 30s per phase" → skip slow providers?
- How should the system degrade if the selected provider fails mid-phase? Retry with fallback? Abort with clear error? Cache partial results?
- Should the provider selection be **per-phase**, **per-section** (Phase 4 processes sections individually), or **per-request** (each chat completion call independently routed)?

### Q3: Credential Management

Cloud providers require API keys. HOARD currently has no credential management — it uses Ollama exclusively.

**Design a credential management system that:**

1. **Is compatible with Kryptis** (`~/Projects/kryptis`, a standalone AES-256-GCM credential vault already in the ecosystem) — either by integrating with it or by implementing the same encryption standard
2. **Never stores keys in plaintext** in config files or version control
3. **Supports multiple keys per provider** (e.g., separate keys for development and production, or keys for different organisational accounts)
4. **Works fully offline** — no keyring daemon, no cloud KMS, no system keychain dependency (some archaeologists run Linux without a desktop environment)
5. **Has a CLI interface** for key management: `hoard config set-openai-key`, `hoard config list-providers`, etc.
6. **Keeps keys out of prompt context** — logging or error messages must never include exposed keys

**Questions:**
- Should credentials be stored in the **project workspace** (per-project API keys) or in **global config** (`~/.config/hoard/`)?
- What encryption scheme should be used for local key storage? AES-256-GCM with a master password? macOS Keychain (platform-specific)? GPG?
- Should we integrate with **Kryptis** directly (via its SQLite vault file) or independently (re-implement AES-256-GCM in Python)?
- How should the master password be handled — prompt on first use, environment variable, or store a hash?

### Q4: Local-First Architecture for Hybrid Workflows

HOARD's core value proposition is **local-first** — no data leaves the machine. Adding cloud support must not compromise this.

**Design a hybrid architecture that:**

1. **Keeps all raw field data local** — only inference requests go to cloud APIs; never upload site photos, context sheets, or finds catalogues to third parties
2. **Has an explicit "offline mode"** — if network is unavailable, all phases fall back to local models automatically
3. **Supports air-gapped operation** — a configuration flag `--offline` that never attempts cloud connections
4. **Is transparent about data handling** — logs exactly what data was sent to which provider in the project audit trail
5. **Optionally supports on-premise models** — for institutional users who deploy their own vLLM or TGI endpoints behind a VPN

**Questions:**
- For cloud providers, what data goes over the wire? Only the text prompt (context sheets already digitised by Phase 1) or also images (Phase 2 photo captioning)?
- Should there be a **privacy tier** system — "never send images to cloud" vs "images OK but not site coordinates" vs "full cloud"?
- How should HOARD's **audit trail** capture cloud usage — log: `Phase 3: 12,847 tokens sent to claude-sonnet-4 ($0.19) at 2026-06-08T14:30:00Z`?
- For institutional deployment, how should a **custom endpoint** (e.g., company's internal vLLM at `https://ai.internal.org/v1`) be configured? Should the abstraction support OpenAI-compatible endpoints generically?

### Q5: Offline Model Tier System

Not all users have the same hardware. Design a **tier system** that configures all four phases based on available resources:

| Tier | VRAM | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|------|------|---------|---------|---------|---------|
| **Ultra-light** | No GPU | Gemini Flash-Lite API | Gemini 2.5 Flash API | Gemini 2.5 Pro API | Gemini 2.5 Flash API |
| **Budget** | 6 GB | GLM-OCR (2.2 GB) | Qwen3-VL-4B (2.8 GB) | Qwen3.5-4B (2.8 GB) | Gemma 4-E2B (2.1 GB) |
| **Standard** | 8-12 GB | GLM-OCR (2.2 GB) | Qwen3-VL-8B (5.5 GB) | Qwen3.5-4B (2.8 GB) | Gemma 4-E2B (2.1 GB) |
| **Performance** | 16-24 GB | NuExtract3 (4.5 GB) | PaliGemma 2 (8 GB) | Qwen3-8B (5.5 GB) | Gemma 4-9B (5.5 GB) |

**Questions:**
- Should tiers be **auto-detected** (probe VRAM + model availability on `hoard init`) or **manually selected**?
- What if a user has 8 GB but wants to run the Performance tier — should HOARD warn and proceed, or block?
- Should the tier system be **extensible** — can users define custom tiers in config?
- How does the tier system interact with the **multi-provider abstraction**? If a user has no GPU, Tier 1 should auto-select cloud providers (and prompt for API keys on first run).

---

## Deliverables

For each question, please provide:

1. **Concrete type signatures** (TypeScript or Python) for the core interfaces — `ModelProvider`, `InferenceRequest`, `InferenceResponse`, `ProviderConfig`, `CredentialStore`
2. **Provider implementation outlines** for at least: Ollama, OpenAI, Anthropic, Google Gemini, and OpenRouter
3. **Error handling patterns** — retry logic, rate limiting, context window exceeded, authentication failure, network timeout
4. **Configuration file format** (YAML schema) for `~/.config/hoard/config.yaml`
5. **Credential storage format** (encrypted file schema + CLI commands)
6. **Migration path** from current Ollama-only to multi-provider — must be incremental, no breaking changes
7. **Cost comparison table** — updated from the prior cloud-llm-blockers research, showing per-phase cost for each provider tier on a typical 50-context site report

Focus on practical, implementable Python code. The researcher has a working HOARD codebase at `/home/mark/Projects/HOARD` and sibling projects at `/home/mark/Projects/simmer` (multi-provider AI client) and `/home/mark/Projects/kryptis` (credential vault) that can be referenced for patterns.

---

## Architect's Decisions (Confirmed 2026-06-08)

After reviewing four Deep Research papers covering both this prompt and the Ecosystem Integration Architecture prompt, the following architectural decisions were confirmed:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Provider interface type** | Python `Protocol` (not `ABC`) | More Pythonic, lighter; Papers 1/3 both acceptable, Protocol preferred |
| **Capability model** | Rich feature exposure with `capabilities()` method returning structured TypedDict | NOT lowest-common-denominator; phase code checks capabilities, not provider identity |
| **Credential storage** | Encrypted YAML (`~/.config/hoard/credentials.yaml.enc`) using AES-256-GCM + PBKDF2 | Mirrors Kryptis schema precisely; simpler to backup and reason about for 4-5 API keys |
| **Vocabulary service** | Python importable library (NOT MCP for initial implementation) | MCP introduces subprocess lifecycle overhead; start with library, upgrade to MCP in Phase F |
| **Config format** | TOML (`~/.config/hoard/config.yaml` for now, `~/.config/heritage/config.toml` post-Phase D) | Python 3.11+ stdlib support; cross-project unification planned |
| **Template format** | Shared YAML core with `hoard:` / `trowel:` extension blocks | Matches HOARD's existing `extends` pattern; simpler than subdirectory approach |
| **Orchestration** | YAML pipeline definition + state machine execution (combined approach) | YAML defines the DAG, state machine drives resumability |
| **Privacy tiers** | 3 tiers: Strict Local, Sanitized Cloud, Full Hybrid | Paper 1 detailed this well; implemented via per-phase routing rules |
| **Cost tracking** | Built into InferenceResponse; logged to per-project audit trail | Enables institutional transparency |
| **Migration** | Incremental: new abstraction layer runs alongside existing Ollama-only code | Users upgrade with zero workflow changes; cloud features opt-in |
| **Timeline** | 4-6 months for full 6-phase roadmap | Budgeted for part-time availability |

See the companion prompt (`ecosystem-integration-architecture.md`) for the full 6-phase implementation roadmap.
