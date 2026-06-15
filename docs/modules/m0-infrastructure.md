# M0 — Infrastructure & DevOps

**Status:** Implemented  
**Location:** Repository root, `.github/workflows/`, `docker-compose.yml`

## Purpose

Shared foundation: monorepo layout, Docker services, environment configuration, Neon/Cloudinary wiring, CI, and dev tooling.

## Repository layout

```text
Scrutinize/
├── backend/                          # M1 FastAPI app
├── frontend/                         # M7 React app
├── docs/                             # Architecture, plan, modules, runbooks, db
├── tests/                            # M8 — unit | integration | system | security
├── docker-compose.yml
├── .env.example
├── Makefile
├── pytest.ini
└── .github/workflows/ci.yml
```

## Deliverables

| Artifact | Role |
|---|---|
| `docker-compose.yml` | Redis, Qdrant, backend, Celery worker, frontend |
| `.env.example` | Template for Neon, Cloudinary, Redis, Qdrant, OpenAI |
| `.github/workflows/ci.yml` | unit / integration / system / security jobs (no ruff gate) |
| `Makefile` | Dev and test commands (see below) |
| `pytest.ini` | Markers + `pythonpath = backend` |
| `backend/.dockerignore`, `frontend/.dockerignore` | Slim Docker build context |
| `backend/scripts/apply_migrations.py` | Apply `001_initial.sql` to Neon |
| `backend/scripts/cloudinary_smoke.py` | Verify Cloudinary credentials |

## Docker Compose services

| Service | Port | Role |
|---|---|---|
| `redis` | 6379 | Celery broker + result backend |
| `qdrant` | 6333 | Vector DB (used by health check; ingestion in later phases) |
| `backend` | 8000 | FastAPI (`env_file: .env`) |
| `worker` | — | `celery -A app.workers.celery_app worker` |
| `frontend` | 5173 | Vite dev server |

**Hosted (not in Compose):** Neon Postgres (`DATABASE_URL`), Cloudinary (`CLOUDINARY_*`).

Backend/worker override `REDIS_URL` and `QDRANT_URL` to Docker service hostnames; all other vars come from `.env`.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes | Neon pooled connection string |
| `CLOUDINARY_CLOUD_NAME` | Phase 1+ uploads | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Phase 1+ uploads | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Phase 1+ uploads | Cloudinary API secret |
| `CLOUDINARY_FOLDER` | No (default `scrutinize`) | Upload folder prefix |
| `REDIS_URL` | No (default localhost) | Celery broker |
| `QDRANT_URL` | No (default localhost) | Qdrant HTTP API |
| `OPENAI_API_KEY` | Phase 1+ | OpenAI API |
| `VITE_API_URL` | No (default `http://localhost:8000`) | Frontend → backend URL |

Setup guides: [Cloudinary runbook](../runbooks/cloudinary-setup.md)

## Makefile targets

| Target | Command |
|---|---|
| `make up` | `docker compose up --build` |
| `make down` | `docker compose down -v` |
| `make logs` | Follow container logs |
| `make db-migrate` | Apply SQL schema to Neon |
| `make cloudinary-smoke` | Test Cloudinary upload |
| `make install-backend` | `pip install -e "./backend[dev]"` |
| `make install-frontend` | `npm install` in `frontend/` |
| `make test-unit` | `pytest tests/unit -m unit` |
| `make test-integration` | `pytest tests/integration -m integration` |
| `make test-system` | `pytest tests/system -m system` |
| `make test-security` | `pytest tests/security -m security` |
| `make lint` | Ruff check/format on `backend/app` (local only) |

## CI/CD

Four jobs on push/PR to `main` (`.github/workflows/ci.yml`):

| Job | Scope |
|---|---|
| `unit-tests` | SQLite in tests; Redis/Qdrant mocked |
| `integration-tests` | Redis + Qdrant service containers; optional Neon via secret |
| `system-tests` | `docker compose up` when compose file present |
| `security-tests` | Bandit, pip-audit, security pytest suite |

GitHub secrets: `DATABASE_URL`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`, `OPENAI_API_KEY`.

Ruff is **not** gated in CI.

## Quick start

```bash
cp .env.example .env
# Set DATABASE_URL (Neon) and CLOUDINARY_* in .env
make install-backend
make db-migrate
docker compose up --build
```

## Consumed by

- **M1** — Neon, Redis, Qdrant, Cloudinary config
- **M7** — frontend Docker service, `VITE_API_URL`
- **M8** — CI workflow, test layout
