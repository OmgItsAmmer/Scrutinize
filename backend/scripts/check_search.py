#!/usr/bin/env python3
"""Run a semantic search query against indexed Qdrant content (M6)."""

import argparse
import json
import sys

from app.core.config import get_settings
from app.models.file import FileModality
from app.services.agents.router_agent import RouterAgent
from app.services.agents.synthesis_agent import SynthesisAgent
from app.services.embedding_service import EmbeddingService
from app.services.search_service import SearchService
from app.services.vector_store import VectorStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Run semantic search (M6)")
    parser.add_argument("query", help="Natural-language search query")
    parser.add_argument(
        "--modality",
        choices=[item.value for item in FileModality],
        help="Optional modality filter (overrides router agent)",
    )
    parser.add_argument("--top-k", type=int, default=None, help="Number of Qdrant hits")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.openai_api_key.strip():
        print("OPENAI_API_KEY is required.", file=sys.stderr)
        sys.exit(1)

    service = SearchService(
        EmbeddingService(settings),
        VectorStore(settings),
        RouterAgent(settings),
        SynthesisAgent(settings),
        settings,
    )
    modality = FileModality(args.modality) if args.modality else None
    result = service.search(args.query, modality_filter=modality, top_k=args.top_k)
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
