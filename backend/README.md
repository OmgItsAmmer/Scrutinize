# Scrutinize Backend

FastAPI application for the Scrutinize multi-modal ingestion and retrieval system.

## Structure

See [M1 module doc](../docs/modules/m1-backend-core.md) for the full package layout.

## Local development

```bash
pip install -e ".[dev]"
# Set DATABASE_URL in repo-root .env to your Neon pooled connection string
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Start Redis and Qdrant locally, or run infra only:

```bash
docker compose up redis qdrant
```

## Database (Neon)

Relational metadata (`files`, `processing_jobs`, `segments`) lives in **Neon Postgres**, not in Docker Compose.

1. Create a Neon project and copy the pooled connection string into `.env` as `DATABASE_URL`.
2. Apply migrations:

   ```bash
   make db-migrate
   # or: cd backend && python scripts/apply_migrations.py
   ```

SQLModel `create_all()` also runs on app startup for dev parity.

Schema reference: [docs/db/schema_doc.md](../docs/db/schema_doc.md)

## Celery worker

```bash
celery -A app.workers.celery_app worker --loglevel=info
```

See the repository root [README.md](../README.md) for Docker Compose setup.
