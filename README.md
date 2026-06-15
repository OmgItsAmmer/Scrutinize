# Scrutinize

Multi-modal AI embedding and retrieval system. Upload text, audio, and video; search across all modalities with natural language.

## Stack

- **Frontend** — React + Vite + Tailwind
- **Backend** — FastAPI + SQLModel + Celery
- **Data** — Neon (Postgres), Redis, Qdrant, Cloudinary (raw files)

## Quick start

1. Create a [Neon](https://neon.tech) project and copy the **pooled** connection string.

2. Set up [Cloudinary](docs/runbooks/cloudinary-setup.md) and copy credentials into `.env`:

   ```bash
   cp .env.example .env
   # Edit .env — Neon DATABASE_URL + Cloudinary credentials
   ```

3. Apply the database schema to Neon:

   ```bash
   make install-backend
   make db-migrate
   ```

4. Start the stack (Redis, Qdrant, backend, worker, frontend):

   ```bash
   docker compose up --build
   ```

5. Open the app:

   - Frontend: http://localhost:5173
   - API docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health

The frontend shows a green **API connected** badge when `/health` reports all dependencies are reachable.

## Local development (without Docker)

### Backend

```bash
cd backend
pip install -e ".[dev]"
# Ensure .env has Neon DATABASE_URL and Cloudinary credentials
uvicorn app.main:app --reload --port 8000
```

Start Redis and Qdrant separately (or use `docker compose up redis qdrant`).

### Worker

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Tests

```bash
make install-backend
make test-unit
make test-integration
```

See `docs/plan.md` for the full test tier breakdown.

## Documentation

- [Architecture](docs/architecture/architecture.md)
- [Project plan](docs/plan.md)
- [Modules](docs/modules/README.md)
- [Runbooks](docs/runbooks/README.md)
- [Database schema](docs/db/schema_doc.md)

## Environment variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | **Required.** Neon Postgres connection string (`postgresql+psycopg://…?sslmode=require`) |
| `REDIS_URL` | Redis broker for Celery |
| `QDRANT_URL` | Qdrant HTTP API base URL |
| `OPENAI_API_KEY` | OpenAI API key (Phase 1+) |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret |
| `CLOUDINARY_FOLDER` | Upload folder prefix (default `scrutinize`) |
| `VITE_API_URL` | Backend URL consumed by the frontend |

## GitHub Actions secrets

For integration/system CI jobs, configure:

- `DATABASE_URL` — Neon pooled connection string
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`
- `OPENAI_API_KEY` — as needed for Phase 1+
