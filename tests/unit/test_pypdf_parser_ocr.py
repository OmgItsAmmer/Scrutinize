from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.parsing.base import ContentBlock
from app.services.parsing.pypdf_parser import PypdfParser


class _FakePage:
    def __init__(self, text: str):
        self._text = text
        self.images = []

    def extract_text(self) -> str:
        return self._text


class _FakePdfReader:
    def __init__(self, stream_or_path):
        self.pages = [_FakePage(""), _FakePage("")]  # no extractable text at all


@pytest.mark.unit
def test_pypdf_parser_falls_back_to_ocr_when_density_is_low():
    ocr_blocks = [
        ContentBlock(text="OCR recovered text", page_number=1, section_path=None, block_type="paragraph"),
    ]
    parser = PypdfParser(ocr_enabled=True, min_chars_per_page=100)

    with (
        patch("pypdf.PdfReader", _FakePdfReader),
        patch("app.services.parsing.ocr.ocr_pdf_pages", return_value=ocr_blocks) as mock_ocr,
    ):
        result = parser.parse(Path("scanned.pdf"))

    mock_ocr.assert_called_once()
    assert result.is_scanned is False
    assert result.blocks == ocr_blocks


@pytest.mark.unit
def test_pypdf_parser_reports_scanned_when_ocr_disabled():
    parser = PypdfParser(ocr_enabled=False, min_chars_per_page=100)

    with patch("pypdf.PdfReader", _FakePdfReader):
        result = parser.parse(Path("scanned.pdf"))

    assert result.is_scanned is True
    assert result.blocks == []


@pytest.mark.unit
def test_pypdf_parser_reports_scanned_when_ocr_also_yields_nothing():
    parser = PypdfParser(ocr_enabled=True, min_chars_per_page=100)

    with (
        patch("pypdf.PdfReader", _FakePdfReader),
        patch("app.services.parsing.ocr.ocr_pdf_pages", return_value=[]),
    ):
        result = parser.parse(Path("scanned.pdf"))

    assert result.is_scanned is True
    assert result.blocks == []
