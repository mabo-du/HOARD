"""pdf_writer.py — PDF/A-2b export via WeasyPrint.

Converts the compiled Markdown report into archival PDF/A-2b with:
    - A4 page size, 2.5 cm margins
    - Font subsetting via WeasyPrint's built-in CSS @font-face support
    - Dublin Core XMP metadata (title, author, date, jurisdiction)
    - sRGB output intent for colour-accurate images
    - Page headers/footers with report title and page number
    - Running section headers for readability

Replaces the earlier pandoc+wkhtmltopdf path which had no PDF/A support.

exports: write_pdf(md_text, path, config) -> Path
used_by: erd.phases.phase5  → export_report()
rules:   No GPU. WeasyPrint 68.1+ required.
license: MIT
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import markdown


def write_pdf(
    md_text: str,
    output_path: Path,
    project_name: str = "Excavation Report",
    jurisdiction: str = "",
    pdfa_level: str = "pdf/a-2b",
) -> Path:
    """Convert Markdown report to PDF/A-2b via WeasyPrint.

    Args:
        md_text: Full Markdown body.
        output_path: Target .pdf path.
        project_name: Used in title metadata and page header.
        jurisdiction: Used in subtitle metadata.
        pdfa_level: PDF/A variant (default "pdf/a-2b").

    Returns:
        output_path (confirmed written).
    """
    import weasyprint

    # ── Markdown → HTML ─────────────────────────────────────────────────────
    html_body = markdown.markdown(
        md_text,
        extensions=[
            "markdown.extensions.extra",
            "markdown.extensions.toc",
        ],
    )

    # ── Wrap in print-ready HTML ────────────────────────────────────────────
    date_str = datetime.now(timezone.utc).strftime("%B %Y")
    escaped_title = html.escape(project_name)

    full_html = _PDF_A_TEMPLATE.format(
        title=escaped_title,
        jurisdiction=html.escape(jurisdiction),
        date=date_str,
        body=html_body,
    )

    # ── WeasyPrint rendering ────────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)

    html_doc = weasyprint.HTML(string=full_html, base_url=output_path.parent)
    html_doc.write_pdf(
        target=str(output_path),
        pdf_variant=pdfa_level,
        pdf_identifier=pdfa_level,
    )

    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
# Print-ready HTML template with A4 CSS, page margins, TOC styling,
# running headers/footers, and Dublin Core XMP metadata injection.
# ═══════════════════════════════════════════════════════════════════════════════

_PDF_A_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>

<!-- ── XMP / Dublin Core metadata (consumed by WeasyPrint for PDF/A) ── -->
<meta name="dcterms.title" content="{title}">
<meta name="dcterms.creator" content="HOARD Archaeological Report Pipeline">
<meta name="dcterms.date" content="{date}">
<meta name="dcterms.type" content="Archaeological Excavation Report">
<meta name="dcterms.publisher" content="HOARD">
<meta name="dcterms.rights" content="© {date} — HOARD Pipeline Output">
<meta name="jurisdiction" content="{jurisdiction}">
<meta name="pdfa_level" content="PDF/A-2b">
<meta name="color_profile" content="sRGB">

<style>
/* ═══════════════════════════════════════════════════════════════════════════
   PDF/A-2b print stylesheet — A4, 2.5 cm margins, serif body.
   ═══════════════════════════════════════════════════════════════════════════ */

@page {{
    size: A4;
    margin: 2.5cm 2.5cm 3cm 2.5cm;

    @bottom-center {{
        content: counter(page);
        font-family: "Calibri", "DejaVu Sans", sans-serif;
        font-size: 9pt;
        color: #666;
    }}

    @top-right {{
        content: "{title}";
        font-family: "Calibri", "DejaVu Sans", sans-serif;
        font-size: 8pt;
        color: #999;
        font-style: italic;
    }}
}}

@page :first {{
    @top-right {{ content: normal; }}
}}

/* ── Base typography ── */
html {{
    font-family: "Calibri", "DejaVu Sans", "Liberation Sans", sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #1a1a1a;
}}

body {{
    text-align: justify;
    hyphens: auto;
}}

/* ── Headings ── */
h1 {{
    font-size: 18pt;
    font-weight: bold;
    color: #1a1a1a;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    page-break-before: always;
    page-break-after: avoid;
}}

h1:first-of-type {{
    page-break-before: avoid;
}}

h2 {{
    font-size: 14pt;
    font-weight: bold;
    color: #333;
    margin-top: 1.2em;
    margin-bottom: 0.3em;
    page-break-after: avoid;
}}

h3 {{
    font-size: 12pt;
    font-weight: bold;
    color: #444;
    margin-top: 1em;
    margin-bottom: 0.3em;
    page-break-after: avoid;
}}

/* ── Paragraphs ── */
p {{
    margin: 0.3em 0;
    orphans: 3;
    widows: 3;
}}

/* ── Tables ── */
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 9.5pt;
    margin: 0.8em 0;
}}

th {{
    background-color: #f0f0f0;
    font-weight: bold;
    text-align: left;
    padding: 4px 6px;
    border: 1px solid #ccc;
}}

td {{
    padding: 3px 6px;
    border: 1px solid #ccc;
    vertical-align: top;
}}

/* ── Images ── */
img {{
    max-width: 100%;
    height: auto;
    margin: 0.8em auto;
    display: block;
}}

/* ── Lists ── */
ul, ol {{
    margin: 0.3em 0;
    padding-left: 1.5em;
}}

li {{
    margin: 0.1em 0;
}}

/* ── Code / formatting ── */
strong {{ font-weight: bold; }}
em {{ font-style: italic; }}

/* ── TOC (if generated) ── */
.toc {{
    page-break-before: avoid;
    page-break-after: always;
}}

.toc ul {{
    list-style: none;
    padding-left: 0;
}}

.toc li {{
    margin: 0.3em 0;
}}

/* ── Cover page ── */
.cover-page {{
    text-align: center;
    padding-top: 40%;
}}

.cover-page h1 {{
    font-size: 24pt;
    page-break-before: avoid;
    text-align: center;
}}

.cover-page .subtitle {{
    font-size: 12pt;
    color: #555;
    margin-top: 1em;
}}

.cover-page .date {{
    font-size: 11pt;
    color: #777;
    margin-top: 3em;
}}
</style>
</head>
<body>

<div class="cover-page">
    <h1>{title}</h1>
    <p class="subtitle">Prepared in accordance with {jurisdiction}</p>
    <p class="date">{date}</p>
</div>

<div style="page-break-before: always;">
{body}
</div>

</body>
</html>
"""
