# M1 — Backend Core

**Status:** Implemented  
**Location:** `backend/app/`

## Purpose

FastAPI application shell: Neon-backed models, health/status API, job orchestration, Cloudinary storage client, and Celery worker wiring.

## Package layout

```text
backend/app/
├── __init__.py                 # __version__ = "0.1.0"
├── main.py                     # create_app(), CORS, lifespan (Neon init)
├── core/
│   ├── config.py               # Settings from .env
│   ├── database.py             # SQLModel engine (Neon SSL, pool_pre_ping)
│   └── deps.py                 # get_db_session, get_job_orchestrator, get_cloudinary_storage
├── models/
│   ├── file.py                 # File, FileModality, FileStatus
│   ├── processing_job.py       # ProcessingJob, JobStatus
│   └── segment.py              # Segment
├── schemas/
│   ├── health.py               # HealthResponse, DependencyCheck
│   ├── job.py                  # JobStatusResponse
│   ├── file.py                 # FileRead, FileCreate
│   ├── segment.py              # SegmentRead, SegmentCreate
│   └── storage.py              # StorageUploadResponse
├── api/
│   ├── router.py               # Includes core routes
│   └── routes.py               # GET /health, GET /status/{job_id}
├── services/
│   ├── health.py               # DB, Redis, Qdrant probes
│   ├── job_orchestrator.py     # File/job/segment CRUD
│   └── cloudinary_storage.py   # Upload wrapper (Cloudinary SDK)
└── workers/
    ├── celery_app.py           # Celery app (Redis broker)
    └── tasks.py                # ping, process_file (placeholder)
```

Supporting files:

- `backend/migrations/001_initial.sql` — Neon DDL
- `backend/pyproject.toml` — dependencies incl. `cloudinary`, `sqlmodel`, `celery`

## API endpoints

| Method | Path | Response | Description |
|---|---|---|---|
| `GET` | `/health` | `HealthResponse` | Overall `ok`/`degraded` + dependency checks |
| `GET` | `/status/{job_id}` | `JobStatusResponse` | Job by UUID; 404 if missing |

OpenAPI: http://localhost:8000/docs

### Health response shape

```json
{
  "status": "ok",
  "service": "scrutinize",
  "version": "0.1.0",
  "checks": {
    "database": { "status": "ok" },
    "redis": { "status": "ok" },
    "qdrant": { "status": "ok" }
  }
}
```

`service` is `settings.app_name.lower()`. Overall status is `ok` only when all three checks pass.

## Data models (Neon)

| Model | Table | Enums |
|---|---|---|
| `File` | `files` | `FileModality`: text, audio, video · `FileStatus`: uploaded, processing, indexed, failed |
| `ProcessingJob` | `processing_jobs` | `JobStatus`: pending, running, done, failed |
| `Segment` | `segments` | Shares `FileModality`; `id` will match Qdrant point id in later phases |

`files.storage_path` stores the Cloudinary `secure_url` once uploads are implemented.

Schema: [schema_doc.md](../db/schema_doc.md) · apply: `make db-migrate`

## JobOrchestrator

| Method | Description |
|---|---|
| `create_file(...)` | Insert `files` row |
| `create_job(file_id, stage)` | Insert `processing_jobs` row (`pending`) |
| `get_job(job_id)` | Lookup or `None` |
| `update_job_status(job_id, status, error_message?)` | Update job + `updated_at` |
| `mark_file_status(file_id, status)` | Update file status |
| `get_file(file_id)` | Lookup or `None` |
| `list_files(limit, offset)` | Recent files, paginated |
| `list_jobs_for_file(file_id)` | All jobs for a file |
| `create_segment(...)` | Insert `segments` row (optional `segment_id`) |
| `list_segments_for_file(file_id)` | Segments for a file |

## CloudinaryStorage

`backend/app/services/cloudinary_storage.py` — requires `settings.cloudinary_configured`.

| Method | Description |
|---|---|
| `upload_bytes(data, filename, modality, resource_type="auto")` | Upload from bytes → `StorageUploadResult` |
| `upload_file(path, filename, modality, resource_type="auto")` | Upload from disk path |
| `delete(public_id, resource_type="image")` | Destroy asset |

Uploads go to `{CLOUDINARY_FOLDER}/{modality}/` (default `scrutinize/text/`, etc.).

Inject via `get_cloudinary_storage()` in `core/deps.py`. Not yet wired to an HTTP route.

## Celery

| Setting | Source |
|---|---|
| Broker / backend | `REDIS_URL` (or `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`) |
| App name | `scrutinize` |

| Task | Name | Returns |
|---|---|---|
| `ping` | `ping` | `"pong"` |
| `process_file` | `process_file` | Placeholder dict (future ingestion) |

Worker command (also used in Docker Compose):

```bash
celery -A app.workers.celery_app worker --loglevel=info
```

## Configuration (`core/config.py`)

| Setting | Env var | Default |
|---|---|---|
| `database_url` | `DATABASE_URL` | `""` (required at startup) |
| `redis_url` | `REDIS_URL` | `redis://localhost:6379/0` |
| `qdrant_url` | `QDRANT_URL` | `http://localhost:6333` |
| `cloudinary_cloud_name` | `CLOUDINARY_CLOUD_NAME` | `""` |
| `cloudinary_api_key` | `CLOUDINARY_API_KEY` | `""` |
| `cloudinary_api_secret` | `CLOUDINARY_API_SECRET` | `""` |
| `cloudinary_folder` | `CLOUDINARY_FOLDER` | `scrutinize` |
| `openai_api_key` | `OPENAI_API_KEY` | `""` |
| `cors_origins` | — | `localhost:5173`, `127.0.0.1:5173` |

Startup fails with `RuntimeError` if `DATABASE_URL` is empty (`main.py` lifespan).

## Local run

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

Requires `.env` at repo root with Neon `DATABASE_URL`. Redis + Qdrant reachable for a green `/health`.

## Dependencies

- **M0** — Docker, env, Neon, Redis, Qdrant

## Used by

- **M7** — consumes `GET /health`
- **M8** — unit/integration tests for routes, orchestrator, health
