"""engine.py — Jurisdiction template engine.

Loads YAML templates, validates structure, runs structural compliance
checks (mandatory sections, required fields, prohibited terms, heading
style, caption format). The model-dependent compliance rewriting pass
(Gemma 4-E2B) lives in phases/phase4.py; this engine provides the
deterministic checks that run before and after that pass.

exports: TemplateEngine, ComplianceReport
used_by: erd.phases.phase4, erd.cli.templates
rules:   Must never import torch or any GPU-bound library.
         Template loading must be safe (yaml.safe_load).
         Adding a new jurisdiction must not require code changes.
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Template engine implementation
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# ── Data Structures ─────────────────────────────────────────────────────────


class ComplianceFinding:
    """A single compliance issue found during checking."""

    def __init__(
        self,
        section_id: str,
        finding_type: str,
        severity: str,
        message: str,
        field: str | None = None,
    ) -> None:
        self.section_id = section_id
        self.finding_type = finding_type  # "missing_section" | "missing_field" | "prohibited_term" | "heading_style" | "caption_format"
        self.severity = severity  # "error" | "warning" | "info"
        self.message = message
        self.field = field

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "type": self.finding_type,
            "severity": self.severity,
            "message": self.message,
            "field": self.field,
        }


class ComplianceReport:
    """Complete report of all compliance checks for a draft."""

    def __init__(self, template_code: str) -> None:
        self.template_code = template_code
        self.findings: list[ComplianceFinding] = []
        self.section_status: dict[str, str] = {}  # section_id -> "present" | "missing" | "has_issues"

    def add_finding(self, finding: ComplianceFinding) -> None:
        self.findings.append(finding)

    @property
    def errors(self) -> list[ComplianceFinding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[ComplianceFinding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_code": self.template_code,
            "passed": self.passed,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "findings": [f.to_dict() for f in self.findings],
            "section_status": self.section_status,
        }


# ── Template Engine ─────────────────────────────────────────────────────────


class TemplateEngine:
    """Loads and validates jurisdiction templates; runs structural compliance checks."""

    def __init__(self, template_dir: str | Path | None = None) -> None:
        self.template_dir = Path(template_dir) if template_dir else Path(__file__).parent.parent.parent.parent / "templates"

    # ── Loading ──────────────────────────────────────────────────────────

    def list_templates(self) -> list[dict[str, str]]:
        """List all available templates with code, jurisdiction name, version."""
        results = []
        for yaml_file in sorted(self.template_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text())
                results.append({
                    "code": yaml_file.stem,
                    "jurisdiction": data.get("jurisdiction", "Unknown"),
                    "version": data.get("version", "?"),
                })
            except Exception:
                results.append({
                    "code": yaml_file.stem,
                    "jurisdiction": "Error loading template",
                    "version": "?",
                })
        return results

    def load_template(self, code: str) -> dict[str, Any] | None:
        """Load a jurisdiction template by code. Returns None if not found."""
        path = self.template_dir / f"{code}.yaml"
        if not path.exists():
            return None
        try:
            data = yaml.safe_load(path.read_text())
            if not isinstance(data, dict):
                return None
            return data
        except yaml.YAMLError:
            return None

    def get_extended_template(self, code: str) -> dict[str, Any] | None:
        """Load a template, resolving 'extends' inheritance if present."""
        template = self.load_template(code)
        if template is None:
            return None

        extends = template.get("extends")
        if extends:
            parent = self.load_template(extends)
            if parent:
                template = self._merge_templates(parent, template)

        return template

    @staticmethod
    def _merge_templates(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
        """Merge child template into parent (deep merge). Child values win."""
        merged = {}
        all_keys = set(parent.keys()) | set(child.keys())
        for key in all_keys:
            if key not in parent:
                merged[key] = child[key]
            elif key not in child:
                merged[key] = parent[key]
            elif isinstance(parent[key], list) and isinstance(child[key], list):
                # Lists: child items override parent by matching 'id'
                if all(isinstance(i, dict) and "id" in i for i in parent[key] + child[key]):
                    parent_map = {i["id"]: i for i in parent[key]}
                    child_map = {i["id"]: i for i in child[key]}
                    merged_map = {**parent_map, **child_map}
                    merged[key] = list(merged_map.values())
                else:
                    merged[key] = child[key]
            elif isinstance(parent[key], dict) and isinstance(child[key], dict):
                merged[key] = {**parent[key], **child[key]}
            else:
                merged[key] = child[key]
        return merged

    # ── Structural Checks ────────────────────────────────────────────────

    def check_mandatory_sections(
        self, draft_text: str, template: dict[str, Any], report: ComplianceReport,
    ) -> None:
        """Verify all mandatory sections are present in the draft.

        Sections are identified by `section:<id>` code-block labels (Phase 3 output
        convention) or by ## heading matching.
        """
        sections = template.get("mandatory_sections", [])
        present_sections = self._extract_section_ids(draft_text)

        for section in sections:
            section_id = section["id"]
            label = section.get("label", section_id)

            if section_id in present_sections:
                report.section_status[section_id] = "present"
            else:
                report.section_status[section_id] = "missing"
                report.add_finding(ComplianceFinding(
                    section_id=section_id,
                    finding_type="missing_section",
                    severity="error",
                    message=f"Mandatory section '{label}' ({section_id}) is missing from the draft",
                ))

    def check_required_fields(
        self, draft_text: str, template: dict[str, Any], report: ComplianceReport,
    ) -> None:
        """Check required fields within each section."""
        sections = template.get("mandatory_sections", [])
        section_texts = self._split_by_section(draft_text)

        for section in sections:
            section_id = section["id"]
            required = section.get("required_fields", [])
            if not required:
                continue

            section_text = section_texts.get(section_id, "")
            if not section_text:
                continue

            for field in required:
                field_label = field.replace("_", " ")
                # Check if field appears in section text (heuristically)
                if not self._field_is_addressed(section_text, field_label):
                    report.add_finding(ComplianceFinding(
                        section_id=section_id,
                        finding_type="missing_field",
                        severity="error",
                        message=f"Required field '{field_label}' not addressed",
                        field=field,
                    ))

    def check_prohibited_terms(
        self, draft_text: str, template: dict[str, Any], report: ComplianceReport,
    ) -> None:
        """Scan draft for prohibited terms from the template."""
        prohibited = template.get("prohibited_terms", [])
        alternatives = template.get("preferred_alternatives", {})

        for term in prohibited:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            matches = pattern.findall(draft_text)
            if matches:
                alt = alternatives.get(term, "")
                alt_msg = f" → use '{alt}' instead" if alt else ""
                report.add_finding(ComplianceFinding(
                    section_id="_global",
                    finding_type="prohibited_term",
                    severity="warning",
                    message=f"Prohibited term '{term}' used {len(matches)} time(s){alt_msg}",
                ))

    def check_heading_style(
        self, draft_text: str, template: dict[str, Any], report: ComplianceReport,
    ) -> None:
        """Verify heading capitalisation catches only extreme violations.

        Only flags ALL-CAPS or all-lowercase headings. The nuanced
        sentence-case vs title-case distinction is handled by the
        Phase 4 model compliance pass, not by heuristics.
        """
        headings = re.findall(r"^#{1,3}\s+(.+)$", draft_text, re.MULTILINE)

        for heading in headings:
            stripped = heading.strip()
            # Only flag extreme cases — not worth false positives on
            # standard section names like "Executive Summary"
            if stripped.isupper():
                report.add_finding(ComplianceFinding(
                    section_id="_global",
                    finding_type="heading_style",
                    severity="warning",
                    message=f"Heading '{stripped}' is in ALL CAPS",
                ))
            elif stripped.islower():
                report.add_finding(ComplianceFinding(
                    section_id="_global",
                    finding_type="heading_style",
                    severity="warning",
                    message=f"Heading '{stripped}' is in all lowercase",
                ))

    def check_figure_captions(
        self, draft_text: str, template: dict[str, Any], report: ComplianceReport,
    ) -> None:
        """Verify figure captions match template format."""
        fmt = template.get("figure_caption_format", "Fig. {n}: {description}.")
        # Extract expected prefix from format string (e.g. "Fig." or "Figure")
        prefix_match = re.match(r"^([A-Za-z.]+)", fmt)
        if not prefix_match:
            return
        expected_prefix = prefix_match.group(1)

        # Find existing captions
        caption_pattern = re.compile(
            rf"^{re.escape(expected_prefix)}\s*\d+\s*:\s*.+$", re.MULTILINE | re.IGNORECASE
        )
        non_matching = []
        for line in draft_text.split("\n"):
            line = line.strip()
            if re.match(rf"^(Fig|Figure|Fig\.|Figure\.)\s+\d+", line, re.IGNORECASE):
                if not caption_pattern.match(line):
                    non_matching.append(line)

        for caption in non_matching[:5]:  # Limit to first 5 to avoid noise
            report.add_finding(ComplianceFinding(
                section_id="_global",
                finding_type="caption_format",
                severity="info",
                message=f"Caption format may not match template style: '{caption[:60]}...'",
            ))

    def check_executive_summary_word_count(
        self, draft_text: str, template: dict[str, Any], report: ComplianceReport,
    ) -> None:
        """Check executive summary doesn't exceed max_words."""
        sections = template.get("mandatory_sections", [])
        exec_section = next((s for s in sections if s.get("id") == "executive_summary"), None)
        if not exec_section:
            return

        max_words = exec_section.get("max_words")
        if not max_words:
            return

        section_texts = self._split_by_section(draft_text)
        exec_text = section_texts.get("executive_summary", "")
        if not exec_text:
            return

        word_count = len(exec_text.split())
        if word_count > max_words:
            report.add_finding(ComplianceFinding(
                section_id="executive_summary",
                finding_type="word_count",
                severity="warning",
                message=f"Executive summary is {word_count} words (max: {max_words})",
            ))

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_section_ids(draft_text: str) -> set[str]:
        """Extract section IDs from Phase 3 code-block labels: ```section:<id>."""
        ids: set[str] = set()
        for match in re.finditer(r"```section:(\S+)", draft_text):
            ids.add(match.group(1))
        # Also look for ## Heading fallback
        for match in re.finditer(r"^##\s+(.+)$", draft_text, re.MULTILINE):
            heading = match.group(1).strip().lower()
            # Create a slug ID from the heading
            slug = re.sub(r"[^a-z0-9]+", "_", heading).strip("_")
            ids.add(slug)
        return ids

    @staticmethod
    def _split_by_section(draft_text: str) -> dict[str, str]:
        """Split draft into sections by ```section:<id> markers or ## headings."""
        sections: dict[str, str] = {}
        current_id: str | None = None
        current_lines: list[str] = []

        for line in draft_text.split("\n"):
            section_match = re.match(r"```section:(\S+)", line)
            heading_match = re.match(r"^##\s+(.+)$", line)

            if section_match:
                # Save previous section
                if current_id:
                    sections[current_id] = "\n".join(current_lines).strip()
                current_id = section_match.group(1)
                current_lines = []
            elif heading_match and current_id is None:
                # Heading-based section start
                if current_id:
                    sections[current_id] = "\n".join(current_lines).strip()
                current_id = re.sub(r"[^a-z0-9]+", "_", heading_match.group(1).strip().lower()).strip("_")
                current_lines = []
            else:
                current_lines.append(line)

        # Save last section
        if current_id:
            sections[current_id] = "\n".join(current_lines).strip()

        return sections

    @staticmethod
    def _field_is_addressed(section_text: str, field_label: str) -> bool:
        """Heuristic check if a required field is addressed in section text."""
        # Direct mention of the field label
        if re.search(re.escape(field_label), section_text, re.IGNORECASE):
            return True

        # Common field label variants
        variants = {
            "project_name": ["project name", "project:", "site name"],
            "ngr": ["ngr", "national grid reference", "grid ref", "ngr:"],
            "dates": ["dates?", "fieldwork date", "excavation date", "between"],
            "methodology_summary": ["methodology", "method"],
            "key_findings": ["findings", "result", "identified", "revealed"],
            "site_location": ["location", "site location", "situated"],
            "planning_authority": ["planning authority", "local authority", "council"],
            "her_reference": ["her", "historic environment record", "her ref"],
            "repository": ["repository", "museum", "archive", "deposited"],
        }
        if field_label.replace(" ", "_") in variants:
            for variant in variants[field_label.replace(" ", "_")]:
                if re.search(variant, section_text, re.IGNORECASE):
                    return True

        return False

    # ── Full Check ───────────────────────────────────────────────────────

    def check_all(self, draft_text: str, template_code: str) -> ComplianceReport:
        """Run all structural compliance checks against a template."""
        template = self.get_extended_template(template_code)
        report = ComplianceReport(template_code)

        if template is None:
            report.add_finding(ComplianceFinding(
                section_id="_global",
                finding_type="template_load",
                severity="error",
                message=f"Template '{template_code}' not found or invalid",
            ))
            return report

        self.check_mandatory_sections(draft_text, template, report)
        self.check_required_fields(draft_text, template, report)
        self.check_prohibited_terms(draft_text, template, report)
        self.check_heading_style(draft_text, template, report)
        self.check_figure_captions(draft_text, template, report)
        self.check_executive_summary_word_count(draft_text, template, report)

        return report
