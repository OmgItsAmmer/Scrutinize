.PHONY: up down logs backend-shell db-migrate test test-unit test-integration test-system test-security lint

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f

backend-shell:
	docker compose exec backend bash

db-migrate:
	cd backend && python scripts/apply_migrations.py

cloudinary-smoke:
	cd backend && python scripts/cloudinary_smoke.py

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
