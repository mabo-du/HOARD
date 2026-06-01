"""export — Phase 5 document export package.

Provides three export pipelines for the assembled report:
    - docx:  python-docx Word document with proper heading styles and tables
    - pdf:   WeasyPrint PDF/A-2b with XMP metadata, font subsetting, sRGB profile
    - photo: rectpack-driven photo plate layout for artefact/environmental images

Each module exposes a single top-level function:
    write_docx(md_text, path, config, template_yaml) -> Path
    write_pdf(md_text, path, config) -> Path
    write_photo_plates(assets_dir, config) -> str

License: MIT
"""

from hoard.export.docx_writer import write_docx
from hoard.export.pdf_writer import write_pdf
from hoard.export.photo_plates import write_photo_plates

__all__ = ["write_docx", "write_pdf", "write_photo_plates"]
