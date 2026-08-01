"""Docling-based parser — page numbers, headings, and table structure survive.

Docling is only imported inside `parse()` so the API process (which never
calls this path when parser_backend="pypdf") doesn't pay its import cost.
"""

from __future__ import annotations

from pathlib import Path

from app.services.parsing.base import BlockType, ContentBlock, ParsedDocument
from app.services.parsing.pypdf_parser import MIN_CHARS_PER_PAGE_DEFAULT

_LABEL_TO_BLOCK_TYPE: dict[str, BlockType] = {
    "section_header": "heading",
    "title": "heading",
    "table": "table",
    "list_item": "list",
    "caption": "caption",
    "picture": "caption",
}


class DoclingParser:
    def parse(self, path: Path) -> ParsedDocument:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(str(path))
        document = result.document

        blocks: list[ContentBlock] = []
        section_stack: list[str] = []
        total_chars = 0
        max_page = 0

        for item, _level in document.iterate_items():
            text = getattr(item, "text", None)
            if not text or not text.strip():
                continue
            text = text.strip()

            label = str(getattr(item, "label", "")).lower()
            block_type = _LABEL_TO_BLOCK_TYPE.get(label, "paragraph")

            page_number = None
            prov = getattr(item, "prov", None)
            if prov:
                page_number = getattr(prov[0], "page_no", None)
                if page_number is not None:
                    max_page = max(max_page, page_number)

            if block_type == "heading":
                section_stack.append(text)
                section_path = " > ".join(section_stack)
            else:
                section_path = " > ".join(section_stack) if section_stack else None

            if block_type == "table":
                table_text = self._render_table(item, document) or text
                total_chars += len(table_text)
                blocks.append(
                    ContentBlock(
                        text=table_text,
                        page_number=page_number,
                        section_path=section_path,
                        block_type="table",
                    )
                )
                continue

            total_chars += len(text)
            blocks.append(
                ContentBlock(
                    text=text,
                    page_number=page_number,
                    section_path=section_path,
                    block_type=block_type,
                )
            )

        n_pages = max_page or 1
        is_scanned = (total_chars / n_pages) < MIN_CHARS_PER_PAGE_DEFAULT
        return ParsedDocument(blocks=blocks, is_scanned=is_scanned)

    @staticmethod
    def _render_table(item: object, document: object) -> str | None:
        """Render a Docling TableItem as markdown so chunk_blocks can split it by row."""
        export_fn = getattr(item, "export_to_markdown", None)
        if callable(export_fn):
            try:
                return export_fn(doc=document)
            except Exception:
                return None
        return None
