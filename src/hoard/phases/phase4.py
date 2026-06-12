"""phase4.py — Compliance Refinement.

Takes the Phase 3 structured Markdown draft and runs it through a
compliance pass driven by a jurisdiction template. Uses Gemma 4-E2B
(section-by-section) to restructure, relabel, and fill missing mandatory
fields — without adding interpretive content.

Model is NOT fine-tuned — this avoids obsolescence when templates change.
Instead, uses prompt engineering + RAG over current guideline PDFs.

exports: run_phase4(config) -> dict  — executes compliance pass
used_by: hoard.cli.run  → orchestrator
rules:   Never add factual claims not present in the Phase 3 draft.
         Section-by-section processing (not whole draft at once).
         Temperature 0.1 for near-deterministic editing.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from hoard.config import Config

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

DEFAULT_MODEL = "tripolskypetr/gemma4-uncensored-aggressive:latest"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_TIMEOUT = 120  # 2 minutes per section

# ── Template Loading ────────────────────────────────────────────────────────


def _load_template(template_name: str) -> dict[str, Any] | None:
    """Load a jurisdiction template YAML file.

    Searches the project templates/ directory for {template_name}.yaml.
    """
    search_paths = [
        Path("templates") / f"{template_name}.yaml",
        Path(__file__).resolve().parent.parent.parent.parent / "templates" / f"{template_name}.yaml",
    ]
    for path in search_paths:
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f)
    return None


def _interpolate_defaults(
    defaults: dict[str, str],
    config: Any,
) -> dict[str, str]:
    """Replace {project_id}, {project_name}, {current_date} in default values."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = {}
    for key, value in defaults.items():
        value = value.replace("{project_id}", getattr(config, "project_id", "unknown"))
        value = value.replace("{project_name}", getattr(config, "project_name", "Excavation"))
        value = value.replace("{current_date}", now)
        result[key] = value.strip()
    return result


def _find_latest_draft(draft_dir: Path) -> str | None:
    """Find the most recent Phase 3 draft in the draft directory."""
    draft_files = sorted(draft_dir.glob("draft_*.md"), reverse=True)
    if not draft_files:
        return None
    return draft_files[0].read_text()


def _parse_sections_from_draft(draft_text: str) -> dict[str, str]:
    """Extract labelled sections from the Phase 3 draft.

    Sections are marked with `##section:{section_id}`.
    """
    sections: dict[str, str] = {}
    current_section: str | None = None
    current_lines: list[str] = []

    for line in draft_text.split("\n"):
        section_match = re.match(r"^##section:(\S+)", line.strip())
        if section_match:
            if current_section is not None:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = section_match.group(1)
            current_lines = [line]
        elif current_section is not None:
            current_lines.append(line)

    if current_section is not None:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections


# ── Ollama API ────────────────────────────────────────────────────────────────


def _ollama_generate(
    model: str,
    system: str,
    prompt: str,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Call the LLM via the provider abstraction. Returns response text."""
    from hoard.helpers import generate_via_provider

    result = generate_via_provider(
        model=model,
        system=system,
        prompt=prompt,
        phase=4,
        temperature=temperature,
        num_ctx=16384,
        timeout=timeout,
    )
    return result["response"]


# ── Compliance Checks ────────────────────────────────────────────────────────


def _build_compliance_prompt(
    section_id: str,
    section_label: str,
    section_content: str,
    required_fields: list[str] | None,
    prohibited_terms: list[str] | None,
    field_defaults: dict[str, str] | None = None,
) -> str:
    """Build a prompt for the compliance model for a single section."""
    prompt_parts = [
        f"You are an editor ensuring an archaeological report section conforms to the {section_label} template.\n",
        "Your task: restructure the provided section draft to match the required fields below.\n",
        "Do NOT add factual claims not present in the draft.\n",
        "If a required field is missing content, check if a template default exists below.\n"
        "  - If a default IS listed: use the default value instead of [MISSING].\n"
        "  - If no default is listed: insert [MISSING: field_name].\n",
        "Replace prohibited terms with the preferred alternatives.\n",
        "Output ONLY the corrected section — no commentary, no meta-text.\n",
    ]

    if required_fields:
        prompt_parts.append("\nRequired fields for this section:\n")
        for field in required_fields:
            prompt_parts.append(f"  - {field}")

    if field_defaults:
        prompt_parts.append("\nDefault values for missing fields:\n")
        for field, default in field_defaults.items():
            prompt_parts.append(f"  {field}: {default}")

    if prohibited_terms:
        prompt_parts.append("\nProhibited terms (replace if found):\n")
        for term in prohibited_terms:
            prompt_parts.append(f"  - {term}")

    prompt_parts.append(f"\n### Section: {section_label}\n\n")
    prompt_parts.append(section_content)
    prompt_parts.append(f"\n\n### Corrected Section\n\n##section:{section_id}")

    return "\n".join(prompt_parts)


def _check_prohibited_terms(
    text: str,
    prohibited_terms: list[str] | None,
) -> list[dict[str, str]]:
    """Check text for prohibited terms and return flags."""
    flags: list[dict[str, str]] = []
    if not prohibited_terms:
        return flags

    for term in prohibited_terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        for match in pattern.finditer(text):
            flags.append({
                "term": term,
                "context": text[max(0, match.start() - 40): match.end() + 40],
            })
    return flags


def _count_words(text: str) -> int:
    """Count words in a text string."""
    return len(text.split())


# ── Main Entry Point ─────────────────────────────────────────────────────────


def run_phase4(
    config: Config,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """Execute Phase 4: Compliance Refinement.

    Args:
        config: Pipeline configuration.
        model: Ollama model for compliance editing.

    Returns:
        Dict with:
            - 'status': 'complete' | 'failed' | 'no_draft'
            - 'sections': dict of section_id → corrected content
            - 'missing_sections': list of sections not found in draft
            - 'prohibited_flags': list of prohibited term violations
            - 'compliant_path': path to written compliant report
            - 'placeholder_count': int — number of [MISSING:] placeholders
    """
    start_time = time.time()

    # Step 1: Load jurisdiction template
    template = _load_template(config.jurisdiction)
    if template is None:
        # Fall back to a generic template
        logger.warning(f"Template '{config.jurisdiction}' not found, using generic")
        template = {
            "jurisdiction": "Generic",
            "version": "1.0",
            "mandatory_sections": [
                {"id": "executive_summary", "label": "Executive Summary"},
                {"id": "introduction", "label": "Introduction"},
                {"id": "methodology", "label": "Methodology"},
                {"id": "stratigraphic_narrative", "label": "Stratigraphic Narrative"},
                {"id": "finds_summary", "label": "Finds Summary"},
                {"id": "discussion", "label": "Discussion"},
                {"id": "archive_statement", "label": "Archive Statement"},
            ],
            "prohibited_terms": [],
        }

    prohibited_terms = template.get("prohibited_terms", [])
    field_defaults = _interpolate_defaults(template.get("field_defaults", {}), config)

    # Step 2: Find and parse Phase 3 draft
    draft_text = _find_latest_draft(config.draft_dir)
    if draft_text is None:
        return {
            "status": "no_draft",
            "error": "No Phase 3 draft found. Run Phase 3 first.",
        }

    draft_sections = _parse_sections_from_draft(draft_text)

    # Step 3: Process each mandatory section
    config.refined_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    compliant_sections: dict[str, str] = {}
    missing_sections: list[str] = []
    all_prohibited_flags: list[dict[str, str]] = []
    placeholder_count = 0

    mandatory_sections = template.get("mandatory_sections", [])

    for sec_def in mandatory_sections:
        sec_id = sec_def["id"]
        sec_label = sec_def.get("label", sec_id)
        required_fields = sec_def.get("required_fields")
        max_words = sec_def.get("max_words")

        if sec_id in draft_sections:
            content = draft_sections[sec_id]
        else:
            missing_sections.append(sec_id)
            content = f"*[MISSING: {sec_id} — no content in Phase 3 draft]*"
            placeholder_count += 1
            compliant_sections[sec_id] = content
            continue

        # Check prohibited terms in the original draft section
        violations = _check_prohibited_terms(content, prohibited_terms)
        all_prohibited_flags.extend(
            {"section": sec_id, **v} for v in violations
        )

        # Send to compliance model for restructuring
        prompt = _build_compliance_prompt(
            section_id=sec_id,
            section_label=sec_label,
            section_content=content,
            required_fields=required_fields,
            prohibited_terms=prohibited_terms,
            field_defaults=field_defaults,
        )

        logger.info(f"Compliance pass for section '{sec_id}'")

        try:
            corrected = _ollama_generate(
                model=model,
                system="You are an archaeological report editor. Restructure sections to match template requirements. Never add factual content. Output only the corrected text.",
                prompt=prompt,
                temperature=DEFAULT_TEMPERATURE,
                timeout=120,
            )
        except RuntimeError as e:
            logger.warning(f"Compliance model failed for '{sec_id}': {e}")
            corrected = content  # Use original if model fails

        # Check for placeholders in corrected output
        new_placeholders = len(re.findall(r"\[MISSING:", corrected))
        placeholder_count += new_placeholders

        # Check prohibited terms in the corrected output too
        new_violations = _check_prohibited_terms(corrected, prohibited_terms)
        all_prohibited_flags.extend(
            {"section": sec_id, **v} for v in new_violations
        )

        # Enforce max_words if specified
        if max_words and _count_words(corrected) > max_words:
            logger.info(f"Section '{sec_id}' exceeds {max_words} words, truncating")
            words = corrected.split()
            corrected = " ".join(words[:max_words]) + "\n\n*[Note: truncated to word limit]*"
            placeholder_count += 1

        compliant_sections[sec_id] = corrected

    # Step 4: Add any draft sections not in the template
    for sec_id, content in draft_sections.items():
        if sec_id not in compliant_sections:
            compliant_sections[sec_id] = content

    # Step 5: Write compliant report
    report_lines: list[str] = []
    for sec_def in mandatory_sections:
        sec_id = sec_def["id"]
        if sec_id in compliant_sections:
            report_lines.append(compliant_sections[sec_id])
            report_lines.append("")

    # Add extra sections after mandatory ones
    for sec_id, content in compliant_sections.items():
        if sec_id not in {s["id"] for s in mandatory_sections}:
            report_lines.append(content)
            report_lines.append("")

    compliant_text = "\n".join(report_lines).strip()
    compliant_path = config.refined_dir / f"compliant_{timestamp}.md"
    compliant_path.write_text(compliant_text)

    # Step 6: Log prohibited terms that couldn't be auto-replaced
    if all_prohibited_flags:
        prohibited_log = config.logs_dir / f"phase4_prohibited_terms_{timestamp}.txt"
        log_lines = ["Prohibited Terms Found:", ""]
        for flag in all_prohibited_flags:
            log_lines.append(f"  Term: '{flag['term']}'")
            log_lines.append(f"  Section: {flag.get('section', '?')}")
            log_lines.append(f"  Context: ...{flag['context']}...")
            log_lines.append("")
        prohibited_log.write_text("\n".join(log_lines))
        logger.warning(f"Found {len(all_prohibited_flags)} prohibited term(s)")

    duration_ms = int((time.time() - start_time) * 1000)

    result: dict[str, Any] = {
        "status": "complete",
        "model": model,
        "template": template.get("jurisdiction", "unknown"),
        "template_version": template.get("version", "?"),
        "sections": compliant_sections,
        "missing_sections": missing_sections,
        "prohibited_flags": all_prohibited_flags,
        "placeholder_count": placeholder_count,
        "compliant_path": str(compliant_path),
        "duration_ms": duration_ms,
    }

    return result
