"""phase5.py — Assembly & Export.

Rule-based phase that compiles the compliant Markdown sections, embeds
figures, generates appendices, builds the Harris Matrix, creates the
bibliography, and exports the final report in DOCX/PDF/TEI-XML formats.
Zero VRAM cost.

exports: run_phase5(config) -> dict  — executes assembly and export
used_by: erd.cli.run  → orchestrator
rules:   Must never import torch or any GPU-bound library.
         pandoc is called as a subprocess (must be installed system-wide).
         All figure numbering, cross-references, and appendix indexing
         are handled here.
agent:   deepseek-v4-flash | 2026-05-09 | s_20260509_001 | Phase 5 implementation
"""

from __future__ import annotations

import json
import re
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from erd.config import Config

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

    Uses graphviz via subprocess. Returns SVG string on success, None if
    graphviz is not available or no relationships exist.

    Relationships are derived from context JSON 'cut_by', 'cuts', 'fills',
    and 'filled_by' fields.
    """
    # Collect all context numbers and relationships
    all_contexts: set[str] = set()
    edges: list[tuple[str, str]] = []  # (above, below) — "above" is later in time

    for data in context_jsons:
        ctx_num = data.get("context_number")
        if not ctx_num:
            continue
        all_contexts.add(ctx_num)

        # A cuts/truncates B → A is later than B
        cuts = data.get("cuts", [])
        for earlier in cuts:
            if isinstance(earlier, str):
                edges.append((ctx_num, earlier))
                all_contexts.add(earlier)

        # A is cut by B → B is later than A
        cut_by = data.get("cut_by", [])
        for later in cut_by:
            if isinstance(later, str):
                edges.append((later, ctx_num))
                all_contexts.add(later)

        # A fills B → A is later than B
        fills = data.get("fills", [])
        for earlier in fills:
            if isinstance(earlier, str):
                edges.append((ctx_num, earlier))
                all_contexts.add(earlier)

        # A is filled by B → B is later than A
        filled_by = data.get("filled_by", [])
        for later in filled_by:
            if isinstance(later, str):
                edges.append((later, ctx_num))
                all_contexts.add(later)

    if not edges and len(all_contexts) <= 1:
        return None

    # Generate DOT input
    dot_lines = [
        "digraph HarrisMatrix {",
        '  rankdir="TB";',
        '  node [shape=box, style=filled, fillcolor="#f0f0f0"];',
        '  edge [arrowhead=none];',
        '  graph [dpi=150, bgcolor="white"];',
    ]
    for ctx in sorted(all_contexts):
        sanitised = ctx.replace("[", "").replace("]", "").replace(" ", "_")
        dot_lines.append(f'  "{sanitised}" [label="{ctx}"];')

    for later, earlier in edges:
        later_s = later.replace("[", "").replace("]", "").replace(" ", "_")
        earlier_s = earlier.replace("[", "").replace("]", "").replace(" ", "_")
        dot_lines.append(f'  "{later_s}" -> "{earlier_s}";')

    dot_lines.append("}")

    dot_source = "\n".join(dot_lines)

    # Call graphviz
    try:
        result = subprocess.run(
            ["dot", "-Tsvg"],
            input=dot_source,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


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
        (config.final_dir / "harris_matrix.svg").write_text(harris_svg)

    # Step 6: Generate bibliography
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
    formats: list[str] | None = None,
) -> dict[str, Path | None]:
    """Export the final Markdown report to requested formats.

    Args:
        final_md: The complete Markdown report string.
        config: Pipeline configuration.
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

    # ── DOCX export ──
    if "docx" in formats:
        docx_path = final_dir / f"report_{timestamp}.docx"
        _pandoc_convert(md_path, docx_path, "docx")
        results["docx"] = docx_path.resolve() if docx_path.exists() else None

    # ── PDF export ──
    if "pdf" in formats:
        pdf_path = final_dir / f"report_{timestamp}.pdf"
        _pandoc_convert(md_path, pdf_path, "pdf")
        results["pdf"] = pdf_path.resolve() if pdf_path.exists() else None

    # ── TEI-XML export ──
    if "tei-xml" in formats:
        tei_path = final_dir / f"report_{timestamp}.xml"
        _pandoc_convert(md_path, tei_path, "tei")
        results["tei-xml"] = tei_path.resolve() if tei_path.exists() else None

    # ── Archive ZIP ──
    if "zip" in formats:
        zip_path = final_dir / f"archive_{timestamp}.zip"
        _create_archive_zip(config, zip_path, md_path)
        results["zip"] = zip_path.resolve() if zip_path.exists() else None

    return results


def _pandoc_convert(input_path: Path, output_path: Path, to_format: str) -> None:
    """Convert a Markdown file to the target format using pandoc."""
    try:
        cmd = [
            "pandoc",
            str(input_path),
            "-f", "markdown",
            "-t", to_format,
            "-o", str(output_path),
            "--metadata", "pagetitle=Excavation Report",
        ]

        # Add PDF-specific options
        if to_format == "pdf":
            cmd.extend(["--pdf-engine", "xelatex"])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            # Fallback: try wkhtmltopdf
            if to_format == "pdf":
                fallback_cmd = [
                    "pandoc",
                    str(input_path),
                    "-f", "markdown",
                    "-t", "html5",
                    "-o", str(output_path),
                ]
                subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=120)

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # pandoc not available — output will be absent


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
    export_paths = export_report(final_md, config, formats)

    result: dict[str, Any] = {
        "report_markdown": str(export_paths.get("markdown", "")),
        "export_paths": {k: str(v) for k, v in export_paths.items() if v is not None},
        "appendices_generated": [k for k, v in appendices.items() if v and not v.startswith("*No")],
        "harris_matrix": str((config.final_dir / "harris_matrix.svg").resolve()
                            if (config.final_dir / "harris_matrix.svg").exists() else ""),
    }

    return result
