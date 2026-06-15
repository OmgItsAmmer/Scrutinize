# M6 — Search & Agents

**Status:** Implemented  
**Location:** `backend/app/services/agents/`, `backend/app/services/search_service.py`, `backend/app/api/search.py`

## Purpose

Cross-modal semantic search over indexed content. A two-agent RAG pipeline rewrites and optionally filters the user's question, embeds it, retrieves top-k segments from Qdrant (M5), and synthesizes a cited natural-language answer with structured source metadata for the frontend (M7).

Maps to **Phase 3 / Milestone 3** in [plan.md](../plan.md).

## Package layout

```text
backend/app/
├── api/
│   └── search.py                    # POST /search
├── schemas/
│   └── search.py                    # SearchRequest, SearchResponse, SearchSource
├── services/
│   ├── search_service.py            # Orchestrates router → embed → Qdrant → synthesis
│   └── agents/
│       ├── __init__.py
│       ├── router_agent.py          # GPT-4o-mini + function calling
│       └── synthesis_agent.py       # GPT-4o-mini answer over retrieved segments
└── core/
    └── deps.py                      # get_router_agent, get_synthesis_agent, get_search_service

backend/scripts/
└── check_search.py                  # CLI smoke test for indexed content
```

## Search pipeline

```text
User query
    │
    ▼
RouterAgent.route()          → { search_query, modality_filter? }
    │
    ▼
effective_modality =         request.modality_filter OR router modality_filter
    │
    ▼
EmbeddingService.embed_texts([search_query])
    │
    ▼
VectorStore.search(vector, top_k, modality=effective_modality)
    │
    ▼
_hit_to_source()             → list[SearchSource]
    │
    ▼
SynthesisAgent.synthesize() → answer string
    │
    ▼
SearchResponse
```

**Modality precedence:** An explicit `modality_filter` on the HTTP request wins over whatever the router agent inferred. If neither is set, Qdrant search runs across all modalities.

**Default top-k:** `settings.search_top_k` (5) unless the request passes `top_k` (1–20).

## API endpoint

| Method | Path | Request | Response |
|---|---|---|---|
| `POST` | `/search` | `SearchRequest` | `SearchResponse` |

OpenAPI: http://localhost:8000/docs (tag: `search`)

### Request (`SearchRequest`)

| Field | Type | Constraints | Description |
|---|---|---|---|
| `query` | `string` | 1–2000 chars | Natural-language question |
| `modality_filter` | `text` \| `audio` \| `video` \| `null` | optional | Hard filter; overrides router |
| `top_k` | `int` | 1–20, optional | Number of Qdrant hits |

### Response (`SearchResponse`)

| Field | Type | Description |
|---|---|---|
| `query` | `string` | Original user query (trimmed) |
| `search_query` | `string` | Router-rewritten query used for embedding |
| `modality_filter` | enum \| `null` | Effective modality filter applied |
| `answer` | `string` | Synthesized natural-language answer |
| `sources` | `SearchSource[]` | Ranked segments for UI playback / citations |

### `SearchSource` (per hit)

| Field | Type | Description |
|---|---|---|
| `segment_id` | `UUID` | Qdrant point id (matches Neon `segments.id`) |
| `file_id` | `UUID` | Parent file |
| `modality` | `text` \| `audio` \| `video` | Segment modality |
| `title` | `string` | File title / filename |
| `content` | `string` | Transcript, caption, or text chunk |
| `source_path` | `string` | Cloudinary HTTPS URL for playback |
| `start_time` | `float` \| `null` | Seconds (audio/video) |
| `end_time` | `float` \| `null` | Seconds (audio/video) |
| `score` | `float` | Cosine similarity from Qdrant |

### Example

```bash
curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Find the video where someone drinks milk", "modality_filter": "video"}'
```

```json
{
  "query": "Find the video where someone drinks milk",
  "search_query": "person drinking milk from a glass",
  "modality_filter": "video",
  "answer": "See bbq-day.mp4 around 00:42 — a person drinks milk.",
  "sources": [
    {
      "segment_id": "…",
      "file_id": "…",
      "modality": "video",
      "title": "bbq-day.mp4",
      "content": "Visual: A person drinks milk …",
      "source_path": "https://res.cloudinary.com/…/bbq-day.mp4",
      "start_time": 42.0,
      "end_time": 51.0,
      "score": 0.91
    }
  ]
}
```

## Agents

### RouterAgent (`router_agent.py`)

- **Model:** `settings.router_model` (default `gpt-4o-mini`)
- **Mechanism:** OpenAI function calling — single tool `route_search_query`
- **Outputs:** `RouterResult(search_query, modality_filter?)`
- **Behaviour:**
  - Rewrites the query for better embedding recall
  - Sets `modality_filter` only when the user clearly targets text, audio, or video
  - Falls back to the raw query (no filter) if the model returns no tool call

### SynthesisAgent (`synthesis_agent.py`)

- **Model:** `settings.synthesis_model` (default `gpt-4o-mini`)
- **Input:** Original query + formatted source list (modality, title, timestamps, score, content)
- **Output:** Concise answer citing file names and timestamps when available
- **Empty hits:** Returns `"No matching indexed content was found for your question."` without calling OpenAI
- **Max tokens:** 500

## SearchService (`search_service.py`)

Wires M5 dependencies into the agent layer:

| Dependency | Role in search |
|---|---|
| `EmbeddingService` | Embeds `route.search_query` via `text-embedding-3-small` |
| `VectorStore` | Cosine search on `text_vector` with optional `modality` payload filter |
| `RouterAgent` | Query rewrite + optional modality hint |
| `SynthesisAgent` | Final answer generation |

`_hit_to_source()` maps Qdrant payload fields (`file_id`, `modality`, `content`, `source_path`, `title`, `start_time`, `end_time`) into `SearchSource`.

## Configuration (`core/config.py`)

| Setting | Env var | Default | Used by |
|---|---|---|---|
| `openai_api_key` | `OPENAI_API_KEY` | `""` | Router, synthesis, embeddings (required) |
| `router_model` | — | `gpt-4o-mini` | RouterAgent |
| `synthesis_model` | — | `gpt-4o-mini` | SynthesisAgent |
| `search_top_k` | — | `5` | SearchService default limit |
| `qdrant_url` | `QDRANT_URL` | `http://localhost:6333` | VectorStore |
| `qdrant_collection` | — | `segments` | VectorStore |
| `embedding_model` | — | `text-embedding-3-small` | EmbeddingService |

Router and synthesis agents raise `RuntimeError` at construction if `OPENAI_API_KEY` is empty.

## CLI check

After indexing at least one file per modality:

```bash
make check-search QUERY="What does the project plan say?"
make check-search QUERY="Find the video where someone drinks milk"  # optional: pass modality via script
```

Direct:

```bash
cd backend
python scripts/check_search.py "your query" [--modality text|audio|video] [--top-k N]
```

Prints `SearchResponse` as JSON to stdout.

## Dependencies

| Module | Why |
|---|---|
| **M1** | FastAPI route, Pydantic schemas, DI via `core/deps.py` |
| **M5** | `EmbeddingService` + `VectorStore.search()` over the `segments` collection |

Requires prior ingestion (M2–M4) so Qdrant has points with complete payloads (`content`, `source_path`, timestamps).

## Used by

| Consumer | Integration |
|---|---|
| **M7** | `frontend/src/api/client.ts` → `POST /search`; `SearchView` + `SourceCard` render answer and per-modality playback |
| **M8** | Unit and security tests (see below) |

## Tests

| Suite | File | Coverage |
|---|---|---|
| Unit | `tests/unit/test_router_agent.py` | Tool-call parsing, fallback without tool call |
| Unit | `tests/unit/test_synthesis_agent.py` | Answer generation, empty sources |
| Unit | `tests/unit/test_search_service.py` | Full mocked pipeline, modality filter wiring |
| Unit | `tests/unit/test_search_api.py` | `POST /search` 200 + empty-query 422 |
| Unit | `tests/unit/test_vector_store.py` | Modality filter passed to Qdrant |
| Security | `tests/security/test_search_security.py` | No secret leakage in responses; no traceback on 422 |

Run:

```bash
pytest -m unit tests/unit/test_router_agent.py tests/unit/test_synthesis_agent.py \
  tests/unit/test_search_service.py tests/unit/test_search_api.py
pytest -m security tests/security/test_search_security.py
```

## Local run

Prerequisites: Qdrant up, `OPENAI_API_KEY` set, indexed content in the `segments` collection.

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

Then `POST /search` or `make check-search QUERY="…"`.

## Known limitations

- Search quality depends on transcription/caption text from ingestion — instrumental audio without lyrics may not match song-title queries (see [plan.md §9](../plan.md)).
- Only `text_vector` is queried; CLIP/CLAP named vectors are deferred (architecture §7 Phase B).
- No auth on `/search` yet; API keys stay server-side only.

## Related docs

- [Architecture §4.4 — Agents](../architecture/architecture.md)
- [plan.md §4 — M5 embedding & vector store](../plan.md)
- [M7 frontend](m7-frontend.md) — search UI consumer
