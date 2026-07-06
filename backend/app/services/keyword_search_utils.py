"""Normalization and variant expansion for BM25 keyword search."""

from __future__ import annotations

import re
import unicodedata
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote, urlparse

from qdrant_client.models import SparseVector

_ALNUM_SPACE_PATTERN = re.compile(r"(?<=[a-z0-9]) (?=[a-z0-9])")


def normalize_for_keyword_search(text: str) -> str:
    """Lowercase, Unicode-normalize, and unify separators for BM25 text."""
    if not text or not text.strip():
        return ""

    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = re.sub(r"[-_]+", " ", normalized)
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def keyword_variants(text: str) -> list[str]:
    """Return unique keyword forms, including collapsed compounds (open ai -> openai)."""
    normalized = normalize_for_keyword_search(text)
    if not normalized:
        return []

    variants: list[str] = [normalized]
    collapsed = normalized
    while True:
        next_collapsed = _ALNUM_SPACE_PATTERN.sub("", collapsed, count=1)
        if next_collapsed == collapsed:
            break
        collapsed = next_collapsed
        variants.append(collapsed)

    seen: set[str] = set()
    unique: list[str] = []
    for variant in variants:
        if variant not in seen:
            seen.add(variant)
            unique.append(variant)
    return unique


def filename_stem(source_path: str) -> str:
    """Extract a searchable filename stem from a path or URL."""
    if not source_path or not source_path.strip():
        return ""

    path = source_path.strip()
    if "://" in path:
        path = unquote(urlparse(path).path)

    name = PurePosixPath(path.replace("\\", "/")).name
    if not name:
        return ""

    if "." in name:
        name = name.rsplit(".", 1)[0]
    return normalize_for_keyword_search(name)


def build_sparse_index_text(
    *,
    content: str,
    title: str = "",
    source_path: str = "",
) -> str:
    """Enriched text for BM25 indexing (dense embeddings still use raw content)."""
    parts: list[str] = []

    for source in (content, title, filename_stem(source_path)):
        for variant in keyword_variants(source):
            parts.append(variant)

    seen: set[str] = set()
    unique_parts: list[str] = []
    for part in parts:
        if part not in seen:
            seen.add(part)
            unique_parts.append(part)
    return " ".join(unique_parts)


def merge_sparse_vectors(vectors: list[SparseVector]) -> SparseVector:
    """Merge sparse vectors by summing weights per token index."""
    if not vectors:
        return SparseVector(indices=[], values=[])
    if len(vectors) == 1:
        return vectors[0]

    merged: dict[int, float] = {}
    for vector in vectors:
        indices = list(vector.indices or [])
        values = list(vector.values or [])
        for index, value in zip(indices, values, strict=True):
            merged[index] = merged.get(index, 0.0) + float(value)

    if not merged:
        return SparseVector(indices=[], values=[])

    sorted_items = sorted(merged.items())
    return SparseVector(
        indices=[index for index, _ in sorted_items],
        values=[value for _, value in sorted_items],
    )


def embed_sparse_query(sparse_model: Any, query: str) -> SparseVector:
    """BM25-embed all keyword variants of a query and merge into one sparse vector."""
    variants = keyword_variants(query)
    if not variants:
        return SparseVector(indices=[], values=[])

    raw_embeddings = list(sparse_model.embed(variants))
    vectors = [
        SparseVector(indices=list(embedding.indices), values=list(embedding.values))
        for embedding in raw_embeddings
    ]
    return merge_sparse_vectors(vectors)
