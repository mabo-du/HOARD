# GUI-Mode Protocol: HOARD ↔ Desktop Tools

**Version:** 1.0 (HOARD v0.3.8+)  
**Intended for:** Trowel integration and any other desktop GUI consuming HOARD's pipeline events.

---

## How It Works

When invoked with `--gui-mode`, HOARD suppresses Rich TUI console output and
emits structured JSON events to stdout instead. A desktop tool (Trowel) spawns
HOARD as a subprocess, reads stdout line-by-line, parses each JSON line, and
maps events to native UI elements.

## Subprocess Lifecycle

```
Trowel spawns:     hoard run --project X --gui-mode
HOARD emits:       events including review_required(phase=N)
HOARD exits:       after pipeline completes or halts

Trowel reads:      all events from stdout until process exit
Trowel collects:   all review_required phase numbers received
User reviews:      flagged items in Trowel's review modal
User writes:       Accept/Edit/Defer decisions back to workspace
Trowel re-spawns:  hoard run --project X --gui-mode --from-phase <min>
```

The `min` value is the lowest phase number that emitted `review_required`.
This single re-spawn runs forward from that phase, picking up all review
decisions in one pass.

## Event Schema

### Phase lifecycle

```json
{"event": "phase_start", "phase": 0, "name": "Ingestion & Triage"}
{"event": "phase_skip",  "phase": 1, "name": "Multi-Modal Digitisation"}
{"event": "phase_error", "phase": 2, "error": "Ollama not running", "hint": "Ensure Ollama is running"}
{"event": "phase_complete", "phase": 3, "status": "success", "sections": 12, "tokens": 45231}
{"event": "pipeline_halt", "reason": "Phase 0 checks failed"}
```

### Progress (Phase 1 — context sheets, Phase 2 — photos)

```json
{"event": "progress", "phase": 1, "current": 3, "total": 15, "item": "ctx_007.jpg"}
```

### Review required

```json
{"event": "review_required", "phase": 0, "flagged_count": 3, "path": "/home/user/.local/share/heritage/workspaces/stoneyfield_2026"}
```

The `path` field points to the project workspace directory. Trowel can scan
for review flags there using the same logic as `hoard review`.

### Info

```json
{"event": "info", "message": "Phase 4: already complete (skipping)"}
```

## Key Behaviours

1. **HOARD never blocks for input in gui-mode.** It runs to completion and
   exits cleanly with exit code 0. The review lifecycle is entirely managed
   by the GUI tool.

2. **All events carry phase numbers** when applicable. The GUI tracks which
   phases need review by collecting `review_required` events.

3. **Ultra-light tier ready.** All events work identically whether using
   local Ollama or cloud-only inference (OpenAI/Anthropic/Google). No GPU
   or Ollama installation required on the user's machine.

4. **HOARD handles full pipeline state.** The workspace tracks completed
   phases. When re-spawning with `--from-phase <N>`, HOARD skips already-
   complete phases and only re-processes from phase N onward.

## Parsing Rules

- One JSON object per line
- Lines without an `event` key should be ignored (may contain logging output)
- Lines are not newline-delimited JSON (NDJSON) — each line is a complete JSON object
- Process exits after pipeline completes — `wait()` for the subprocess
