"""OCR fallback for scanned PDFs on the pypdf parser path (V5 M5).

The Docling parser already runs OCR per-page automatically (do_ocr=True in
its default pipeline), so this module only matters when parser_backend is
"pypdf" or Docling failed to load and pypdf was used as the fallback.
"""

from __future__ import annotations

from pathlib import Path

from app.services.parsing.base import ContentBlock


def ocr_pdf_pages(path: Path) -> list[ContentBlock]:
    """Rasterize each page and run RapidOCR, returning one paragraph block per page."""
    import pypdfium2 as pdfium
    from rapidocr import RapidOCR

    engine = RapidOCR()
    blocks: list[ContentBlock] = []

    pdf = pdfium.PdfDocument(str(path))
    try:
        for page_index in range(len(pdf)):
            page = pdf[page_index]
            try:
                bitmap = page.render(scale=2.0)
                image = bitmap.to_pil()
                result = engine(image)
                lines = result.txts if result and result.txts else []
                text = "\n".join(lines).strip()
            finally:
                page.close()

            if text:
                blocks.append(
                    ContentBlock(
                        text=text,
                        page_number=page_index + 1,
                        section_path=None,
                        block_type="paragraph",
                    )
                )
    finally:
        pdf.close()

    return blocks
