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
