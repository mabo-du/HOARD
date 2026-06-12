"""phase3.py — Synthesis & Narrative Drafting.

Calls the Phase 3 LLM (Qwen3.5-4B via Ollama) with a complete context
assembled from all Phase 1-2 outputs. Produces a structured Markdown draft
matching the jurisdiction template skeleton.

The model runs in "thinking mode" — it produces an internal reasoning chain
before the final draft. This reasoning chain is captured and logged.

exports: run_phase3(config) -> dict  — executes synthesis, returns draft metadata
used_by: hoard.cli.run  → orchestrator
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

from hoard.config import Config
from hoard.helpers import load_json_safe, find_json_files, OLLAMA_BASE_URL

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

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
    context_files = find_json_files(digitised_dir)
    if not context_files:
        return "*No context data available.*\n"

    rows: list[list[str]] = []
    for ctx_file in context_files:
        data = load_json_safe(ctx_file)
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
    context_files = find_json_files(digitised_dir)
    relationships: list[str] = []
    relation_count = 0

    for ctx_file in context_files:
        data = load_json_safe(ctx_file)
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
    context_files = find_json_files(digitised_dir)
    all_finds: list[list[str]] = []
    total_finds = 0

    for ctx_file in context_files:
        data = load_json_safe(ctx_file)
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
    context_files = find_json_files(digitised_dir)
    all_samples: list[list[str]] = []

    for ctx_file in context_files:
        data = load_json_safe(ctx_file)
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
    photo_files = find_json_files(spatial_dir)
    if not photo_files:
        return "*No photo data available.*\n"

    captions: list[str] = ["## Photo Captions & Annotations", ""]
    for photo_file in photo_files:
        data = load_json_safe(photo_file)
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


# ── Chunk-and-Merge (Large Sites) ────────────────────────────────────────────

# Threshold: if assembled context exceeds ~70K chars (~17K tokens),
# switch to chunk-and-merge (leaves ~15K tokens for model output)
_CHUNK_THRESHOLD_CHARS = 70000

# Period ordering for chronological narrative (earliest first)
_PERIOD_ORDER = [
    "palaeolithic", "mesolithic", "neolithic", "bronze age",
    "iron age", "roman", "anglo-saxon", "early medieval",
    "saxon", "viking", "medieval", "post-medieval", "modern",
    "undated", "unknown",
]


def _group_contexts_by_period(digitised_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Group Phase 1 context data by period field.

    Returns dict mapping normalised period name → list of context dicts.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for f in find_json_files(digitised_dir):
        data = load_json_safe(f)
        if not data or not data.get("context_number"):
            continue
        period = data.get("period", "undated").lower().strip()
        period = _normalise_period(period)
        if period not in groups:
            groups[period] = []
        groups[period].append(data)
    return groups


def _normalise_period(raw: str) -> str:
    """Normalise a period string to its canonical form.

    Uses exact match first, then common variant mapping.
    Unrecognised periods are returned lowercase as-is (but sorted last).
    """
    raw_lower = raw.lower().strip()
    # Remove common suffixes
    for suffix in (" period", " phase", " era", "-"):
        if raw_lower.endswith(suffix):
            raw_lower = raw_lower[: -len(suffix)].strip()

    # Exact matches in canonical list
    for canonical in _PERIOD_ORDER:
        if raw_lower == canonical:
            return canonical

    # Known aliases
    aliases = {
        "bronze age": "bronze age",
        "prehistoric": "neolithic",  # fallback for generic prehistoric
        "saxon": "anglo-saxon",
        "postmed": "post-medieval",
        "post med": "post-medieval",
        "post-med": "post-medieval",
        "17th c": "post-medieval",
        "18th c": "post-medieval",
        "19th c": "post-medieval",
        "20th c": "modern",
        "21st c": "modern",
        "c19th": "modern",
        "early med": "early medieval",
        "later medieval": "medieval",
        "late med": "medieval",
        "later med": "medieval",
    }
    if raw_lower in aliases:
        return aliases[raw_lower]

    return raw_lower


def _render_period_context_table(contexts: list[dict[str, Any]]) -> str:
    """Render a condensed context table for a single period."""
    lines = [
        "| Context | Type | Description | Interpretation |",
        "|---------|------|-------------|----------------|",
    ]
    for ctx in contexts:
        num = ctx.get("context_number", "?")
        typ = ctx.get("type", "")
        desc = ctx.get("description", "")[:80]
        interp = ctx.get("interpretation", "")[:60]
        lines.append(f"| {num} | {typ} | {desc} | {interp} |")
    return "\n".join(lines)


def _render_period_finds(contexts: list[dict[str, Any]]) -> str:
    """Render finds summary for contexts in one period."""
    from collections import Counter
    find_types: Counter[str] = Counter()
    for ctx in contexts:
        for f in ctx.get("finds", []):
            ft = f.get("type", "unknown")
            qty = f.get("qty", 1)
            try:
                find_types[ft] += int(qty)
            except (ValueError, TypeError):
                find_types[ft] += 1
    if not find_types:
        return ""
    items = ", ".join(f"{v}× {k}" for k, v in find_types.most_common())
    return f"Finds: {items}"


def _render_period_relations(contexts: list[dict[str, Any]]) -> str:
    """Render stratigraphic relationships for contexts in one period."""
    relationships: list[str] = []
    context_nums = {str(c.get("context_number", "")).strip("[]") for c in contexts}
    for ctx in contexts:
        num = ctx.get("context_number", str(ctx.get("context_number")))
        for rel_field, rel_verb in [("cut_by", "cut by"), ("cuts", "cuts")]:
            for other in ctx.get(rel_field, []):
                other_clean = str(other).strip("[]")
                if other_clean in context_nums:
                    relationships.append(f"  {num} {rel_verb} {other}")
    if not relationships:
        return ""
    return "Relationships:\n" + "\n".join(sorted(set(relationships)))


def _assemble_period_context(
    period: str,
    contexts: list[dict[str, Any]],
    metadata: str,
) -> str:
    """Assemble the full context document for a single period."""
    parts = [
        metadata,
        "",
        f"## Period: {period.title()} ({len(contexts)} contexts)",
        "",
        _render_period_context_table(contexts),
        "",
    ]
    finds = _render_period_finds(contexts)
    if finds:
        parts.append(finds)
        parts.append("")
    relations = _render_period_relations(contexts)
    if relations:
        parts.append(relations)
        parts.append("")
    return "\n".join(parts)


def _build_period_drafting_prompt(period: str, context_text: str) -> str:
    """Build the drafting prompt for a single period's stratigraphic narrative."""
    return (
        f"Using the data below, write the stratigraphic narrative for the "
        f"**{period.title()}** period.\n\n"
        f"### Context Data\n\n{context_text}\n\n"
        f"### Instructions\n\n"
        f"Describe all contexts from this period in chronological sequence. "
        f"Cover every context and its relationships. Use standard archaeological "
        f"terminology. Begin with `##section:results_{period}`.\n"
    )


def _build_condensed_overview_prompt(
    period_summaries: list[tuple[str, int, dict[str, int]]],
    site_metadata: str,
) -> str:
    """Build a condensed prompt for the overview sections.

    Uses period summaries (counts + find types) rather than full
    context data to stay within token budget.
    """
    summary_lines = []
    for period, ctx_count, find_counts in period_summaries:
        line = f"- **{period.title()}**: {ctx_count} contexts"
        if find_counts:
            items = ", ".join(f"{v}× {k}" for k, v in find_counts.items())
            line += f". Finds: {items}"
        summary_lines.append(line)

    return (
        "Using the condensed site summary below, write the following report "
        f"sections as a structured Markdown draft.\n\n"
        f"### Site Metadata\n\n{site_metadata}\n\n"
        f"### Period Summary\n\n"
        + "\n".join(summary_lines)
        + "\n\n"
        "### Required Sections\n\n"
        "Write EACH section starting with `##section:{{id}}`. Generate ALL sections listed:\n\n"
        "1. **executive_summary** — 1-2 paragraph summary of the excavation\n"
        "2. **introduction** — Site location, NGR, geology, project background\n"
        "3. **aims_and_objectives** — Research aims and specific objectives\n"
        "4. **methodology** — Excavation strategy, recording system, policies\n"
        "5. **discussion** — Interpretation in local and regional context\n"
        "6. **archive_statement** — Archive deposition and accession details\n"
        "7. **bibliography** — List references cited. If none, note 'No references cited.'\n"
    )


def _merge_chunked_drafts(
    overview_draft: str,
    period_drafts: list[tuple[str, str]],
) -> str:
    """Merge drafted sections from all chunks into a single document.

    Args:
        overview_draft: Draft of non-period sections (exec summary, etc.).
        period_drafts: List of (period_name, draft_text) tuples.

    Returns:
        Merged Markdown document with sections in logical order.
    """
    merged_parts: list[str] = [overview_draft, ""]

    for period_name, draft_text in period_drafts:
        merged_parts.append(draft_text.strip())
        merged_parts.append("")

    return "\n".join(merged_parts)


def _sort_periods(groups: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Sort period names by chronological order."""
    order_map = {p: i for i, p in enumerate(_PERIOD_ORDER)}
    return sorted(groups.keys(), key=lambda p: order_map.get(p, 9999))


# ── Main Entry Point ─────────────────────────────────────────────────────────


def run_phase3(config: Config, model: str = DEFAULT_MODEL) -> dict[str, Any]:
    """Execute Phase 3: Synthesis & Narrative Drafting.

    For small sites (<70K chars context, ~17K tokens), drafts the full report
    in one pass. For large sites, uses chunk-and-merge: groups contexts by
    period, drafts each period's narrative separately, then merges with a
    condensed overview of executive sections.

    Args:
        config: Pipeline configuration.
        model: Ollama model name. Defaults to huihui_ai/qwen3.5-abliterated:4B.

    Returns:
        Dict with keys:
            - 'status': 'complete' | 'failed'
            - 'model': model used
            - 'sections': dict of section_id → content
            - 'reasoning': list of reasoning chains
            - 'triggers': list of review trigger dicts
            - 'draft_path': path to written draft file
            - 'reasoning_path': path to written reasoning log
            - 'total_tokens': int
            - 'duration_ms': int
            - 'chunked': bool (True if chunk-and-merge was used)
    """
    start_time = time.time()

    config.draft_dir.mkdir(parents=True, exist_ok=True)
    config.logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Step 1: Assemble context and check size
    full_context = assemble_context(config)

    # Step 2: Collect context numbers for review triggers
    context_numbers: set[str] = set()
    for f in find_json_files(config.digitised_dir):
        data = load_json_safe(f)
        ctx = data.get("context_number")
        if ctx:
            context_numbers.add(ctx.strip("[]"))

    # ── Chunk-and-merge path (large sites) ──────────────────────────────────
    if len(full_context) > _CHUNK_THRESHOLD_CHARS:
        logger.info(
            f"Context size {len(full_context)} chars exceeds threshold "
            f"{_CHUNK_THRESHOLD_CHARS} — using chunk-and-merge"
        )
        return _run_phase3_chunked(
            config, model, timestamp, context_numbers, start_time
        )

    # ── Single-pass path (standard) ─────────────────────────────────────────
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
        "Required sections (generate EVERY listed section — do not skip any):\n"
        "1. **executive_summary** — 2-3 paragraph summary of the excavation, methods, and key findings\n"
        "2. **introduction** — Site location, NGR, geology, topography, and project background\n"
        "3. **aims_and_objectives** — Research aims and specific objectives of the evaluation\n"
        "4. **methodology** — Excavation strategy, recording system, finds and sampling policy\n"
        "5. **results_by_period** — Phased description of ALL contexts in chronological order, grouped by period where possible. Cover every context from the data.\n"
        "6. **finds_summary** — Overview of recovered finds by category and period\n"
        "7. **environmental_summary** — Summary of environmental samples and results\n"
        "8. **discussion** — Interpretation of the site in its local and regional context\n"
        "9. **archive_statement** — Recommended archive deposition and accession details\n"
        "10. **bibliography** — List all references cited in the text. If none were cited, note 'No references cited.'\n"
    )
    drafting_prompt = drafting_template.format(context=full_context)

    logger.info(f"Calling Ollama model: {model}")
    result = _ollama_generate(
        model=model,
        system=SYSTEM_PROMPT,
        prompt=drafting_prompt,
        temperature=DEFAULT_TEMPERATURE,
    )

    duration_ms = int((time.time() - start_time) * 1000)

    if not result.get("response"):
        return {
            "status": "failed",
            "model": model,
            "error": "Model returned empty response",
            "chunked": False,
        }

    draft_text = result["response"]
    sections = _extract_sections(draft_text)
    triggers = _check_review_triggers(
        draft_text, {"context_numbers": context_numbers}
    )

    draft_path = config.draft_dir / f"draft_{timestamp}.md"
    draft_path.write_text(draft_text)
    logger.info(f"Draft written to {draft_path}")

    reasoning_path = None
    reasoning_chain = result.get("reasoning")
    if reasoning_chain:
        reasoning_path = config.logs_dir / f"phase3_reasoning_{timestamp}.txt"
        reasoning_path.write_text(reasoning_chain)
        logger.info(f"Reasoning chain written to {reasoning_path}")

    return {
        "status": "complete",
        "model": model,
        "sections": sections,
        "reasoning": reasoning_chain,
        "triggers": triggers,
        "draft_path": str(draft_path),
        "reasoning_path": str(reasoning_path) if reasoning_path else None,
        "total_tokens": result.get("eval_count", 0),
        "duration_ms": duration_ms,
        "chunked": False,
    }


def _run_phase3_chunked(
    config: Config,
    model: str,
    timestamp: str,
    context_numbers: set[str],
    start_time: float,
) -> dict[str, Any]:
    """Run Phase 3 using chunk-and-merge for large sites.

    1. Group contexts by period
    2. Draft stratigraphic narrative for each period
    3. Draft overview sections from condensed period summaries
    4. Merge all sections together
    """
    from collections import Counter

    # Group contexts by period
    period_groups = _group_contexts_by_period(config.digitised_dir)
    sorted_periods = _sort_periods(period_groups)

    logger.info(
        f"Chunk-and-merge: {len(sorted_periods)} periods, "
        f"{sum(len(period_groups[p]) for p in sorted_periods)} contexts"
    )

    # Build period summaries for the condensed overview
    period_summaries: list[tuple[str, int, dict[str, int]]] = []
    for period in sorted_periods:
        contexts = period_groups[period]
        find_counts: Counter[str] = Counter()
        for ctx in contexts:
            for f in ctx.get("finds", []):
                ft = f.get("type", "unknown")
                try:
                    find_counts[ft] += int(f.get("qty", 1))
                except (ValueError, TypeError):
                    find_counts[ft] += 1
        period_summaries.append((
            period, len(contexts), dict(find_counts),
        ))

    # Draft overview sections from condensed summaries
    site_metadata = _render_site_metadata(config)
    overview_prompt = _build_condensed_overview_prompt(period_summaries, site_metadata)

    logger.info("Drafting condensed overview sections...")
    overview_result = _ollama_generate(
        model=model,
        system=SYSTEM_PROMPT,
        prompt=overview_prompt,
        temperature=DEFAULT_TEMPERATURE,
    )
    overview_draft = overview_result.get("response", "")

    all_reasoning: list[str] = []
    if overview_result.get("reasoning"):
        all_reasoning.append(f"--- Overview ---\n{overview_result['reasoning']}")

    # Track token usage across all chunks
    total_tokens = overview_result.get("eval_count", 0)

    # Draft each period's narrative
    period_drafts: list[tuple[str, str]] = []
    for period in sorted_periods:
        contexts = period_groups[period]
        period_ctx = _assemble_period_context(
            period, contexts, site_metadata,
        )
        period_prompt = _build_period_drafting_prompt(period, period_ctx)

        logger.info(f"Drafting period: {period} ({len(contexts)} contexts)")
        period_result = _ollama_generate(
            model=model,
            system=SYSTEM_PROMPT,
            prompt=period_prompt,
            temperature=DEFAULT_TEMPERATURE,
        )
        period_text = period_result.get("response", "")
        period_drafts.append((period, period_text))
        total_tokens += period_result.get("eval_count", 0)

        if period_result.get("reasoning"):
            all_reasoning.append(
                f"--- Period: {period} ---\n{period_result['reasoning']}"
            )

    # Merge all drafts
    merged_text = _merge_chunked_drafts(overview_draft, period_drafts)

    duration_ms = int((time.time() - start_time) * 1000)

    # Extract sections and check review triggers
    sections = _extract_sections(merged_text)
    triggers = _check_review_triggers(
        merged_text, {"context_numbers": context_numbers}
    )

    # Write to disk
    draft_path = config.draft_dir / f"draft_{timestamp}.md"
    draft_path.write_text(merged_text)
    logger.info(f"Merged draft written to {draft_path}")

    reasoning_path = None
    if all_reasoning:
        reasoning_path = config.logs_dir / f"phase3_reasoning_{timestamp}.txt"
        reasoning_path.write_text("\n\n".join(all_reasoning))
        logger.info(f"Reasoning chains written to {reasoning_path}")

    return {
        "status": "complete",
        "model": model,
        "sections": sections,
        "reasoning": all_reasoning if all_reasoning else None,
        "triggers": triggers,
        "draft_path": str(draft_path),
        "reasoning_path": str(reasoning_path) if reasoning_path else None,
        "total_tokens": total_tokens,
        "duration_ms": duration_ms,
        "chunked": True,
        "chunk_periods": sorted_periods,
        "chunk_count": len(sorted_periods),
    }
