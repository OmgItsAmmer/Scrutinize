# v2 Search Pipeline

Architecture for `backend/app/services/v2/` as wired by `PipelineOrchestrator` (`POST /v2/search`).

```mermaid
flowchart TD
    subgraph API["API"]
        REQ["POST /v2/search<br/>SearchV2Request"]
    end

    subgraph Memory["ConversationMemory"]
        PREP["prepare()<br/>trim to last 10 chat exchanges<br/>not an LLM call"]
    end

    subgraph Stage1["Stage 1 — Rewrite"]
        RW1["QueryRewriter.rewrite()<br/>LLM: qwen3.5:2b"]
    end

    subgraph Stage2["Stage 2 — Route"]
        GATE{"RagGate.classify()<br/>LLM: qwen3.5:0.8b<br/>JSON: route + reason + optional reply"}
    end

    subgraph GenericPath["Generic path"]
        GREPLY["Gate direct reply<br/>or GenericAgent.reply()<br/>LLM: qwen3.5:0.8b"]
        GDEC{"DecisionAgent.evaluate()<br/>LLM: qwen3.5:4b<br/>verdict + confidence + correct_route"}
        GESCALATE["Escalate to RAG path<br/>if correct_route = rag"]
    end

    subgraph RAGPath["RAG path (retry loop, max 2 attempts)"]
        RW2["QueryRewriter.rewrite()<br/>attempt 1: reuse Stage 1 rewrite<br/>retries: feedback from DecisionAgent<br/>LLM: qwen3.5:2b"]
        RRF["RrfRetriever.retrieve()<br/>not an LLM call"]
        EMB["Embed rewritten query"]
        QDRANT["Qdrant vector search<br/>top 5 chunks"]
        EMPTY{"Any chunks<br/>retrieved?"}
        SYN["RagSynthesisAgent.synthesize()<br/>LLM: qwen3.5:2b"]
        NOIDX["Fixed message:<br/>No matching indexed content found"]
        RDEC{"DecisionAgent.evaluate()<br/>LLM: qwen3.5:4b"}
        OK{"confidence ≥ 0.7<br/>and verdict = good?"}
        RETRY{"Attempts<br/>remaining?"}
        DISCLAIM["Append low-confidence disclaimer"]
    end

    subgraph Output["Response"]
        RESP["SearchV2Response<br/>answer, sources, route,<br/>confidence, attempts, conversation"]
        RECORD["ConversationMemory.record_exchange()<br/>append user + assistant turns"]
    end

    subgraph Observability["Observability (optional DB session)"]
        LOG["PipelineLogger<br/>rewrite, gate, retrieval,<br/>synthesis, evaluation, run"]
    end

    REQ --> PREP
    PREP --> RW1
    RW1 --> GATE
    GATE -->|"route = generic"| GREPLY
    GREPLY --> GDEC
    GDEC -->|"correct_route ≠ rag"| RECORD
    GDEC -->|"correct_route = rag"| GESCALATE
    GESCALATE --> RW2

    GATE -->|"route = rag"| RW2
    RW2 --> RRF
    RRF --> EMB --> QDRANT --> EMPTY
    EMPTY -->|"no"| NOIDX --> RDEC
    EMPTY -->|"yes"| SYN --> RDEC
    RDEC --> OK
    OK -->|"yes"| RECORD
    OK -->|"no"| RETRY
    RETRY -->|"yes"| RW2
    RETRY -->|"no"| DISCLAIM --> RECORD

    RECORD --> RESP

    RW1 -.-> LOG
    GATE -.-> LOG
    RRF -.-> LOG
    SYN -.-> LOG
    NOIDX -.-> LOG
    GDEC -.-> LOG
    RDEC -.-> LOG
    RESP -.-> LOG
```

## Component map

| Module | Role | LLM / external |
|--------|------|----------------|
| `conversation_memory.py` | Rolling snapshot of last 10 chat exchanges with UTC timestamps | — |
| `query_rewriter.py` | Keyword-focused rewrite; uses feedback on RAG retry | qwen3.5:2b |
| `rag_gate.py` | Route `generic` vs `rag`; optional generic reply | qwen3.5:0.8b |
| `generic_agent.py` | Fallback reply when gate routes generic without reply | qwen3.5:0.8b |
| `rrf_retriever.py` | Qdrant dense search on rewritten query | Qdrant (no LLM) |
| `retrieval_utils.py` | Qdrant hit → `SearchSource` | — |
| `rag_synthesis_agent.py` | Grounded answer from top-5 chunks | qwen3.5:2b |
| `decision_agent.py` | Score draft answer; trigger retry or RAG escalation | qwen3.5:4b |
| `pipeline_orchestrator.py` | Wires stages, retry loop, escalation | — |
| `pipeline_logger.py` | Persists run steps when DB session present | — |
| `local_llm_client.py` | HTTP client to local model host (ngrok/Ollama) | — |

## Retrieval detail

On each RAG attempt, `RrfRetriever`:

1. Embeds the **rewritten** query via `EmbeddingService`.
2. Runs one Qdrant dense search with `top_k = v2_rrf_top_k` (default **5**).
3. Returns those `SearchSource` chunks to synthesis.

Defaults: `v2_rrf_top_k=5`, `v2_max_pipeline_attempts=2`, `v2_confidence_threshold=0.7`.
