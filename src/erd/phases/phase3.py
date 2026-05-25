"""phase3.py — Synthesis & Narrative Drafting.

Calls the Phase 3 LLM (Qwen3.5-4B via Ollama) with a complete context
assembled from all Phase 1-2 outputs. Produces a structured Markdown draft
matching the jurisdiction template skeleton.

The model runs in "thinking mode" — it produces an internal reasoning chain
before the final draft. This reasoning chain is captured and logged.

exports: run_phase3(config) -> dict  — executes synthesis, returns draft metadata
used_by: erd.cli.run  → orchestrator
rules:   Must call Ollama API (localhost:11434). Must handle Ollama not running.
         Must capture thinking/reasoning chain if available.
         Must flag sections for human review if triggers fire.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from erd.config import Config

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "huihui_ai/qwen3.5-abliterated:4B"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_TIMEOUT = 300  # 5 minutes for drafting

# ── System Prompt ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert commercial archaeologist and grey literature author. Your task is to synthesise the provided field data into a structured, publication-ready excavation report section.

## Rules

1. **Cite only data present in the provided context.** Never invent context numbers, finds, measurements, or interpretations.
2. **Use standard archaeological terminology.** Use the ROMFA scale (Rare/Occasional/Moderate/Frequent/Abundant) for inclusion frequency. Use standard sedimentological descriptors (e.g. "firm mid-brown silty clay", not "brown dirt").
3. **Respect stratigraphic logic.** Cuts must be described before their fills. Deposits cannot be earlier than the cuts they fill. The Harris Matrix relationships are authoritative — do not contradict them.
4. **Use passive voice and objective tone.** Archaeological grey literature is written in formal, impersonal style.
5. **When data is insufficient**, say so explicitly rather than inventing interpretations. Phrases like "the function of this feature remains uncertain" or "no dating evidence was recovered from this context" are acceptable.
6. **Section format:** Begin each section with `##section:{section_id}` on its own line, followed by the section heading, then the narrative content.

## Terminological Reference

- **ROMFA scale for inclusions**: Rare (<1%), Occasional (1-5%), Moderate (5-25%), Frequent (25-50%), Abundant (>50%)
- **Colour**: Use standard Munsell-derived descriptions (e.g. "dark greyish-brown", "mid-yellowish brown")
- **Compaction**: Very loose / Loose / Firm / Compact / Very Compact
- **Sorting**: Well-sorted / Moderately sorted / Poorly sorted
- **Inclusions**: Describe by type, size range in mm, angularity (angular/sub-angular/sub-rounded/rounded), and frequency (ROMFA)
"""

# ── Context Assembly ────────────────────────────────────────────────────────


def _load_json_safe(path: Path) -> dict[str, Any]:
    """Load JSON file, returning empty dict if missing or corrupt."""
    try:
        if path.exists() and path.suffix == ".json":
            return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _find_json_files(directory: Path, pattern: str = "*.json") -> list[Path]:
    """Find JSON files in a directory, sorted by name."""
    if not directory.is_dir():
        return []
    return sorted(directory.glob(pattern))


def _render_site_metadata(config: Config) -> str:
    """Render site metadata block from project config."""
    return (
        f"## Site Metadata\n"
        f"- **Project ID**: {config.project_id}\n"
        f"- **Project Name**: {config.project_name}\n"
        f"- **Jurisdiction**: {config.jurisdiction}\n"
        f"- **Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
    )


def _render_context_summary(digitised_dir: Path) -> str:
    """Render a condensed context sheet summary table from Phase 1 JSON."""
    context_files = _find_json_files(digitised_dir)
    if not context_files:
        return "*No context data available.*\n"

    rows: list[list[str]] = []
    for ctx_file in context_files:
        data = _load_json_safe(ctx_file)
        ctx_num = data.get("context_number", str(ctx_file.stem))
        ctx_type = data.get("type", "")
        description = data.get("description", "")[:120]
        interpretation = data.get("interpretation", "")[:60]
        period = data.get("period", "")
        rows.append([ctx_num, ctx_type, description, interpretation, period])

    if not rows:
        return "*No context data available.*\n"

    lines = [
        "## Context Register Summary",
        "",
        "| Context | Type | Description | Interpretation | Period |",
        "|---------|------|-------------|----------------|--------|",
    ]
    for row in rows:
        escaped = [c.replace("|", "\\|") for c in row]
        lines.append(f"| {' | '.join(escaped)} |")

    return "\n".join(lines) + "\n"


def _render_harris_relationships(digitised_dir: Path) -> str:
    """Render stratigraphic relationships as a text summary."""
    context_files = _find_json_files(digitised_dir)
    relationships: list[str] = []
    relation_count = 0

    for ctx_file in context_files:
        data = _load_json_safe(ctx_file)
        ctx_num = data.get("context_number", str(ctx_file.stem))

        cut_by = data.get("cut_by", [])
        for parent in cut_by:
            relationships.append(f"  {ctx_num} is cut by {parent}")
            relation_count += 1

        cuts = data.get("cuts", [])
        for child in cuts:
            relationships.append(f"  {ctx_num} cuts {child}")
            relation_count += 1

        fills = data.get("fills", [])
        for child in fills:
            relationships.append(f"  {ctx_num} is filled by {child}")
            relation_count += 1

        filled_by = data.get("filled_by", [])
        for parent in filled_by:
            relationships.append(f"  {ctx_num} fills {parent}")
            relation_count += 1

        same_as = data.get("same_as")
        if same_as:
            relationships.append(f"  {ctx_num} same as {same_as}")
            relation_count += 1

    if not relationships:
        return "*No stratigraphic relationships recorded.*\n"

    header = f"## Stratigraphic Relationships ({relation_count} relationships)\n"
    return header + "\n".join(sorted(set(relationships))) + "\n"


def _render_finds_summary(digitised_dir: Path) -> str:
    """Render finds catalogue summary from Phase 1 JSON."""
    context_files = _find_json_files(digitised_dir)
    all_finds: list[list[str]] = []
    total_finds = 0

    for ctx_file in context_files:
        data = _load_json_safe(ctx_file)
        ctx_num = data.get("context_number", str(ctx_file.stem))
        finds = data.get("finds", [])
        for find in finds:
            find_type = find.get("type", "")
            qty = str(find.get("qty", find.get("quantity", "")))
            period = find.get("period", "")
            notes = find.get("notes", "")[:60]
            all_finds.append([ctx_num, find_type, qty, period, notes])
            total_finds += int(qty) if qty.isdigit() else 0

    if not all_finds:
        return "*No finds data available.*\n"

    lines = [
        "## Finds Summary",
        f"Total: {total_finds} items across {len(all_finds)} entries.",
        "",
        "| Context | Type | Quantity | Period | Notes |",
        "|---------|------|----------|--------|-------|",
    ]
    for row in all_finds:
        escaped = [c.replace("|", "\\|") for c in row]
        lines.append(f"| {' | '.join(escaped)} |")

    return "\n".join(lines) + "\n"


def _render_sample_results(digitised_dir: Path) -> str:
    """Render environmental/sample results from Phase 1 JSON."""
    context_files = _find_json_files(digitised_dir)
    all_samples: list[list[str]] = []

    for ctx_file in context_files:
        data = _load_json_safe(ctx_file)
        ctx_num = data.get("context_number", str(ctx_file.stem))
        samples = data.get("samples", [])
        for sample in samples:
            sample_id = sample.get("id", "")
            sample_type = sample.get("type", "")
            notes = sample.get("notes", "")[:80]
            all_samples.append([ctx_num, sample_id, sample_type, notes])

    if not all_samples:
        return "*No sample data available.*\n"

    lines = [
        "## Sample Results",
        "",
        "| Context | Sample ID | Type | Notes |",
        "|---------|-----------|------|-------|",
    ]
    for row in all_samples:
        escaped = [c.replace("|", "\\|") for c in row]
        lines.append(f"| {' | '.join(escaped)} |")

    return "\n".join(lines) + "\n"


def _render_photo_captions(spatial_dir: Path) -> str:
    """Render photo captions and annotations from Phase 2 outputs."""
    photo_files = _find_json_files(spatial_dir)
    if not photo_files:
        return "*No photo data available.*\n"

    captions: list[str] = ["## Photo Captions & Annotations", ""]
    for photo_file in photo_files:
        data = _load_json_safe(photo_file)
        source = data.get("source_file", photo_file.stem)
        caption = data.get("caption", "")
        grounding = data.get("grounding", [])
        cross_check = data.get("cross_check", {})

        captions.append(f"### {source}")
        if caption:
            captions.append(f"Caption: {caption}")
        if grounding:
            labels = [g.get("label", "?") for g in grounding]
            captions.append(f"Detected features: {', '.join(labels)}")
        inconsistencies = cross_check.get("inconsistencies", [])
        if inconsistencies:
            for inc in inconsistencies:
                captions.append(f"⚠️ Cross-check issue: {inc}")
        captions.append("")

    return "\n".join(captions)


def assemble_context(config: Config) -> str:
    """Assemble the full context document from all Phase 1-2 outputs.

    Returns a single Markdown string combining all data sources,
    formatted as a structured prompt for the LLM.
    """
    digitised_dir = config.digitised_dir
    spatial_dir = config.spatial_dir

    parts: list[str] = [
        _render_site_metadata(config),
        "",
        _render_context_summary(digitised_dir),
        "",
        _render_harris_relationships(digitised_dir),
        "",
        _render_finds_summary(digitised_dir),
        "",
        _render_sample_results(digitised_dir),
        "",
        _render_photo_captions(spatial_dir),
    ]

    return "\n".join(parts)


# ── Ollama API ────────────────────────────────────────────────────────────────


def _ollama_generate(
    model: str,
    system: str,
    prompt: str,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Call Ollama's generate API and return the response.

    Returns dict with 'response' (str) and optionally 'reasoning' (str)
    if the model supports thinking/reasoning output.
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": model,
        "system": system,
        "prompt": prompt,
        "temperature": temperature,
        "stream": False,
        "options": {
            "num_ctx": 32768,  # 32K context window
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        result = resp.json()

        response_text = result.get("response", "")

        # Try to extract thinking/reasoning if present
        # Qwen3.5 in thinking mode outputs <think>...</think> blocks
        reasoning = None
        think_match = re.search(
            r"<think>(.*?)</think>", response_text, re.DOTALL
        )
        if think_match:
            reasoning = think_match.group(1).strip()
            # Remove thinking block from the response
            response_text = re.sub(
                r"<think>.*?</think>\s*", "", response_text, flags=re.DOTALL
            ).strip()

        return {
            "response": response_text,
            "reasoning": reasoning,
            "model": model,
            "eval_count": result.get("eval_count", 0),
            "eval_duration": result.get("eval_duration", 0),
        }

    except requests.ConnectionError:
        raise RuntimeError(
            f"Cannot connect to Ollama at {OLLAMA_BASE_URL}. "
            f"Ensure Ollama is running: 'ollama serve'"
        )
    except requests.Timeout:
        raise RuntimeError(
            f"Ollama request timed out after {timeout}s. "
            f"The model may still be loading or the prompt is too long."
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Ollama API error: {e}")


def _extract_sections(markdown_text: str) -> dict[str, str]:
    """Extract labelled sections from the model output.

    Sections are marked with `##section:{section_id}` labels.
    Returns dict mapping section_id to section content.
    """
    sections: dict[str, str] = {}
    current_section: str | None = None
    current_lines: list[str] = []

    for line in markdown_text.split("\n"):
        section_match = re.match(r"^##section:(\S+)", line.strip())
        if section_match:
            # Save previous section
            if current_section is not None:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = section_match.group(1)
            current_lines = [line]  # Include the section label
        elif current_section is not None:
            current_lines.append(line)

    # Save last section
    if current_section is not None and current_lines:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections


# ── Review Triggers ──────────────────────────────────────────────────────────


def _check_review_triggers(
    draft_text: str,
    context_data: dict[str, Any],
) -> list[dict[str, str]]:
    """Check the generated draft for conditions that require human review.

    Returns a list of trigger dicts with 'section', 'issue', and 'detail' keys.
    """
    triggers: list[dict[str, str]] = []

    # Trigger 1: Model expressed uncertainty
    uncertainty_phrases = [
        "insufficient data",
        "conflicting evidence",
        "cannot determine",
        "unclear",
        "uncertain",
        "requires further",
        "further investigation",
    ]
    for phrase in uncertainty_phrases:
        for line in draft_text.lower().split("\n"):
            if phrase in line and len(line) < 200:
                # Find which section this belongs to
                section = "unknown"
                section_match = re.match(r"^##section:(\S+)", line)
                if section_match:
                    section = section_match.group(1)
                triggers.append({
                    "section": section,
                    "issue": "UNCERTAINTY",
                    "detail": f"Model expressed uncertainty: '{phrase}' in: {line.strip()[:100]}",
                })
                break

    # Trigger 2: Draft references a context number not in the source data
    known_contexts = set()
    for entry in context_data.get("context_numbers", []):
        known_contexts.add(str(entry))
    # Extract all [NNN] or NNN context references from draft
    draft_refs = set(re.findall(r"\[(\d+)\]", draft_text))
    draft_refs |= set(re.findall(r"(?<!\w)(\d{3,4})(?!\w)", draft_text))
    unknown_refs = draft_refs - known_contexts
    if unknown_refs and known_contexts:
        triggers.append({
            "section": "unknown",
            "issue": "HALLUCINATED_CONTEXT",
            "detail": f"Draft references context numbers not in source data: {', '.join(sorted(unknown_refs)[:10])}",
        })

    return triggers


# ── Main Entry Point ─────────────────────────────────────────────────────────


def run_phase3(config: Config, model: str = DEFAULT_MODEL) -> dict[str, Any]:
    """Execute Phase 3: Synthesis & Narrative Drafting.

    Args:
        config: Pipeline configuration.
        model: Ollama model name. Defaults to huihui_ai/qwen3.5-abliterated:4B.

    Returns:
        Dict with keys:
            - 'status': 'complete' | 'failed'
            - 'model': model used
            - 'sections': dict of section_id → content
            - 'reasoning': model's reasoning chain (or None)
            - 'triggers': list of review trigger dicts
            - 'draft_path': path to written draft file
            - 'reasoning_path': path to written reasoning log
            - 'total_tokens': int
            - 'duration_ms': int
    """
    start_time = time.time()

    # Create draft and logs directories
    config.draft_dir.mkdir(parents=True, exist_ok=True)
    config.logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Step 1: Assemble context
    context_text = assemble_context(config)

    # Step 2: Build drafting prompt
    drafting_template = (
        "Using the site data provided below, write the excavation report sections.\n\n"
        "### Site Data\n\n"
        "{context}\n\n"
        "### Instructions\n\n"
        "Write the following sections one by one based on the site data above.\n"
        "Each section MUST begin with `##section:{{section_id}}` on its own line.\n"
        "Do NOT merge sections — each section label starts a new section.\n\n"
        "Format example:\n"
        "##section:executive_summary\n"
        "The archaeological evaluation...\n\n"
        "##section:introduction\n"
        "The site is located...\n\n"
        "Required sections:\n"
        "1. **executive_summary** — 2-3 paragraph summary of the excavation, methods, and key findings\n"
        "2. **introduction** — Site location, NGR, geology, topography, and project background\n"
        "3. **methodology** — Excavation strategy, recording system, finds and sampling policy\n"
        "4. **stratigraphic_narrative** — Phased description of ALL contexts in chronological order, grouped by period. Cover every context from the data.\n"
        "5. **finds_summary** — Overview of recovered finds by category and period\n"
        "6. **environmental_summary** — Summary of environmental samples and results\n"
        "7. **discussion** — Interpretation of the site in its local and regional context\n"
        "8. **archive_statement** — Recommended archive deposition and accession details\n"
    )
    drafting_prompt = drafting_template.format(context=context_text)

    # Step 3: Collect context numbers for review trigger checking
    context_numbers: set[str] = set()
    for f in _find_json_files(config.digitised_dir):
        data = _load_json_safe(f)
        ctx = data.get("context_number")
        if ctx:
            # Strip brackets
            clean = ctx.strip("[]")
            context_numbers.add(clean)

    # Step 4: Call Ollama
    logger.info(f"Calling Ollama model: {model}")
    result = _ollama_generate(
        model=model,
        system=SYSTEM_PROMPT,
        prompt=drafting_prompt,
        temperature=DEFAULT_TEMPERATURE,
    )

    duration_ms = int((time.time() - start_time) * 1000)

    if result.get("response"):
        draft_text = result["response"]
    else:
        return {
            "status": "failed",
            "model": model,
            "error": "Model returned empty response",
        }

    # Step 5: Extract sections
    sections = _extract_sections(draft_text)

    # Step 6: Check review triggers
    triggers = _check_review_triggers(
        draft_text, {"context_numbers": context_numbers}
    )

    # Step 7: Write draft to disk
    draft_path = config.draft_dir / f"draft_{timestamp}.md"
    draft_path.write_text(draft_text)
    logger.info(f"Draft written to {draft_path}")

    # Step 8: Write reasoning chain if present
    reasoning_path = None
    if result.get("reasoning"):
        reasoning_path = config.logs_dir / f"phase3_reasoning_{timestamp}.txt"
        reasoning_path.write_text(result["reasoning"])
        logger.info(f"Reasoning chain written to {reasoning_path}")

    return {
        "status": "complete",
        "model": model,
        "sections": sections,
        "reasoning": result.get("reasoning"),
        "triggers": triggers,
        "draft_path": str(draft_path),
        "reasoning_path": str(reasoning_path) if reasoning_path else None,
        "total_tokens": result.get("eval_count", 0),
        "duration_ms": duration_ms,
    }
