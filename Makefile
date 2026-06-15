.PHONY: up down logs backend-shell db-migrate test test-unit test-integration test-system test-security lint install-frontend frontend-dev

up:
	docker compose up --build

down:
	docker compose down -v

reset-qdrant:
	docker compose down -v
	docker compose pull qdrant

logs:
	docker compose logs -f

backend-shell:
	docker compose exec backend bash

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

install-backend:
	cd backend && pip install -e ".[dev]"

install-frontend:
	cd frontend && npm install

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

lint:
	cd backend && ruff check app
	cd backend && ruff format --check app

frontend-dev:
	cd frontend && npm run dev
