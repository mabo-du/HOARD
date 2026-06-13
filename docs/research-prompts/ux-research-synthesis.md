# UX Research Synthesis: CLI-to-GUI Divergence

**Filed:** 2026-06-14  
**Source reports:**
- [From CLI to Click](../research-papers/From%20CLI%20to%20Click_%20A%20Strategic%20Roadmap%20for%20Making%20the%20HOARD%20Archaeological%20Pipeline%20Accessible%20to%20Non-Terminal%20Users.md)
- [Architectural Viability](../research-papers/Making%20HOARD%20Accessible%20to%20Non-Users.md)  
**Related prompt:** [UX Beyond the Terminal](ux-beyond-the-terminal.md)

---

## The Core Divergence

Report 1 ("From CLI to Click") ranks **web wrapper first, Tauri second, Trowel third/fourth**.  
Report 2 ("Architectural Viability") ranks **Trowel integration first, web wrapper second, Tauri third**.

The divergence traces to one factual assumption: Report 2 asserts Trowel already has standalone PyInstaller desktop builds (.exe, .dmg). Report 1 assumes Trowel is pip-only.

**The single deciding question: does Trowel have standalone installer builds, or is it pip-installable only?**

---

## Where They Converge

- The ultra-light tier is the most important existing accessibility lever
- Textual TUI is low priority (too narrow an audience)
- Guided onboarding and CLI presets are parallel infrastructure, not alternatives
- FastAPI is the right web backend choice
- Tauri introduces maintenance overhead from Rust/Python hybrid
- The cold-start problem (getting installed and running) is harder than the UI problem

## Key Insights from Report 2

- **`--gui-mode` flag**: When a GUI calls HOARD, it suppresses Rich TUI output and emits structured JSON logs to stdout. This is a clean architectural boundary regardless of GUI choice — should be built first.
- **Wand/ImageMagick DLL bundling**: PyInstaller on Windows needs explicit registry key extraction for ImageMagick.
- **SSE over polling**: Server-Sent Events (supported natively by HTMX) for real-time pipeline progress.
- **System keychain for vault credentials**: Windows Credential Manager / macOS Keychain instead of in-process variables.
- **FastAPI + HTMX over FastAPI + Svelte**: No Node.js, no build step, no separate frontend codebase.

## Decision Tree

```
If Trowel has standalone builds →
  Trowel integration: 2-3 weeks, --gui-mode, QThread workers,
  JSON logs → PyQt progress bars. Cold-start solved by existing installer.
  Web wrapper becomes future option for users without Trowel.

If Trowel is pip-only →
  Web wrapper (FastAPI + HTMX) with PyInstaller bundling:
  4-5 weeks, invest in PyInstaller pipeline (Wand/ImageMagick fix),
  write desktop launcher.

Either way →
  Build --gui-mode flag first (low effort, prerequisite)
  Promote ultra-light tier in docs (zero-cost accessibility win)
```

## Verdict

The two reports don't conflict — they make different bets on one unknown. The single factual question (does Trowel ship standalone builds?) determines which bet is correct. Everything else — FastAPI + HTMX, `--gui-mode`, ultra-light tier prominence, SSE for progress, system keychain vault — is consensus and should be treated as design direction regardless of the Trowel decision.

---

## Update 2026-06-14: Pivotal Fact Confirmed

**Trowel has standalone PyInstaller builds.** The Trowel project has a complete build pipeline at `.github/workflows/build.yml` that uses `pyinstaller trowel.spec --noconfirm` to produce platform executables for Linux, Windows, and macOS. These are uploaded to GitHub Releases as `.tar.gz` packages.

This confirms Report 2's assumption was correct. The divergence is resolved in favour of **Trowel integration as the first GUI move** (estimated 2-3 developer-weeks). Report 1's web wrapper drops to a secondary option for users without Trowel.

The `--gui-mode` flag shipped in v0.3.7 with 9 event types (phase_start,
progress, phase_complete, phase_error, phase_skip, review_required,
pipeline_halt, info). The event schema is documented in CHANGELOG.md.

---

## Final Contract: HOARD ↔ Trowel GUI-Mode Protocol

Implemented in HOARD v0.3.8. Trowel side ready for implementation.

### Subprocess lifecycle

```
Trowel spawns:     hoard run --project X --gui-mode
HOARD emits:       events including review_required(phase=N)
HOARD exits:       after pipeline completes or halts
                   
Trowel collects:   all review_required phase numbers
User reviews:      phases in Trowel modal, writes decisions
Trowel re-spawns:  hoard run --project X --gui-mode --from-phase <min>
(min = earliest phase that had review items — single pass forward)
```

### Event schema (v1)

| Event | Payload | When |
|-------|---------|------|
| `phase_start` | phase, name | Phase begins |
| `progress` | phase, current, total, item | Per-item progress in Phase 1/2 |
| `phase_complete` | phase, status, metrics | Phase succeeds |
| `phase_error` | phase, error, hint | Phase fails |
| `phase_skip` | phase, name | Already complete |
| `review_required` | phase, flagged_count, path | Flagged items exist (0-4) |
| `pipeline_halt` | reason | Fatal failure |
| `info` | message | Generic message |

### Key behaviours

- **Batch review**: Pipeline runs to completion, emitting review_required
  events. Trowel collects all affected phases, reviews them after exit.
- **Single re-spawn**: After review, Trowel spawns once with
  `--from-phase <min>` where min is the earliest phase with review items.
  This avoids re-processing un-affected phases.
- **No blocking**: HOARD never blocks for review input in gui-mode.
  It exits cleanly. Trowel manages the entire review lifecycle.
- **Ultra-light ready**: All events work identically with cloud-only
  inference — no GPU or Ollama required.
