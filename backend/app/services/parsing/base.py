"""Structured document parsing protocol (V5 M3/M4).

A DocumentParser turns a raw file into position-anchored ContentBlocks so page
numbers, section headings, and table structure survive into chunking and
citations, instead of being flattened into one string before chunking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

BlockType = Literal["paragraph", "heading", "table", "list", "caption"]


@dataclass(frozen=True)
class ContentBlock:
    text: str
    page_number: int | None
    section_path: str | None
    block_type: BlockType


@dataclass(frozen=True)
class ParsedDocument:
    blocks: list[ContentBlock] = field(default_factory=list)
    is_scanned: bool = False  # True when text density is too low to have real content (M5)


class DocumentParser(Protocol):
    def parse(self, path: Path) -> ParsedDocument: ...
