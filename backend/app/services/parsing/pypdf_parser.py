"""pypdf-based parser — preserves pre-V5 extraction behavior behind the DocumentParser protocol.

No table/heading structure recognition (pypdf has none); each page's text
becomes one paragraph block. This is the fallback when `parser_backend` is
"pypdf" or when the Docling parser fails to load.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.services.parsing.base import ContentBlock, ParsedDocument
from app.services.vision_service import VisionService

MIN_CHARS_PER_PAGE_DEFAULT = 100


class PypdfParser:
    def __init__(
        self,
        vision_service: VisionService | None = None,
        *,
        ocr_enabled: bool = True,
        min_chars_per_page: int = MIN_CHARS_PER_PAGE_DEFAULT,
    ) -> None:
        self._vision_service = vision_service
        self._ocr_enabled = ocr_enabled
        self._min_chars_per_page = min_chars_per_page

    def parse(self, path: Path) -> ParsedDocument:
        from pypdf import PdfReader

        reader = PdfReader(path)
        blocks: list[ContentBlock] = []
        total_chars = 0

        with tempfile.TemporaryDirectory() as img_temp_dir:
            img_temp_path = Path(img_temp_dir)

            for page_idx, page in enumerate(reader.pages):
                page_number = page_idx + 1
                text = (page.extract_text() or "").strip()
                total_chars += len(text)
                if text:
                    blocks.append(
                        ContentBlock(
                            text=text,
                            page_number=page_number,
                            section_path=None,
                            block_type="paragraph",
                        )
                    )

                image_paths = []
                for img_idx, img in enumerate(page.images):
                    suffix = Path(img.name).suffix or ".png"
                    if suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                        suffix = ".png"
                    img_path = img_temp_path / f"page_{page_idx}_img_{img_idx}{suffix}"
                    img_path.write_bytes(img.data)
                    image_paths.append(img_path)

                if image_paths:
                    if not self._vision_service:
                        raise RuntimeError(
                            "VisionService is not configured but PDF contains images to caption."
                        )
                    for caption in self._vision_service.caption_images(image_paths):
                        blocks.append(
                            ContentBlock(
                                text=f"[Image]: {caption}",
                                page_number=page_number,
                                section_path=None,
                                block_type="caption",
                            )
                        )

        n_pages = len(reader.pages) or 1
        is_scanned = (total_chars / n_pages) < self._min_chars_per_page

        if is_scanned and self._ocr_enabled:
            from app.services.parsing.ocr import ocr_pdf_pages

            ocr_blocks = ocr_pdf_pages(path)
            if ocr_blocks:
                captions = [b for b in blocks if b.block_type == "caption"]
                return ParsedDocument(blocks=ocr_blocks + captions, is_scanned=False)

        return ParsedDocument(blocks=blocks, is_scanned=is_scanned)
