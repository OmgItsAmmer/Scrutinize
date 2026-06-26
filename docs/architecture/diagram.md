# v2 Search Pipeline

Architecture for `backend/app/services/v2/` as wired by `PipelineOrchestrator` (`POST /v2/search`).

```mermaid
flowchart TD
    subgraph API["API"]
        REQ["POST /v2/search<br/>SearchV2Request"]
    end

    subgraph Memory["ConversationMemory"]
        PREP["prepare()<br/>trim to last 10 chat exchanges<br/>UTC timestamps per message<br/>not an LLM call"]
    end

    subgraph Stage1["Stage 1 — Route"]
        GATE{"RagGate.classify()<br/>current query + full conversation snapshot<br/>LLM: Qwen3.5-2B<br/>JSON: route + reason + reply"}
    end

    subgraph GenericPath["Generic path"]
        GREPLY["Gate direct reply<br/>or GenericAgent.reply()<br/>uses full conversation_context<br/>LLM: Qwen3.5-2B"]
        GDEC{"DecisionAgent.evaluate()<br/>original query + conversation context<br/>LLM: qwen3.5:4b<br/>verdict + confidence + correct_route"}
        GESCALATE["Escalate to RAG path<br/>if correct_route = rag"]
    end

    subgraph RAGPath["RAG path (retry loop, max 2 attempts)"]
        RW["QueryRewriter.rewrite()<br/>first step of RAG — keyword rewrite<br/>uses full conversation_context<br/>LLM: Qwen3.5-2B"]
        RRF["RrfRetriever.retrieve()<br/>not an LLM call"]
        EMB["Embed rewritten query"]
        QDRANT["Qdrant vector search<br/>top 5 chunks"]
        EMPTY{"Any chunks<br/>retrieved?"}
        SYN["RagSynthesisAgent.synthesize()<br/>uses full conversation_context<br/>LLM: Qwen3.5-2B"]
        NOIDX["Fixed message:<br/>No matching indexed content found"]
        RDEC{"DecisionAgent.evaluate()<br/>uses full conversation_context<br/>LLM: qwen3.5:4b"}
        OK{"confidence ≥ 0.7<br/>and verdict = good?"}
        RETRY{"Attempts<br/>remaining?"}
        DISCLAIM["Append low-confidence disclaimer"]
    end

    subgraph Output["Response"]
        RESP["SearchV2Response<br/>answer, sources, route,<br/>confidence, attempts, conversation"]
        RECORD["ConversationMemory.record_exchange()<br/>append user + assistant turns"]
    end

    subgraph Observability["Observability (optional DB session)"]
        LOG["PipelineLogger<br/>gate, rewrite, retrieval,<br/>synthesis, evaluation, run"]
    end

    REQ --> PREP
    PREP --> GATE
    GATE -->|"route = generic"| GREPLY
    GREPLY --> GDEC
    GDEC -->|"correct_route ≠ rag"| RECORD
    GDEC -->|"correct_route = rag"| GESCALATE
    GESCALATE --> RW

    GATE -->|"route = rag"| RW
    RW --> RRF
    RRF --> EMB --> QDRANT --> EMPTY
    EMPTY -->|"no"| NOIDX --> RDEC
    EMPTY -->|"yes"| SYN --> RDEC
    RDEC --> OK
    OK -->|"yes"| RECORD
    OK -->|"no"| RETRY
    RETRY -->|"yes"| RW
    RETRY -->|"no"| DISCLAIM --> RECORD

    RECORD --> RESP

    GATE -.-> LOG
    RW -.-> LOG
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
| `rag_gate.py` | Route `generic` vs `rag` using current query + full conversation; optional generic reply | Qwen3.5-2B |
| `query_rewriter.py` | Keyword-focused rewrite (RAG path only); uses feedback on retry | Qwen3.5-2B |
| `generic_agent.py` | Fallback reply when gate routes generic without reply | Qwen3.5-2B |
| `rrf_retriever.py` | Qdrant dense search on rewritten query | Qdrant (no LLM) |
| `retrieval_utils.py` | Qdrant hit → `SearchSource` | — |
| `rag_synthesis_agent.py` | Grounded answer from top-5 chunks | Qwen3.5-2B |
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
