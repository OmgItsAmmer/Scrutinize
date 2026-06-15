# Project Plan — Scrutinize

Module-wise division & phases for **Scrutinize**, a multi-modal AI embedding & retrieval system.

This plan maps the brief's **3 milestones** onto **5 build phases** and **8 modules**. Each phase lists which modules it touches, the concrete tasks, the deliverable, and how it maps back to the brief's submission requirements.

---

## 1. Module Map

| Module | Name | Lives in | Summary |
|---|---|---|---|
| **M0** | Infrastructure & DevOps | repo root, `docker-compose.yml`, `.github/workflows/` | Repo scaffold, Docker, env config, Qdrant/Redis provisioning, Neon `DATABASE_URL`, GitHub Actions CI |
| **M1** | Backend Core | `backend/app/core`, `api/` | FastAPI app, config, Pydantic schemas, Neon/SQLModel models, job orchestration |
| **M2** | Text Ingestion | `backend/app/services/text_processor.py` | Text chunking + embedding pipeline |
| **M3** | Audio Ingestion | `backend/app/services/audio_processor.py` | Whisper transcription + segment embedding pipeline |
| **M4** | Video Ingestion | `backend/app/services/video_processor.py` | FFmpeg extraction + transcription + captioning + segment embedding pipeline |
| **M5** | Embedding & Vector Store | `backend/app/services/embedding_service.py`, `vector_store.py` | Shared embedding wrapper + Qdrant client/collection management |
| **M6** | Search & Agents | `backend/app/services/agents/` | Router agent, retrieval, synthesis agent, `/search` endpoint |
| **M7** | Frontend | `frontend/src/` | React UI (upload, search, results, library) — see `frontend.md` |
| **M8** | QA, Docs & Demo | `docs/`, `tests/` | Tests, README, project report, demo recording |

---

## 2. Phase Overview

| Phase | Maps to Brief Milestone | Modules | Goal |
|---|---|---|---|
| **Phase 0** — Setup | (pre-Milestone 1) | M0, M1 | Repo, infra, and a working "hello world" API + frontend wired together |
| **Phase 1** — Ingestion Pipeline | **Milestone 1** | M2, M3, M4, M5 | Each modality can be uploaded and produces vectors in Qdrant |
| **Phase 2** — Indexing & Context | **Milestone 2** | M1, M2–M5, M0 | Rich payload (transcripts/captions), Neon metadata, job status tracking |
| **Phase 3** — Search & Demo UI | **Milestone 3** | M6, M7 | Cross-modal search via agents, surfaced in the React UI |
| **Phase 4** — Polish & Submission | (submission guidelines) | M7, M8 | Tests, docs, README, architecture/report writeups, demo video |

---

## 3. Phase 0 — Setup & Infrastructure

**Modules:** M0, M1

| Task | Detail |
|---|---|
| Repo scaffold | Monorepo: `/backend`, `/frontend`, `/docs`, `docker-compose.yml`, `.env.example` |
| Qdrant up | Run via Docker Compose, confirm `GET /collections` works |
| Neon project | Create project at [neon.tech](https://neon.tech), copy **pooled** connection string → `DATABASE_URL` in `.env` |
| Schema on Neon | `make db-migrate` (runs `backend/migrations/001_initial.sql`) |
| Cloudinary | Create cloud, copy credentials for raw file uploads (`CLOUDINARY_*`) — see `docs/runbooks/cloudinary-setup.md` |
| FastAPI skeleton | `app/main.py` with health check `/health`, CORS configured for the React dev server |
| SQLModel models | `files`, `processing_jobs`, `segments` tables (from `architecture.md` §8) |
| Redis + Celery skeleton | One no-op task (`ping`) wired up to confirm the worker connects |
| Frontend scaffold | Vite + React + Tailwind, talking to `/health` to confirm connectivity |
| Env management | `.env` for `DATABASE_URL` (Neon), `CLOUDINARY_*`, `OPENAI_API_KEY`, `QDRANT_URL`, `REDIS_URL` |
| CI skeleton | `.github/workflows/ci.yml` — four jobs: unit, integration, system, security (no ruff); pytest marker config in `backend/pyproject.toml` |
| Test layout | `tests/unit/`, `tests/integration/`, `tests/system/`, `tests/security/` with `@pytest.mark.unit` etc. |

**Deliverable:** `docker compose up` brings up frontend + backend + worker + Qdrant + Redis (Neon + Cloudinary are external), frontend shows a green "API connected" state, Neon tables exist, Cloudinary configured, and CI runs.

---

## 4. Phase 1 — Data Ingestion Pipeline (Milestone 1)

**Modules:** M2, M3, M4, M5

### M5 first (shared foundation)
- [ ] `embedding_service.py`: wraps `text-embedding-3-small`, takes `list[str]` → `list[vector]`, includes basic batching
- [ ] `vector_store.py`: Qdrant client wrapper — `create_collection()`, `upsert_segments()`, `search()`
- [ ] Define the `segments` Qdrant collection per `architecture.md` §7

### M2 — Text
- [ ] `/upload` accepts `.txt` / `.md` (PDF optional/stretch)
- [ ] Chunk text into ~300–500 token windows with overlap (tiktoken-aware)
- [ ] Embed each chunk → upsert to Qdrant with `modality=text`
- [ ] Write `segments` rows to Neon

### M3 — Audio
- [ ] `/upload` accepts `.mp3` / `.wav` / `.m4a`
- [ ] Send to Whisper API → get timestamped transcript
- [ ] Window transcript into ~15–30s segments
- [ ] Embed each segment → upsert with `modality=audio`, `start_time`/`end_time`
- [ ] Write `segments` rows to Neon

### M4 — Video
- [ ] `/upload` accepts `.mp4` / `.mov`
- [ ] FFmpeg: extract audio track → reuse M3's Whisper step
- [ ] FFmpeg: extract keyframes every N seconds
- [ ] GPT-4o-mini vision: caption each keyframe
- [ ] Merge transcript + captions into time-aligned segments
- [ ] Embed each segment → upsert with `modality=video`, `start_time`/`end_time`
- [ ] Write `segments` rows to Neon

**Deliverable (matches brief Milestone 1):** "A functional pipeline that takes an input file and successfully generates and stores its vector embedding in the chosen vector database" — for **all three modalities**, each independently testable via `/upload` + a Qdrant point count check.

---

## 5. Phase 2 — Multi-Modal Indexing & Context (Milestone 2)

**Modules:** M1, M2–M5 (enrichment pass), M0

| Task | Detail |
|---|---|
| Job status tracking | `processing_jobs` rows updated through each pipeline stage (`pending → running → done/failed`); `/status/{job_id}` endpoint |
| Payload completeness audit | Confirm every Qdrant point has: original vector, transcript/caption text, `source_path`, `start_time`/`end_time` (where applicable), `title` |
| Visual metadata enrichment | For video, store the **list of per-keyframe captions** (not just merged text) as an additional payload field — satisfies "extracted visual metadata (e.g., object lists, generated captions)" from the brief |
| Error handling | Failed stages (e.g. Whisper timeout) mark `processing_jobs.status='failed'` with `error_message`, file status reflects it, retry endpoint/CLI command |
| `/library` endpoint | Lists files + status + segment counts, for the frontend's "My Index" view |
| (Optional, Phase B from architecture.md) | Add CLIP keyframe embeddings as a second named vector — explicitly **deferred to "future work"** unless time allows |

**Deliverable (matches brief Milestone 2):** Querying Qdrant for any point returns its original vector **and** human-readable transcript/caption/metadata; `/library` + `/status` give visibility into the whole pipeline.

---

## 6. Phase 3 — Search Interface & Demo (Milestone 3)

**Modules:** M6, M7

### M6 — Search & Agents (backend)
- [ ] `router_agent.py`: GPT-4o-mini + function calling → `{modality_filter, search_query}`
- [ ] `/search` endpoint: router → embed → Qdrant search (top-k, optional modality filter) → synthesis agent
- [ ] `synthesis_agent.py`: GPT-4o-mini → short answer + structured list of source segments (file, modality, timestamps, score)
- [ ] Response shape designed for the frontend to render text/audio/video results differently (see `frontend.md`)

### M7 — Frontend (search-facing parts)
- [ ] Search input (the adapted "Chatly" chat box) posts to `/search`
- [ ] Results renderer: text snippet card, audio player seeking to `start_time`, video player seeking to `start_time`
- [ ] Modality filter chips (All / Text / Audio / Video) wired to `/search`'s filter param
- [ ] Upload flow (drag-and-drop or file picker) → `/upload`, with a progress/status indicator polling `/status/{job_id}`
- [ ] "My Index" / Library view → `/library`

**Deliverable (matches brief Milestone 3):** A working web app where a user types each of the brief's example queries (§II.B) and gets back the right modality of result with a working media link/timestamp.

---

## 7. Phase 4 — Testing, Documentation & Submission

**Modules:** M7, M8

| Task | Detail |
|---|---|
| Unit tests | `tests/unit/` — embedding service (mocked OpenAI), chunking logic, Qdrant upsert/search wrapper, router/synthesis agent (mocked); run locally via `pytest -m unit` |
| Integration tests | `tests/integration/` — one flow per modality against real Qdrant + Redis + Neon (`DATABASE_URL`); OpenAI mocked or keyed via CI secret |
| System tests | `tests/system/` — full `docker compose up` stack: health checks, upload→index→search happy path, `/library` and `/status` visibility |
| Security tests | `tests/security/` — upload path traversal, MIME/size enforcement, auth on protected routes; plus `bandit` (SAST) and `pip-audit` (dependency CVEs) in CI |
| CI/CD | `.github/workflows/ci.yml` runs unit → integration → system → security on push/PR; ruff is **not** gated in CI (local dev only) |
| README | Setup instructions, `.env.example`, `docker-compose up` quickstart, architecture diagram embed, CI badge |
| Project report | Architecture decisions (link to `docs/architecture/architecture.md`), challenges (e.g. cross-modal embedding alignment, video processing latency/cost), what was deferred (CLIP/CLAP phase B) and why |
| Demo recording | Walk through: upload one file per modality → run the 4 example queries from the brief → show results with playback |
| Repo hygiene | `.gitignore`, no committed secrets, consistent formatting (`ruff`/`black` locally, `eslint`/`prettier` for frontend) |

**Deliverable (matches Submission Guidelines):** GitHub repo for **Scrutinize** (shared with the relevant person), `docs/architecture/architecture.md` + `docs/plan.md` + `docs/frontend.md` + report, demo video, green CI on `main`.

---

## 8. Suggested Timeline (adjust to your actual deadline)

| Phase | Duration (suggested) |
|---|---|
| Phase 0 — Setup | 0.5–1 day |
| Phase 1 — Ingestion Pipeline | 2–3 days |
| Phase 2 — Indexing & Context | 1–2 days |
| Phase 3 — Search & Demo UI | 2–3 days |
| Phase 4 — Polish & Submission | 1 day |

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Video processing is slow/expensive (many GPT-4o-mini vision calls per video) | Cap keyframes per video (e.g. max 10–15), use short demo videos, document cost in the report |
| "Find a song by XYZ" can't be answered by transcription alone if the audio is instrumental/no lyrics | Document this as a known limitation; rely on filename/metadata matching as a fallback; mention CLAP as future work |
| Whisper/GPT-4o-mini rate limits during a live demo | Pre-index demo files ahead of time; have a fallback recorded demo |
| Scope creep into "OmniAgent"-style generic agents | Keep the agent layer to exactly 2 agents (router, synthesis) per `architecture.md` §4.4 |
| CI flakiness on system tests (Docker timing) | Retry health-check waits; keep system suite small (smoke-level); run heavier flows in integration tier |
| Qdrant payload/schema drift between Phase 1 and Phase 2 | Lock the payload schema (§7 of `architecture.md`) before Phase 1 ingestion starts |