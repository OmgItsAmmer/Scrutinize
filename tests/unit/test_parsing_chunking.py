import pytest

from app.services.parsing.base import ContentBlock
from app.services.parsing.chunking import chunk_blocks


@pytest.mark.unit
def test_chunk_blocks_empty_input_returns_empty():
    assert chunk_blocks([]) == []


@pytest.mark.unit
def test_chunk_blocks_never_merges_across_page_boundary():
    blocks = [
        ContentBlock(text="Page one paragraph.", page_number=1, section_path=None, block_type="paragraph"),
        ContentBlock(text="Page two paragraph.", page_number=2, section_path=None, block_type="paragraph"),
    ]
    chunks = chunk_blocks(blocks, chunk_size=400, overlap=50)

    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[1].page_number == 2
    assert "Page one" in chunks[0].text
    assert "Page two" in chunks[1].text


@pytest.mark.unit
def test_chunk_blocks_merges_consecutive_paragraphs_on_same_page():
    blocks = [
        ContentBlock(text="First paragraph.", page_number=1, section_path=None, block_type="paragraph"),
        ContentBlock(text="Second paragraph.", page_number=1, section_path=None, block_type="paragraph"),
    ]
    chunks = chunk_blocks(blocks, chunk_size=400, overlap=50)

    assert len(chunks) == 1
    assert "First paragraph." in chunks[0].text
    assert "Second paragraph." in chunks[0].text


@pytest.mark.unit
def test_chunk_blocks_headings_are_hard_boundaries():
    blocks = [
        ContentBlock(text="Intro", page_number=1, section_path="Intro", block_type="heading"),
        ContentBlock(text="Body text.", page_number=1, section_path="Intro", block_type="paragraph"),
    ]
    chunks = chunk_blocks(blocks, chunk_size=400, overlap=50)

    assert len(chunks) == 2
    assert chunks[0].block_type == "heading"
    assert chunks[0].text == "Intro"
    assert chunks[1].block_type == "paragraph"


@pytest.mark.unit
def test_chunk_blocks_section_path_carries_down_to_children():
    blocks = [
        ContentBlock(text="Payment Terms", page_number=3, section_path="2.1 Payment Terms", block_type="heading"),
        ContentBlock(text="Invoices are due within 30 days.", page_number=3, section_path="2.1 Payment Terms", block_type="paragraph"),
    ]
    chunks = chunk_blocks(blocks, chunk_size=400, overlap=50)

    assert chunks[1].section_path == "2.1 Payment Terms"
    assert chunks[1].page_number == 3


@pytest.mark.unit
def test_chunk_blocks_table_emitted_whole_when_it_fits():
    table_text = "| A | B |\n|---|---|\n| 1 | 2 |"
    blocks = [
        ContentBlock(text=table_text, page_number=1, section_path=None, block_type="table"),
    ]
    chunks = chunk_blocks(blocks, chunk_size=400, overlap=50)

    assert len(chunks) == 1
    assert chunks[0].block_type == "table"
    assert chunks[0].text == table_text


@pytest.mark.unit
def test_chunk_blocks_table_split_by_rows_repeats_header_when_oversized():
    header = "| Col A | Col B |\n|---|---|"
    rows = "\n".join(f"| val{i} | val{i} |" for i in range(200))
    table_text = f"{header}\n{rows}"
    blocks = [
        ContentBlock(text=table_text, page_number=5, section_path="Appendix", block_type="table"),
    ]
    chunks = chunk_blocks(blocks, chunk_size=100, overlap=10)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.block_type == "table"
        assert chunk.page_number == 5
        assert chunk.text.startswith("| Col A | Col B |")  # header repeated in every split chunk


@pytest.mark.unit
def test_chunk_blocks_caption_is_its_own_chunk():
    blocks = [
        ContentBlock(text="Body text.", page_number=2, section_path=None, block_type="paragraph"),
        ContentBlock(text="[Image]: a chart", page_number=2, section_path=None, block_type="caption"),
    ]
    chunks = chunk_blocks(blocks, chunk_size=400, overlap=50)

    assert len(chunks) == 2
    assert chunks[1].block_type == "caption"
    assert chunks[1].page_number == 2


@pytest.mark.unit
def test_chunk_blocks_rejects_invalid_overlap():
    blocks = [ContentBlock(text="x", page_number=1, section_path=None, block_type="paragraph")]
    with pytest.raises(ValueError, match="overlap"):
        chunk_blocks(blocks, chunk_size=10, overlap=10)


@pytest.mark.unit
def test_chunk_blocks_long_paragraph_splits_with_overlap():
    long_text = "word " * 500
    blocks = [ContentBlock(text=long_text, page_number=1, section_path=None, block_type="paragraph")]
    chunks = chunk_blocks(blocks, chunk_size=100, overlap=20)

    assert len(chunks) > 1
    assert all(c.page_number == 1 for c in chunks)
