"""Structure-aware chunking over ContentBlocks (V5 M4).

Unlike chunk_text's flat token-window slicing, this never merges across a
page boundary, never splits a table row, and treats headings as hard
chunk boundaries — so page_number/section_path stay accurate per chunk.
"""

from __future__ import annotations

from dataclasses import dataclass

import tiktoken

from app.services.parsing.base import BlockType, ContentBlock

_ENCODING_NAME = "cl100k_base"


@dataclass(frozen=True)
class Chunk:
    text: str
    page_number: int | None
    section_path: str | None
    block_type: BlockType
    char_start: int
    char_end: int


def chunk_blocks(
    blocks: list[ContentBlock],
    *,
    chunk_size: int = 400,
    overlap: int = 50,
) -> list[Chunk]:
    if not blocks:
        return []
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    encoding = tiktoken.get_encoding(_ENCODING_NAME)
    chunks: list[Chunk] = []

    # Group consecutive blocks that share a page and aren't headings/tables —
    # those are hard boundaries and are chunked independently.
    for group in _group_mergeable_blocks(blocks):
        if len(group) == 1 and group[0].block_type in ("table", "heading", "caption"):
            block = group[0]
            if block.block_type == "table":
                chunks.extend(_chunk_table(block, chunk_size=chunk_size, encoding=encoding))
            else:
                chunks.append(_whole_block_chunk(block))
            continue

        chunks.extend(
            _chunk_paragraph_group(group, chunk_size=chunk_size, overlap=overlap, encoding=encoding)
        )

    return chunks


def _group_mergeable_blocks(blocks: list[ContentBlock]) -> list[list[ContentBlock]]:
    """Split into groups that may be merged together: same page, both paragraph/list.

    Headings, tables, and captions each form their own single-block group —
    they are hard boundaries or standalone units.
    """
    groups: list[list[ContentBlock]] = []
    current: list[ContentBlock] = []

    def _flush() -> None:
        if current:
            groups.append(list(current))
            current.clear()

    for block in blocks:
        if block.block_type in ("heading", "table", "caption"):
            _flush()
            groups.append([block])
            continue

        if current and current[-1].page_number != block.page_number:
            _flush()
        current.append(block)

    _flush()
    return groups


def _whole_block_chunk(block: ContentBlock) -> Chunk:
    return Chunk(
        text=block.text,
        page_number=block.page_number,
        section_path=block.section_path,
        block_type=block.block_type,
        char_start=0,
        char_end=len(block.text),
    )


def _chunk_table(block: ContentBlock, *, chunk_size: int, encoding: tiktoken.Encoding) -> list[Chunk]:
    """Emit a table as one chunk if it fits; otherwise split by rows with the header repeated."""
    tokens = encoding.encode(block.text)
    if len(tokens) <= chunk_size:
        return [_whole_block_chunk(block)]

    lines = block.text.split("\n")
    if len(lines) < 3:
        # Not enough structure to safely split by row — keep as a single oversized chunk
        # rather than risk truncating mid-row.
        return [_whole_block_chunk(block)]

    header_lines = lines[:2]  # markdown table: header row + separator row
    header_text = "\n".join(header_lines)
    header_tokens = len(encoding.encode(header_text))
    body_lines = lines[2:]

    chunks: list[Chunk] = []
    current_lines: list[str] = []
    current_tokens = header_tokens
    offset = 0

    def _flush(end_offset: int) -> None:
        nonlocal current_lines, current_tokens
        if not current_lines:
            return
        text = "\n".join([*header_lines, *current_lines])
        chunks.append(
            Chunk(
                text=text,
                page_number=block.page_number,
                section_path=block.section_path,
                block_type="table",
                char_start=offset,
                char_end=end_offset,
            )
        )
        current_lines = []
        current_tokens = header_tokens

    for line in body_lines:
        line_tokens = len(encoding.encode(line))
        if current_lines and current_tokens + line_tokens > chunk_size:
            _flush(offset)
        current_lines.append(line)
        current_tokens += line_tokens
        offset += len(line) + 1

    _flush(offset)
    return chunks


def _chunk_paragraph_group(
    group: list[ContentBlock],
    *,
    chunk_size: int,
    overlap: int,
    encoding: tiktoken.Encoding,
) -> list[Chunk]:
    """Token-window chunk a same-page run of paragraph/list blocks, joined by blank lines."""
    combined = "\n\n".join(b.text for b in group)
    page_number = group[0].page_number
    section_path = group[0].section_path
    block_type = group[0].block_type

    tokens = encoding.encode(combined)
    if not tokens:
        return []

    chunks: list[Chunk] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        window_text = encoding.decode(tokens[start:end])
        char_start = len(encoding.decode(tokens[:start]))
        chunks.append(
            Chunk(
                text=window_text,
                page_number=page_number,
                section_path=section_path,
                block_type=block_type,
                char_start=char_start,
                char_end=char_start + len(window_text),
            )
        )
        if end >= len(tokens):
            break
        start = end - overlap
    return chunks
