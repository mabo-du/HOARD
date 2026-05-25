"""phase5.py — Assembly & Export.

Rule-based phase that compiles the compliant Markdown sections, embeds
figures, generates appendices, builds the Harris Matrix, creates the
bibliography, and exports the final report in DOCX/PDF/TEI-XML formats.
Zero VRAM cost.

exports: run_phase5(config) -> dict  — executes assembly and export
used_by: erd.cli.run  → orchestrator
rules:   Must never import torch or any GPU-bound library.
         DOCX is generated via python-docx (no pandoc needed).
         PDF/A-2b is generated via WeasyPrint (no xelatex/wkhtmltopdf).
         Photo plates use rectpack 2D bin-packing (CPU only).
license: MIT
"""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from erd.config import Config
from erd.export.docx_writer import write_docx
from erd.export.pdf_writer import write_pdf
from erd.export.photo_plates import write_photo_plates

# ── Helpers ─────────────────────────────────────────────────────────────────


def _load_json_safe(path: Path) -> dict[str, Any]:
    """Load JSON file, returning empty dict if missing or corrupt."""
    try:
        if path.exists():
            return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _find_json_files(directory: Path, pattern: str = "*.json") -> list[Path]:
    """Find JSON files in a directory, sorted by name."""
    if not directory.is_dir():
        return []
    return sorted(directory.glob(pattern))


# ── Figure Resolution ────────────────────────────────────────────────────────


def _resolve_figures(draft_text: str, assets_dir: Path, refined_dir: Path) -> str:
    """Replace [FIG:filename] tokens with embedded Markdown images.

    Looks for the image file first in assets/, then in refined/.
    """
    def _replace_fig(match: re.Match) -> str:
        fig_ref = match.group(1)
        stem = fig_ref.replace("FIG:", "").replace("fig:", "").strip()
        # Try common extensions
        for ext in (".png", ".jpg", ".jpeg", ".svg", ".gif"):
            for base in (assets_dir, refined_dir):
                candidate = base / f"{stem}{ext}"
                if candidate.exists():
                    return f"![{stem}]({candidate.resolve()}){{ width=100% }}"
        # If no image found, return a placeholder
        return f"*[Image: {stem} — not found]*"

    return re.sub(r"\[(FIG:[^\]]+)\]", _replace_fig, draft_text, flags=re.IGNORECASE)


# ── Appendix Generation ─────────────────────────────────────────────────────


def _generate_context_register(digitised_dir: Path) -> str:
    """Generate Context Register appendix from Phase 1 JSON files."""
    context_files = _find_json_files(digitised_dir)
    if not context_files:
        return "*No context data available.*\n\n"

    rows: list[list[str]] = []
    for ctx_file in context_files:
        data = _load_json_safe(ctx_file)
        ctx_num = data.get("context_number", str(ctx_file.stem))
        ctx_type = data.get("type", "")
        description = data.get("description", "")[:80]
        interpretation = data.get("interpretation", "")[:60]
        period = data.get("period", "")
        rows.append([ctx_num, ctx_type, description, interpretation, period])

    if not rows:
        return "*No context data available.*\n\n"

    # Simple Markdown table
    lines = [
        "| Context | Type | Description | Interpretation | Period |",
        "|---------|------|-------------|----------------|--------|",
    ]
    for row in rows:
        escaped = [c.replace("|", "\\|") for c in row]
        lines.append(f"| {' | '.join(escaped)} |")

    return "\n".join(lines) + "\n\n"


def _generate_finds_concordance(digitised_dir: Path) -> str:
    """Generate Finds Concordance appendix from Phase 1 JSON files."""
    context_files = _find_json_files(digitised_dir)
    if not context_files:
        return "*No finds data available.*\n\n"

    rows: list[list[str]] = []
    for ctx_file in context_files:
        data = _load_json_safe(ctx_file)
        ctx_num = data.get("context_number", str(ctx_file.stem))
        finds = data.get("finds", [])
        for find in finds:
            find_type = find.get("type", "")
            qty = str(find.get("qty", ""))
            period = find.get("period", "")
            notes = find.get("notes", "")[:50]
            rows.append([ctx_num, find_type, qty, period, notes])

    if not rows:
        return "*No finds data available.*\n\n"

    lines = [
        "| Context | Find Type | Quantity | Period | Notes |",
        "|---------|-----------|----------|--------|-------|",
    ]
    for row in rows:
        escaped = [c.replace("|", "\\|") for c in row]
        lines.append(f"| {' | '.join(escaped)} |")

    return "\n".join(lines) + "\n\n"


def _generate_sample_register(digitised_dir: Path) -> str:
    """Generate Sample Register appendix from Phase 1 JSON files."""
    context_files = _find_json_files(digitised_dir)
    if not context_files:
        return "*No sample data available.*\n\n"

    rows: list[list[str]] = []
    for ctx_file in context_files:
        data = _load_json_safe(ctx_file)
        ctx_num = data.get("context_number", str(ctx_file.stem))
        samples = data.get("samples", [])
        for sample in samples:
            sample_id = sample.get("id", "")
            sample_type = sample.get("type", "")
            sample_notes = sample.get("notes", "")[:60]
            rows.append([ctx_num, sample_id, sample_type, sample_notes])

    if not rows:
        return "*No sample data available.*\n\n"

    lines = [
        "| Context | Sample ID | Type | Notes |",
        "|---------|-----------|------|-------|",
    ]
    for row in rows:
        escaped = [c.replace("|", "\\|") for c in row]
        lines.append(f"| {' | '.join(escaped)} |")

    return "\n".join(lines) + "\n\n"


# ── Harris Matrix ────────────────────────────────────────────────────────────


def _generate_harris_matrix_svg(context_jsons: list[dict[str, Any]]) -> str | None:
    """Generate a Harris Matrix SVG from stratigraphic relationships.

    Uses the pure-Python Harris Matrix renderer (no graphviz needed).
    Returns SVG string on success, None if no relationships exist.

    Relationships are derived from context JSON 'cut_by', 'cuts', 'fills',
    'filled_by', and 'same_as' fields.
    """
    if not context_jsons:
        return None

    from erd.review.harris import build_matrix_from_contexts, render_harris_svg

    nodes = build_matrix_from_contexts(context_jsons)
    if not nodes:
        return None
    return render_harris_svg(nodes, title="Harris Matrix")


# ── Bibliography ─────────────────────────────────────────────────────────────


def _generate_bibliography(draft_text: str) -> str:
    """Extract citations from draft text and generate a bibliography.

    Supports author_date style: (Author, year) or (Author year)
    """
    citations: dict[str, dict[str, Any]] = {}
    # Find citation patterns: (Surname, YYYY) or (Surname YYYY)
    patterns = [
        r"\(([A-Z][a-zéèêëàâäùûüôöîïç]+(?: et al\.)?),?\s+(\d{4}[a-z]?)\)",
        r"\(([A-Z][a-zéèêëàâäùûüôöîïç]+)\s+(\d{4}[a-z]?)\)",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, draft_text):
            author = match.group(1)
            year = match.group(2)
            key = f"{author}, {year}"
            if key not in citations:
                citations[key] = {"author": author, "year": year, "count": 0}
            citations[key]["count"] += 1

    if not citations:
        return "*No citations found in draft.*\n\n"

    lines = [
        "## References",
        "",
    ]
    for key in sorted(citations.keys()):
        entry = citations[key]
        lines.append(f"{entry['author']} ({entry['year']}). *[Title — populated from citation context]*.")
        lines.append("")

    return "\n".join(lines)


# ── Assembly ─────────────────────────────────────────────────────────────────


def assemble_report(
    config: Config,
    digitised_dir: Path | None = None,
) -> tuple[str, dict[str, str]]:
    """Assemble the final report from Phase 4 refined Markdown sections.

    Returns (full_report_markdown, {appendix_id: appendix_markdown}).
    """
    refined_dir = config.refined_dir
    assets_dir = config.assets_dir

    # Use provided digitised_dir or default
    dig_dir = digitised_dir or config.digitised_dir

    # Step 1: Load refined sections
    section_files = _find_json_files(refined_dir, "*.md")
    section_text = ""
    if section_files:
        section_text = section_files[-1].read_text()  # Most recent refined file
    else:
        # Fallback: read all .md files in order
        section_text = ""
        for f in sorted(refined_dir.glob("*.md")):
            section_text += f.read_text() + "\n\n"

    if not section_text.strip():
        section_text = "*No refined draft available. Run Phase 4 first.*\n\n"

    # Step 2: Resolve figure references
    section_text = _resolve_figures(section_text, assets_dir, refined_dir)

    # Step 3: Generate appendices
    appendices: dict[str, str] = {}

    appendices["context_register"] = _generate_context_register(dig_dir)
    appendices["finds_concordance"] = _generate_finds_concordance(dig_dir)
    appendices["sample_register"] = _generate_sample_register(dig_dir)

    # Step 4: Collect context JSON for Harris Matrix
    context_jsons: list[dict[str, Any]] = []
    for f in _find_json_files(dig_dir):
        data = _load_json_safe(f)
        if data.get("context_number"):
            context_jsons.append(data)

    # Step 5: Generate Harris Matrix
    harris_svg = _generate_harris_matrix_svg(context_jsons)
    if harris_svg:
        config.final_dir.mkdir(parents=True, exist_ok=True)
        (config.final_dir / "harris_matrix.svg").write_text(harris_svg)

    # Step 6: Generate photo plates from assets (only Phase 2-processed images)
    photo_plates_md = write_photo_plates(assets_dir, spatial_dir=config.spatial_dir)
    if photo_plates_md:
        appendices["photo_plates"] = photo_plates_md

    # Step 7: Generate bibliography
    bibliography = _generate_bibliography(section_text)

    # Step 7: Compile final Markdown
    final_md = _compile_markdown(section_text, appendices, bibliography)

    return final_md, appendices


def _compile_markdown(
    body: str,
    appendices: dict[str, str],
    bibliography: str,
) -> str:
    """Compile all sections into a single final Markdown document."""
    parts = [
        "---",
        "title: Excavation Report",
        f"date: {datetime.now(timezone.utc).strftime('%B %Y')}",
        "---",
        "",
        body.strip(),
        "",
        "---",
        "## Bibliography",
        "",
        bibliography,
        "---",
        "## Appendices",
        "",
    ]

    appendix_labels = {
        "context_register": "Appendix 1: Context Register",
        "finds_concordance": "Appendix 2: Finds Concordance",
        "sample_register": "Appendix 3: Sample Register",
    }

    # Add photo plates appendix if present
    if "photo_plates" in appendices:
        appendix_labels["photo_plates"] = "Appendix 4: Photo Plates"

    for app_id, label in appendix_labels.items():
        content = appendices.get(app_id, "")
        if content and not content.startswith("*No"):
            parts.append(f"### {label}")
            parts.append("")
            parts.append(content)

    return "\n".join(parts)


# ── Export ───────────────────────────────────────────────────────────────────


def export_report(
    final_md: str,
    config: Config,
    appendices: dict[str, str] | None = None,
    formats: list[str] | None = None,
) -> dict[str, Path | None]:
    """Export the final Markdown report to requested formats.

    Args:
        final_md: The complete Markdown report string.
        config: Pipeline configuration.
        appendices: Appendix dict (for docx writer).
        formats: List of formats ('docx', 'pdf', 'tei-xml', 'zip').
                 Defaults to ['docx', 'pdf', 'zip'].

    Returns:
        Dict mapping format names to output file paths (or None on failure).
    """
    if formats is None:
        formats = ["docx", "pdf", "zip"]

    final_dir = config.final_dir
    final_dir.mkdir(parents=True, exist_ok=True)

    # Write the Markdown source
    md_path = final_dir / "report.md"
    md_path.write_text(final_md)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results: dict[str, Path | None] = {"markdown": md_path.resolve()}

    # Load jurisdiction template for metadata
    template_yaml = _load_template_yaml(config)
    project_name = _get_project_name(config, template_yaml)
    jurisdiction_label = _get_jurisdiction_label(config, template_yaml)

    # ── DOCX export (via python-docx) ──
    if "docx" in formats:
        docx_path = final_dir / f"report_{timestamp}.docx"
        try:
            write_docx(
                md_text=final_md,
                output_path=docx_path,
                project_name=project_name,
                jurisdiction=jurisdiction_label,
                appendices=appendices,
                template_yaml=template_yaml,
            )
            results["docx"] = docx_path.resolve() if docx_path.exists() else None
        except ImportError:
            results["docx"] = None
        except Exception:
            results["docx"] = None

    # ── PDF/A-2b export (via WeasyPrint) ──
    if "pdf" in formats:
        pdf_path = final_dir / f"report_{timestamp}.pdf"
        try:
            write_pdf(
                md_text=final_md,
                output_path=pdf_path,
                project_name=project_name,
                jurisdiction=jurisdiction_label,
                pdfa_level="pdf/a-2b",
            )
            results["pdf"] = pdf_path.resolve() if pdf_path.exists() else None
        except ImportError:
            results["pdf"] = None
        except Exception:
            results["pdf"] = None

    # ── Signed PDF (optional — requires pyHanko + signing key) ──
    if "signed-pdf" in formats:
        from erd.export.signatures import sign_pdf, has_signing_key
        pdf_out = results.get("pdf")
        if pdf_out and has_signing_key():
            signed_path = sign_pdf(Path(str(pdf_out)))
            results["signed-pdf"] = signed_path.resolve() if signed_path else None
        else:
            results["signed-pdf"] = None

    # ── TEI-XML export ──
    if "tei-xml" in formats:
        tei_path = final_dir / f"report_{timestamp}.xml"
        _generate_tei_xml(final_md, tei_path, project_name)
        results["tei-xml"] = tei_path.resolve() if tei_path.exists() else None

    # ── Archive ZIP ──
    if "zip" in formats:
        zip_path = final_dir / f"archive_{timestamp}.zip"
        _create_archive_zip(config, zip_path, md_path)
        results["zip"] = zip_path.resolve() if zip_path.exists() else None

    return results


def _load_template_yaml(config: Config) -> dict[str, Any] | None:
    """Load the jurisdiction template YAML if available."""
    try:
        import yaml
        template_path = config.project_dir / "config.yaml"
        if template_path.exists():
            data = yaml.safe_load(template_path.read_text())
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return None


def _get_project_name(config: Config, template_yaml: dict[str, Any] | None) -> str:
    """Extract project name from config or template."""
    name = getattr(config, "project_name", "")
    if not name and template_yaml:
        name = template_yaml.get("project_name", "")
    return name or "Excavation Report"


def _get_jurisdiction_label(config: Config, template_yaml: dict[str, Any] | None) -> str:
    """Extract jurisdiction label from config or template."""
    jur = getattr(config, "jurisdiction", "")
    if not jur and template_yaml:
        jur = template_yaml.get("jurisdiction", "")
    return jur or ""


def _generate_tei_xml(md_text: str, output_path: Path, project_name: str) -> None:
    """Generate a lightweight TEI-XML wrapper from the Markdown body."""
    import html as html_mod

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    body_html = html_mod.escape(md_text[:50000])

    tei = f"""<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="http://www.tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>{html_mod.escape(project_name)}</title>
        <respStmt>
          <resp>Generated by</resp>
          <name>HOARD Archaeological Report Pipeline</name>
        </respStmt>
      </titleStmt>
      <publicationStmt>
        <publisher>HOARD</publisher>
        <date>{date_str}</date>
      </publicationStmt>
      <sourceDesc>
        <p>Born-digital archaeological report</p>
      </sourceDesc>
    </fileDesc>
  </teiHeader>
  <text>
    <body>
      <p>{body_html}</p>
    </body>
  </text>
</TEI>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(tei)


# ── ZIP Archive ──────────────────────────────────────────────────────────────


def _create_archive_zip(config: Config, zip_path: Path, md_path: Path) -> None:
    """Package all pipeline outputs into a ZIP archive."""
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add final report
            if md_path.exists():
                zf.write(md_path, "report.md")

            # Add refined draft
            for f in sorted(config.refined_dir.glob("*.md")):
                zf.write(f, f"refined/{f.name}")

            # Add digitised data
            for f in _find_json_files(config.digitised_dir):
                zf.write(f, f"digitised/{f.name}")

            # Add spatial data
            for f in sorted(config.spatial_dir.rglob("*")):
                if f.is_file():
                    zf.write(f, f"spatial/{f.relative_to(config.spatial_dir)}")

            # Add pipeline state
            state_file = config.project_dir / "pipeline_state.json"
            if state_file.exists():
                zf.write(state_file, "pipeline_state.json")

            # Add manifest
            manifest_file = config.manifest_dir / "manifest.json"
            if manifest_file.exists():
                zf.write(manifest_file, "manifest.json")

            # Add Harris Matrix
            harris_svg = config.final_dir / "harris_matrix.svg"
            if harris_svg.exists():
                zf.write(harris_svg, "harris_matrix.svg")

            # Add logs
            for f in sorted(config.logs_dir.glob("*")):
                if f.is_file():
                    zf.write(f, f"logs/{f.name}")
    except (OSError, zipfile.BadZipFile):
        pass


# ── Main entry point ─────────────────────────────────────────────────────────


def run_phase5(config: Config, formats: list[str] | None = None) -> dict[str, Any]:
    """Execute Phase 5: Assembly & Export.

    Returns a summary dict with paths to generated outputs.
    """
    if formats is None:
        formats = ["docx", "pdf", "zip"]

    final_dir = config.final_dir
    final_dir.mkdir(parents=True, exist_ok=True)

    # Assemble the report
    final_md, appendices = assemble_report(config)

    # Export
    export_paths = export_report(final_md, config, appendices=appendices, formats=formats)

    result: dict[str, Any] = {
        "report_markdown": str(export_paths.get("markdown", "")),
        "export_paths": {k: str(v) for k, v in export_paths.items() if v is not None},
        "appendices_generated": [k for k, v in appendices.items() if v and not v.startswith("*No")],
        "harris_matrix": str((config.final_dir / "harris_matrix.svg").resolve()
                            if (config.final_dir / "harris_matrix.svg").exists() else ""),
    }

    return result
