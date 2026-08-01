from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.services.parsing.factory import get_document_parser
from app.services.parsing.pypdf_parser import PypdfParser


@pytest.mark.unit
def test_get_document_parser_returns_docling_by_default():
    settings = Settings(parser_backend="docling")
    parser = get_document_parser(settings)
    assert type(parser).__name__ == "DoclingParser"


@pytest.mark.unit
def test_get_document_parser_returns_pypdf_when_configured():
    settings = Settings(parser_backend="pypdf")
    parser = get_document_parser(settings)
    assert isinstance(parser, PypdfParser)


@pytest.mark.unit
def test_get_document_parser_falls_back_to_pypdf_when_docling_import_fails():
    settings = Settings(parser_backend="docling")
    with patch(
        "app.services.parsing.docling_parser.DoclingParser.__init__",
        side_effect=ImportError("docling not installed"),
    ):
        parser = get_document_parser(settings)
    assert isinstance(parser, PypdfParser)
