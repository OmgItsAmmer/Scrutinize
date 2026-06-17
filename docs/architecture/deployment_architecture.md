
# Deployment architecture (Scrutinize)

This document describes what must be deployed, where it runs, and how the pieces connect to make the full app work.

## High-level overview

Scrutinize is split into:

- A **frontend SPA** (React/Vite) deployed to **Vercel**
- A **public backend API** (FastAPI) deployed to **Fly.io** as `scrutinize-api`
- A **background worker** (Celery) deployed to **Fly.io** as `scrutinize-worker`
- A **Redis broker** deployed to **Fly.io** as `scrutinize-redis`
- External managed services:
  - **Neon Postgres** (metadata + job state)
  - **Cloudinary** (raw file storage)
  - **Qdrant** (vector search; typically Qdrant Cloud)
  - **OpenAI** (transcription/embeddings/vision, depending on modality)

## Connection diagram

```text
User browser
   |
   | 1) HTTPS (Vercel)
   v
Vercel: Frontend (React SPA)
   |  VITE_API_URL = https://scrutinize-api.fly.dev  (baked at build time)
   |
   | 2) HTTPS API calls (/health, /library, /upload, /search, /status)
   v
Fly.io: scrutinize-api (FastAPI)
   |
   | 3) SQL (Neon Postgres)  <-- DATABASE_URL
   +-----> Neon Postgres (files, processing_jobs, segments metadata)
   |
   | 4) TCP (Fly private network)  <-- REDIS_URL=redis://scrutinize-redis.flycast:6379
   +-----> Fly.io: scrutinize-redis (Celery broker + result backend)
   |
   | 5) HTTPS (Qdrant Cloud)  <-- QDRANT_URL (+ QDRANT_API_KEY if needed)
   +-----> Qdrant (vectors)
   |
   | 6) HTTPS (Cloudinary)  <-- CLOUDINARY_*
   +-----> Cloudinary (uploaded file bytes)
   |
   | 7) Enqueue background work (Celery task.delay(job_id))
   v
Fly.io: scrutinize-worker (Celery)
   |
   | consumes from Redis, reads/writes Neon, downloads from Cloudinary,
   | calls OpenAI, writes vectors to Qdrant.
   v
External services (Neon + Cloudinary + OpenAI + Qdrant)
```

## What is deployed where

### 1) Frontend (Vercel)

- Host: Vercel
- Build: Vite/React
- Required config:
  - `VITE_API_URL` must point to the Fly API base URL.

In code, all frontend API requests are built from `VITE_API_URL`:

```11:43:frontend/src/api/client.ts
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  ...
}
```

Operational note: the UI wakes the Fly API by polling `/health` on landing:

```297:308:frontend/src/context/AppContext.tsx
// Wake API + Redis on landing (Fly auto_start on first /health request).
void pollHealth().then((ok) => schedulePoll(ok ? 120_000 : 5_000));
```

### 2) API (Fly.io: `scrutinize-api`)

- Host: Fly.io
- Public endpoint: `https://scrutinize-api.fly.dev` (or your custom domain)
- Container: built from `backend/Dockerfile`
- Responsibilities:
  - Serve HTTP API for the frontend
  - Read/write metadata in Neon
  - Upload file bytes to Cloudinary
  - Enqueue Celery jobs to Redis
  - Serve search (calls Qdrant) and library browsing (Neon + Cloudinary links)

Critical requirement: the API will not start without `DATABASE_URL`:

```14:26:backend/app/main.py
async def lifespan(_: FastAPI):
    settings = get_settings()
    if not settings.database_url.strip():
        raise RuntimeError("DATABASE_URL is required. ...")
    init_db()
    yield
```

### 3) Worker (Fly.io: `scrutinize-worker`)

- Host: Fly.io
- Not publicly reachable (no HTTP service)
- Container: built from the same `backend/Dockerfile`
- Responsibilities:
  - Consume Celery tasks from Redis
  - For each job:
    - Download file from Cloudinary
    - Run modality-specific processing (FFmpeg for video/audio where needed)
    - Call OpenAI (transcription/embeddings/vision)
    - Write vectors to Qdrant
    - Update job state + segments metadata in Neon

Important: the worker will not auto-start from web traffic. It must be scaled up:

```10:20:deploy/fly/worker/fly.toml
[processes]
  worker = "celery -A app.workers.celery_app worker --loglevel=info"

# Worker has no public HTTP service — omit [http_service]
# It will NOT auto-start from browser traffic; scale manually (§5d).
```

### 4) Redis (Fly.io: `scrutinize-redis`)

- Host: Fly.io
- Purpose: Celery broker + result backend
- Should be addressed over Fly private networking:
  - `REDIS_URL=redis://scrutinize-redis.flycast:6379`

### 5) Neon Postgres (managed, external)

- Host: Neon
- Purpose:
  - `files`, `processing_jobs`, `segments` tables (source of truth for library + job status)
- Connection:
  - `DATABASE_URL` in both API and worker.
- Deployment note:
  - Migrations are applied from your machine; they are not automatically run on Fly during deploy.

### 6) Cloudinary (managed, external)

- Host: Cloudinary
- Purpose: store uploaded raw content (text/audio/video)
- Used by:
  - API: upload bytes during `/upload`
  - Worker: download bytes for processing

### 7) Qdrant (managed, external by default)

- Host: Qdrant Cloud recommended for budget.
- Used by:
  - Worker: upsert vectors
  - API: search queries

## Minimal “app works” requirements

The app is only fully functional when:

1. Frontend is deployed with `VITE_API_URL` pointing at the API.
2. API is deployed and has Fly secrets set:
   - `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`, `CLOUDINARY_*`, `OPENAI_API_KEY`, `CORS_ORIGINS`
3. Neon schema/migrations match the deployed backend code.
4. Redis is deployed and reachable over `.flycast`.
5. For ingestion (new uploads to become searchable), the worker is running (scaled to 1+) and has the same required secrets as the API.

## Typical deployment sequence (recommended)

1. Neon: apply migrations to the target database.
2. Fly: deploy `scrutinize-redis` (one-time, or when config changes).
3. Fly: deploy `scrutinize-api`.
4. Fly: deploy `scrutinize-worker` (optional), then keep it scaled to 0 until you need ingestion.
5. Vercel: deploy frontend with `VITE_API_URL=https://scrutinize-api.fly.dev`.
6. Fly: update `CORS_ORIGINS` on `scrutinize-api` to include the Vercel origin.

