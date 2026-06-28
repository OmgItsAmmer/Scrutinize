# v2 Search Pipeline

Architecture for `backend/app/services/v2/` as wired by `PipelineOrchestrator` (`POST /v2/search`).

## Flowchart Diagram

```mermaid
flowchart TD
    subgraph API["API"]
        REQ["POST /v2/search<br/>SearchV2Request"]
    end

    subgraph Memory["ConversationMemory"]
        PREP["prepare()<br/>trim to last 10 chat exchanges<br/>UTC timestamps per message<br/>not an LLM call"]
    end

    subgraph Stage1["Stage 1 — Route"]
        GATE{"RagGate.classify()<br/>current query + full conversation snapshot<br/>LLM: Gate Model"}
    end

    subgraph GenericPath["Generic path"]
        GREPLY["Gate direct reply<br/>or GenericAgent.reply()<br/>uses full conversation_context<br/>LLM: Gate Model (if reply empty)"]
        GDEC{"DecisionAgent.evaluate()<br/>original query + conversation context<br/>LLM: Decision Model<br/>verdict + confidence + correct_route"}
        GESCALATE["Escalate to RAG path<br/>if correct_route = RAG"]
    end

    subgraph RAGPath["RAG path (retry loop, max attempts)"]
        RW["QueryRewriter.rewrite()<br/>first step of RAG — keyword rewrite<br/>uses full conversation_context<br/>LLM: Rewriter Model (skipped if standalone)"]
        RRF["RrfRetriever.retrieve()<br/>not an LLM call"]
        EMB["Dense Embedding<br/>(EmbeddingService API call)"]
        SPARSE["Sparse BM25 Embedding<br/>(Local fastembed call)"]
        QDRANT["Qdrant Hybrid Search<br/>RRF Fusion of top-k chunks"]
        EMPTY{"Any chunks<br/>retrieved?"}
        SYN["RagSynthesisAgent.synthesize()<br/>uses full conversation_context<br/>LLM: Rewriter Model"]
        NOIDX["Fixed message:<br/>No matching indexed content found"]
        RDEC{"DecisionAgent.evaluate()<br/>uses full conversation_context<br/>LLM: Decision Model"}
        OK{"confidence ≥ threshold<br/>and verdict = good?"}
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
    RRF --> EMB
    RRF --> SPARSE
    EMB --> QDRANT
    SPARSE --> QDRANT
    QDRANT --> EMPTY
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

## LLM Running Placements & Client Routing Layer

Depending on the `USE_CLOUD_LLM` flag, all LLM calls are routed either locally or to OpenAI:

```mermaid
flowchart TD
    subgraph AgentLayer["Agent Layer"]
        GATE_A["RagGate.classify()"]
        GEN_A["GenericAgent.reply()"]
        RW_A["QueryRewriter.rewrite()"]
        SYN_A["RagSynthesisAgent.synthesize()"]
        DEC_A["DecisionAgent.evaluate()"]
    end

    subgraph ClientRouting["LLM Client Routing Layer"]
        CLIENT{"get_v2_llm_client()<br/>use_cloud_llm?"}
        LOCAL["LocalLlmClient<br/>(Local Ollama via ngrok)"]
        CLOUD["CloudLlmClient<br/>(Cloud OpenAI API)"]
    end

    subgraph Models["Model Targets"]
        M_GATE["Gate Model<br/>Local: Qwen/Qwen3.5-2B<br/>Cloud: gpt-4o-mini"]
        M_REWRITE["Rewriter Model<br/>Local: Qwen/Qwen3.5-2B<br/>Cloud: gpt-4o-mini"]
        M_DECISION["Decision Model<br/>Local: qwen3.5:4b<br/>Cloud: gpt-4o-mini"]
    end

    GATE_A --> CLIENT
    GEN_A --> CLIENT
    RW_A --> CLIENT
    SYN_A --> CLIENT
    DEC_A --> CLIENT

    CLIENT -->|"False"| LOCAL
    CLIENT -->|"True"| CLOUD

    LOCAL -->|"Gate/Generic"| M_GATE
    LOCAL -->|"Rewriter/Synthesis"| M_REWRITE
    LOCAL -->|"Decision"| M_DECISION

    CLOUD --> M_GATE
    CLOUD --> M_REWRITE
    CLOUD --> M_DECISION
```

## Component map

| Module | Role | LLM / external |
|--------|------|----------------|
| `conversation_memory.py` | Rolling snapshot of last 10 chat exchanges with UTC timestamps | — |
| `rag_gate.py` | Route `generic` vs `rag` using current query + full conversation; optional generic reply | Gate Model |
| `query_rewriter.py` | Keyword-focused rewrite (RAG path only); uses feedback on retry | Rewriter Model |
| `generic_agent.py` | Fallback reply when gate routes generic without reply | Gate Model |
| `rrf_retriever.py` | Orchestrates query embedding and retrieves top-k matching documents from Qdrant | Embedding Service + Qdrant (no LLM) |
| `retrieval_utils.py` | Qdrant hit → `SearchSource` | — |
| `rag_synthesis_agent.py` | Grounded answer from top-5 chunks | Rewriter Model |
| `decision_agent.py` | Score draft answer; trigger retry or RAG escalation | Decision Model |
| `pipeline_orchestrator.py` | Wires stages, retry loop, escalation, and logging | — |
| `pipeline_logger.py` | Writes steps (gate, rewrite, retrieval, synthesis, evaluation) to Postgres | Neon Postgres |
| `llm_clients/base.py` | Abstract base class for the LLM execution client | — |
| `llm_clients/local.py` | OpenAI-compatible HTTP client for local model host (ngrok/Ollama) | Local Ollama |
| `llm_clients/cloud.py` | OpenAI API client for cloud model host | OpenAI |

## Retrieval detail

On each RAG attempt, `RrfRetriever`:

1. Embeds the **rewritten** query via `EmbeddingService` (Dense Vector).
2. Generates the lexical sparse representation via the local `fastembed` model (Sparse Vector).
3. Queries both indexes concurrently in Qdrant and combines them natively using **Reciprocal Rank Fusion (RRF)**.
4. Returns those `SearchSource` chunks to synthesis.

Defaults: `v2_rrf_top_k=5`, `v2_max_pipeline_attempts=2`, `v2_confidence_threshold=0.7`.

