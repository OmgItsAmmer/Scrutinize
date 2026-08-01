.PHONY: help up down logs infra-up infra-down reset-qdrant backend-shell backend-dev worker-dev v2-dev v2-health \
	db-migrate test test-unit test-integration test-system test-security test-evals lint install-backend install-frontend frontend-dev \
	seed-eval-corpus reindex-project backend frontend

# =============================================================================
# Scrutinize — run the entire project
# =============================================================================
# Windows: use Git Bash or WSL for `make`.
#
# FIRST TIME ONLY
#   1. cp .env.example backend/.env
#      Edit backend/.env — Neon DATABASE_URL, Cloudinary, OPENAI_API_KEY, etc.
#   2. make install-backend
#   3. make install-frontend
#   4. make db-migrate
#
# OPTION A — Full stack in Docker (simplest; backend + worker in containers)
#   Terminal 1:  make up-build
#   Terminal 2:  make frontend-dev
#   Do NOT also run make worker-dev — Docker already includes a worker service.
#   App:         http://localhost:5173
#   API docs:    http://localhost:8000/docs
#
# OPTION B — Local backend with hot reload (best for v2 pipeline development)
#   Terminal 1:  make backend           # starts Qdrant + Redis, Phoenix serve, API server, and Celery worker
#   Terminal 2:  make frontend          # starts Vite dev server
#
#   Alternative: you can still run components individually using:
#     make infra-up, make backend-dev, make worker-dev, make frontend-dev, phoenix serve
#
# AFTER STARTUP
#   make logs         — follow Docker service logs
#   make v2-health    — check v2 LLM endpoints (local pipeline)
#   make help         — list all commands
#
# V5 RETRIEVAL EVALS (Phase 0 baseline + regression checks)
#   make seed-eval-corpus   — seed the fixture project used by test-evals (needs
#                             Postgres + Qdrant + OPENAI_API_KEY configured)
#   make test-evals         — run retrieval metrics (Recall@k/MRR/nDCG@k) against
#                             the golden dataset; writes backend/app/evals/results/<sha>.json
#   First run of the reranker/Docling downloads models from Hugging Face —
#   expect a slower first request/ingestion.
#
# V5 REINDEXING (after a parsing/chunking/contextual-retrieval change)
#   make reindex-project PROJECT_ID=<uuid> ARGS="--dry-run"   — preview
#   make reindex-project PROJECT_ID=<uuid> ARGS="--sync"      — run without a worker
#   make reindex-project PROJECT_ID=<uuid>                     — enqueue on Celery
# =============================================================================

help:
	@echo "Scrutinize dev commands"
	@echo ""
	@echo "  Quick start: see instructions at the top of this Makefile."
	@echo ""
	@echo "  Run entire app (Local):"
	@echo "    make backend           - starts Qdrant + Redis, Phoenix serve, API server, and Celery worker"
	@echo "    make frontend          - starts Vite dev server"
	@echo ""
	@echo "  Full stack (Docker):     make up"
	@echo "  v2 local backend:        make v2-dev          (infra + guide; then backend-dev in another terminal)"
	@echo "  Backend only (reload):   make backend-dev"
	@echo "  Check Qdrant + .env:     make check-qdrant"
	@echo "  Celery worker:           make worker-dev  (restart after .env changes!)"
	@echo "  Frontend (Vite):         make frontend-dev"
	@echo "  Redis + Qdrant only:     make infra-up   (qdrant always; redis skipped if port 6379 busy)"
	@echo "  Qdrant only:             make infra-qdrant"
	@echo "  Check v2 LLM:            make v2-health"
	@echo ""
	@echo "  Unit/integration tests:  make test-unit / test-integration / test-system / test-security"
	@echo "  V5 retrieval evals:      make seed-eval-corpus   then   make test-evals"
	@echo "  V5 reindex a project:    make reindex-project PROJECT_ID=<uuid> [ARGS=\"--dry-run\"]"
	@echo ""
	@echo "v2 uses the same FastAPI app — search hits POST /v2/search (frontend: VITE_SEARCH_API=/v2/search)."

# --- Docker full stack ---

up:
	docker compose up

up-build:
	docker compose up --build

build:
	docker compose build

down:
	docker compose down -v

infra-up:
	docker compose up -d qdrant
	-docker compose up -d redis

infra-qdrant:
	docker compose up -d qdrant

infra-down:
	docker compose stop redis qdrant

reset-qdrant:
	docker compose down -v
	docker compose pull qdrant

logs:
	docker compose logs -f

backend-shell:
	docker compose exec backend bash

# --- Local backend (v1 + v2 routes on same server) ---

backend:
	cd backend && python scripts/run_backend.py

frontend: frontend-dev

backend-dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker-dev:
	cd backend && celery -A app.workers.celery_app worker --loglevel=info --pool=solo

check-config:
	cd backend && python scripts/print_config.py

check-qdrant: check-config

# Start infra, then print what to run next for v2 (local Qwen pipeline).
v2-dev: infra-up
	@echo ""
	@echo "=== v2 backend dev ==="
	@echo "1. Ensure backend/.env has:"
	@echo "     REDIS_URL=redis://localhost:6379/0"
	@echo "     LOCAL_LLM_BASE_URL=https://YOUR-NGROK-HOST/api/generate"
	@echo "   For search-only (no uploads): CELERY_TASK_ALWAYS_EAGER=true"
	@echo "   For uploads: keep Redis running + run 'make worker-dev' in another terminal."
	@echo ""
	@echo "2. Terminal A:  make backend-dev"
	@echo "3. Terminal B:  make frontend-dev   (uses /v2/search by default)"
	@echo "4. Optional:    make worker-dev      (file ingestion; uses --pool=solo on Windows)"
	@echo ""
	@echo "API:  http://localhost:8000/docs"
	@echo "v2:   POST /v2/search   GET /v2/llm-health"

v2-health:
	curl -s http://localhost:8000/v2/llm-health

# --- DB / scripts ---

db-migrate:
	cd backend && python scripts/apply_migrations.py

cloudinary-smoke:
	cd backend && python scripts/cloudinary_smoke.py

check-ffmpeg:
	cd backend && python scripts/check_ffmpeg.py

check-text-ingestion:
	cd backend && python scripts/check_text_ingestion.py $(FILE)

check-audio-ingestion:
	cd backend && python scripts/check_audio_ingestion.py $(FILE)

check-video-ingestion:
	cd backend && python scripts/check_video_ingestion.py $(FILE)

check-search:
	cd backend && python scripts/check_search.py $(QUERY)

# V5 Phase 0 — seed/reset the reproducible fixture corpus used by test-evals.
seed-eval-corpus:
	cd backend && python scripts/seed_eval_corpus.py

# V5 M7 — reindex every text file in a project (re-parse/chunk/enrich/embed).
# Usage: make reindex-project PROJECT_ID=<uuid> [ARGS="--dry-run"]
reindex-project:
	cd backend && python scripts/reindex_project.py $(PROJECT_ID) $(ARGS)

install-backend:
	cd backend && pip install -e ".[dev]"

install-frontend:
	cd frontend && npm install

# --- Tests / lint ---

test:
	pytest tests -v

test-unit:
	pytest tests/unit -m unit -v

test-integration:
	pytest tests/integration -m integration -v

test-system:
	pytest tests/system -m system -v

test-security:
	pytest tests/security -m security -v

# V5 Phase 0 — retrieval eval harness. Requires a real Postgres + Qdrant + OpenAI
# environment seeded via `make seed-eval-corpus`. Not part of `make test` / CI.
test-evals:
	pytest tests/evals -m evals -v -s

lint:
	cd backend && ruff check app
	cd backend && ruff format --check app

frontend-dev:
	cd frontend && npm run dev
