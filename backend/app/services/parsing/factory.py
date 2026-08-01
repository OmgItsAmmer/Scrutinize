"""Select a DocumentParser, falling back to pypdf if Docling can't be loaded."""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.services.parsing.base import DocumentParser
from app.services.parsing.pypdf_parser import PypdfParser
from app.services.vision_service import VisionService

logger = logging.getLogger(__name__)


def get_document_parser(
    settings: Settings,
    *,
    vision_service: VisionService | None = None,
) -> DocumentParser:
    if settings.parser_backend == "docling":
        try:
            from app.services.parsing.docling_parser import DoclingParser

            return DoclingParser()
        except Exception:
            logger.exception(
                "Docling parser unavailable; falling back to pypdf for this worker process."
            )
    return PypdfParser(
        vision_service=vision_service,
        ocr_enabled=settings.ocr_enabled,
        min_chars_per_page=settings.ocr_min_chars_per_page,
    )
