# Research Prompt: Making HOARD Accessible to Non-Terminal Users

**Status:** Research prompt — no implementation commitment  
**Filed:** 2026-06-12  
**Context:** HOARD is currently a pure CLI application. This prompt explores how to
serve users who find terminal windows confronting, without compromising the strengths
of a CLI-first architecture.

---

## Technical Context

HOARD (Heritage Observation And Report Drafter) is a Python application distributed
via PyPI as `pip install hoard-erd`. It runs a six-phase AI-assisted pipeline that
converts raw archaeological field records into publication-ready grey literature
reports (DOCX, PDF/A-2b, TEI-XML).

**AI backend:** Multi-provider — Ollama (local GPU), OpenAI, Anthropic Claude, and
Google Gemini. HOARD auto-routes between providers per phase based on task type,
hardware availability, and privacy constraints.

**Hardware tier system (already implemented):**
- Ultra-light — cloud-only inference, no GPU or Ollama required
- Budget — 6 GB VRAM, compact local models
- Standard — 8–12 GB VRAM, full local pipeline
- Performance — 16–24 GB VRAM, high-end models

Hardware tier is auto-detected on first run. **The ultra-light tier is a significant
existing accessibility lever** — a non-technical Windows user with API keys can
potentially run the full pipeline today without installing Ollama or requiring a GPU.
The research must evaluate whether this tier, combined with better onboarding,
substantially changes the accessibility calculus before recommending new UI work.

**Existing Rich TUI:** The review dashboard launches after each pipeline phase and
presents flagged items (blurred images, low-confidence OCR, spatial mismatches,
compliance warnings) for Accept/Edit/Defer review. It covers post-phase review only,
not pipeline execution or project setup.

**Unified ecosystem CLI:** `heritage-cli` provides a single entry point across the
ecosystem (`heritage run/calibrate/lithics/review/matrix/publish`). Evaluate whether
a GUI wrapper should target `hoard` subcommands directly or the `heritage` umbrella.

**Ecosystem integrations (all currently active):**
- StratiGraph — Tauri 2 + React; shared JSON Schema with HOARD Phase 1 exports
- Trowel — PyQt6; **bidirectional JSON import/export and shared jurisdiction
  templates already implemented**; evaluate whether Trowel could launch HOARD
  pipeline phases from within its existing GUI
- Libby — FastAPI + Svelte 5; proves this stack is viable in the ecosystem
- Cache & Carry — Tauri + Rust
- Dibble — Python + PyVista

The developer has existing Tauri 2 experience from StratiGraph and can reuse
patterns and potentially UI components from that codebase.

**Credential vault:** AES-256-GCM + PBKDF2, cross-compatible with the Kryptis
vault format. Any web-based UI must handle vault unlock safely.

**The installation problem is a distinct barrier from the interface problem.**
`pip install hoard-erd` presupposes Python installed and on the PATH — not a given
for a Windows heritage professional. The research must address distribution strategy
(standalone installer, bundled Python, winget/brew packaging) as a separate axis
from which UI approach is chosen. A polished Textual TUI is useless if the user
can't install the package.

---

## Target User Persona

The non-terminal user being served is a **commercial field archaeologist or heritage
consultant** who:
- Uses Windows or macOS (not Linux)
- Is comfortable with QGIS, Excel, and commercial CRM software
- Has never opened a terminal by choice
- Manages a small team on site (2–10 people)
- Would benefit from HOARD's pipeline but currently relies on manual report drafting

This is not a developer. They are not a student. They may supervise junior staff who
are equally non-technical.

---

## Background

HOARD's CLI design was intentional:

- CLI tools compose well with scripts, CI/CD, and headless automation
- A GUI would add maintenance burden and platform-specific complexity
- The target audience (commercial archaeologists) already uses terminal-based tools
  (ARK, R, QGIS plugins)
- The review dashboard already provides a Rich TUI for interactive use

But there's a real user segment who need HOARD's pipeline but are intimidated by the
terminal. The question is: what does "help" look like for them?

---

## Areas to Explore

### 1. Progressive Disclosure — CLI with Training Wheels

How much can be done *within* the terminal before needing a GUI?

- An interactive `hoard wizard` command that steps through setup, project init,
  model selection, and pipeline execution with prompts and defaults
- Colour-coded guidance messages explaining what each phase does before running it
- A "dry run" mode that shows what will happen without executing
- Defaults for everything — user only types `hoard run` and it works
- A `hoard doctor` that checks prerequisites and suggests fixes (Ollama running?
  Models pulled? Enough disk space?)

### 2. TUI Enhancement (Terminal User Interface)

The review dashboard already uses Rich. Could this be extended?

- A full-terminal dashboard (`hoard dashboard`) showing project status, phase
  progress, and one-click phase execution
- File picker dialogs in the terminal (via Rich or Textual)
- A tree view of the workspace with actions on each file
- Real-time phase progress with estimated time remaining

[Textual](https://github.com/Textualize/textual) is the natural framework —
same maintainer as Rich, same ecosystem, potentially installable as an optional
dependency rather than a core requirement.

Evaluate whether Textual should be a core dependency, an optional extra
(`pip install hoard[tui]`), or deferred to a separate companion package.

### 3. Web-Based Wrapper (Local-Only)

A local web server that wraps the CLI:

- `hoard serve` — starts a local web UI at http://localhost:8765
- No cloud, no data leaves the machine
- Web-based file upload (drag-and-drop field records)
- Start/stop pipeline phases with a button
- Progress bars and logs in the browser
- Preview generated reports before export
- Potentially accessible from a tablet on the same LAN

Implementation approaches to compare (treat these as distinct options, not
a single option):
- **FastAPI + minimal JS** — backend serves REST endpoints; frontend is plain
  HTML with fetch() calls; no build step
- **FastAPI + HTMX** — server-side rendering, hypermedia responses; no JS
  framework; minimal complexity
- **FastAPI + Svelte** — compiled frontend with reactive UI; requires a build
  step; separate frontend codebase

**Critical question to address:** The bootstrapping paradox. If the target user
cannot use a terminal, how do they start `hoard serve` in the first place?
Any web-based solution must explicitly address the first-run experience —
e.g., a desktop shortcut, a platform-specific launcher script, or an OS-level
service. Evaluate each sub-option's answer to this problem.

### 4. Tauri Desktop Shell

A thin native desktop application wrapping the HOARD CLI:

- A small Tauri (Rust + web frontend) app that provides a native window with
  a button-based interface for running HOARD phases
- The CLI remains the core; the Tauri shell calls `hoard` subcommands via
  Tauri's `Command` API and streams output to the UI
- Distributable as a native installer (.exe, .dmg, .deb) — solves the
  cold-start problem entirely, no terminal required
- Consistent with the project's existing Tauri experience (Cache & Carry,
  grantAIde)

Evaluate effort, maintenance burden, and whether a Tauri shell adds meaningful
value over a local web server approach given the dev's existing Tauri experience.

### 5. Integration with Existing Desktop Tools

Rather than building a new UI, extend existing tools:

- **Trowel** (PyQt6 desktop report drafter) could integrate HOARD as a pipeline
  engine — user clicks "Run Phase 1" inside Trowel
- A HOARD plugin for QGIS (archaeologists already use it)
- HOARD as a service that other tools call via JSON file-based IPC (already
  designed this way)

**Note:** Trowel integration is likely the lowest-marginal-cost path to a GUI,
since Trowel already exists as a PyQt6 application in the same ecosystem.
Evaluate whether Trowel could serve as the primary GUI entry point for HOARD
without requiring a separate UI codebase — and whether this conflicts with
Trowel's intended scope.

### 6. Configuration Profiles and Presets

Reduce cognitive load for non-technical users regardless of interface:

- `hoard init --quick` — asks only 2 questions (project name, jurisdiction),
  fills everything else with smart defaults
- Pre-built hardware profiles: `hoard init --desktop`, `hoard init --laptop`
- Template starter packs: `hoard init --template heritage-survey`
- A `hoard.json` presets file that teams can share and distribute

### 7. Guided Onboarding Flow

A first-run experience:

- On first `hoard`, show a welcome screen with links to documentation
- Check prerequisites automatically and report status with emoji/colour
- Offer to run `hoard wizard` for a guided setup
- Provide example commands that the user can copy-paste (with their project
  name pre-filled)
- "Quickstart" mode that downloads a test dataset and runs the full pipeline
  end-to-end

---

## Parallel Track (Not an Alternative)

Documentation, tutorials, and video walkthroughs are a **parallel investment**,
not an alternative to a UI solution. Assume whichever UI option is chosen will
be accompanied by:

- A "HOARD in 5 commands" cheat sheet
- A first-run tutorial in the README
- Possibly an animated GIF or short screen recording

The research report should not rank documentation as a substitute for a UI
improvement. It should note, per top-ranked option, what documentation would
need to accompany it.

---

## Constraints to Respect

Any solution should preserve HOARD's core design principles:

1. **Offline-first** — no mandatory cloud dependency
2. **File-based IPC** — the CLI is the API; web/desktop UIs shell out to it
3. **Minimal core dependency footprint** — avoid adding heavy frameworks to
   the base `pip install hoard`; optional extras (`hoard[tui]`, `hoard[web]`)
   are acceptable
4. **Maintainable by one developer** — don't create a separate UI codebase
   that diverges from the CLI and requires independent maintenance
5. **No credential exposure** — web UI must handle the encrypted vault safely
6. **Cross-platform** — target users are on Windows and macOS; Linux is
   secondary for this persona
7. **Solves the cold-start problem** — the solution must work for a user who
   has never opened a terminal

---

## Evaluation Rubric

Score each approach on the following criteria. Weights reflect a solo developer
with no maintenance budget:

| Criterion | Weight | Description |
|---|---|---|
| Solo maintenance burden | HIGH | Will this diverge, rot, or require active upkeep? |
| Effort to MVP | HIGH | Developer-weeks to a usable first version |
| Cold-start solvability | HIGH | Can a non-terminal user actually launch this? |
| Dependency impact (core) | MEDIUM | Does this bloat `pip install hoard`? |
| Reach | MEDIUM | How many of the target persona does this actually help? |
| Security risk | MEDIUM | Does this introduce credential exposure or data leakage? |
| Synergy with existing tools | LOW | Does this leverage Trowel, Tauri, or QGIS already built? |

---

## Recommended Output

Produce the following, in order:

1. **Summary paragraph** (3–4 sentences): What is the core tension being solved,
   and what is the single most important finding?

2. **Ranked approaches table**: All evaluated options ranked 1–N by combined
   effort-to-impact score, with one-line rationale per entry.

3. **Detailed write-up for top 2 options**, each covering:
   - What it looks like from the target user's perspective (a brief narrative)
   - How the cold-start problem is solved
   - What files/modules in HOARD need to change
   - What new dependencies are required (core vs optional)
   - The minimum viable version that would be genuinely useful
   - Estimated developer-weeks to MVP for a solo developer
   - Main maintenance risk

4. **One paragraph per remaining option** covering why it was ranked where it
   was and any notable tradeoff.

5. **Documentation note**: For the top-ranked option, what documentation would
   need to accompany the release to make it usable by the target persona?
