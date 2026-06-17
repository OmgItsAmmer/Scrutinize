
# Deployment issue: Fly backend can’t read/write Neon after deploy

## What you observed

- The deployed backend “stopped working” after a deployment-related change.
- It cannot fetch from the database and new uploads are not being processed.

This combination almost always means the API is failing its Neon connection (so it cannot read library rows or create `files` / `processing_jobs` rows during upload).

The upload endpoint writes to Neon before enqueueing Celery:

```1:96:backend/app/api/upload.py
async def upload_file(
    file: UploadFile = File(...),
    orchestrator: JobOrchestrator = Depends(get_job_orchestrator),
    storage: CloudinaryStorage = Depends(get_cloudinary_storage),
    settings: Settings = Depends(get_app_settings),
) -> UploadResponse:
    ...
    upload_result = storage.upload_bytes(...)

    file_record = orchestrator.create_file(...)
    job = orchestrator.create_job(...)
    orchestrator.mark_file_status(...)

    task = TASK_BY_MODALITY[modality.value]
    task.delay(str(job.id))
```

So if Neon is unavailable or schema is wrong, uploads fail immediately (or fail before a job can run).

## The “proper reason” (most likely root cause)

### Root cause A (most common): the new image expects DB schema changes, but migrations were not applied to Neon

Fly deploys a new container image, but it does **not** run DB migrations for you. If the code you deployed added/changed tables or columns and Neon did not get the matching migrations, then any endpoint that queries those new columns/tables will start failing.

This explains a sudden “everything DB-related broke right after deploy” without touching secrets.

**Fix:** apply backend migrations to Neon before (or immediately after) deploying the new backend image.

### Root cause B: `DATABASE_URL` (or SSL settings) is wrong/missing on Fly

The API hard-fails on startup if `DATABASE_URL` is empty:

```14:24:backend/app/main.py
async def lifespan(_: FastAPI):
    settings = get_settings()
    if not settings.database_url.strip():
        raise RuntimeError(
            "DATABASE_URL is required. Add your Neon Postgres connection string to .env "
            "(see .env.example)."
        )
    init_db()
    yield
```

If `DATABASE_URL` is missing, the API won’t even boot. If it’s present but wrong (wrong host/user/pass/db, missing `sslmode=require`, or using a non-pooled Neon URL that is being blocked/limited), `/health` will show `database: error`.

**Fix:** set/correct `DATABASE_URL` on `scrutinize-api` (and `scrutinize-worker`) and ensure it is Neon’s **pooled** URL with `sslmode=require`.

### Root cause C (separate symptom): uploads “stay pending” because the worker is scaled to 0

Even when the API is healthy, uploads will remain `pending` until the worker is running because the API enqueues a Celery job (`task.delay(...)`), and only the worker consumes Redis.

This is an expected “budget profile” behavior (scale-to-zero worker).

**Fix:** scale the worker to 1 when you want ingestion.

## Manual diagnosis checklist (no commands required here, but exact things to check)

### 1) Check API health page and look at the `database` check

The `/health` endpoint explicitly checks Neon with `SELECT 1`:

```8:16:backend/app/services/health.py
def check_database(session: Session) -> DependencyCheck:
    try:
        session.connection().exec_driver_sql("SELECT 1")
        return DependencyCheck(status="ok")
    except Exception as exc:  # noqa: BLE001
        return DependencyCheck(status="error", detail=str(exc))
```

- If `database.status` is `error`, the backend cannot talk to Neon.
- The `detail` string will usually tell you whether it is “password authentication failed”, “could not translate host name”, “SSL required”, “timeout”, etc.

### 2) Verify Fly secrets on `scrutinize-api`

In Fly dashboard (or via CLI), confirm these exist on the **API** app:

- `DATABASE_URL` (Neon pooled URL, includes `?sslmode=require`)
- `REDIS_URL` (should be `redis://scrutinize-redis.flycast:6379`)
- `QDRANT_URL` (Qdrant Cloud HTTPS URL, or internal if self-hosted)
- `CLOUDINARY_*` (required for uploads)
- `OPENAI_API_KEY` (required for ingestion after worker runs)

The runbook’s expected values:

```350:367:docs/runbooks/fly-io-deploy.md
fly secrets set -a scrutinize-api \
  DATABASE_URL="postgresql+psycopg://USER:PASSWORD@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require" \
  REDIS_URL="redis://scrutinize-redis.flycast:6379" \
  QDRANT_URL="https://YOUR-CLUSTER-ID.region.aws.cloud.qdrant.io" \
  OPENAI_API_KEY="sk-..." \
  CLOUDINARY_CLOUD_NAME="your_cloud" \
  CLOUDINARY_API_KEY="..." \
  CLOUDINARY_API_SECRET="..." \
  CLOUDINARY_FOLDER="scrutinize" \
  CORS_ORIGINS='["https://YOUR-PROJECT.vercel.app"]'
```

If `DATABASE_URL` is missing/wrong: set it and let Fly restart the app.

### 3) Verify Neon status and credentials

In Neon dashboard:

- Confirm the project/branch is not paused/suspended.
- Confirm you are using the **pooled** connection string endpoint (`...-pooler...`).
- If you recently reset Neon passwords or rotated credentials, update `DATABASE_URL` on Fly.

### 4) Confirm migrations are applied to Neon for the deployed backend version

If your deploy included backend changes that touch models/tables:

- Run migrations locally against Neon (recommended path is in the runbook).
- Then redeploy the API.

The runbook explicitly calls out that migrations run from your machine, not in the image:

```131:138:docs/runbooks/fly-io-deploy.md
- Neon schema applied **before** first deploy:
  ```bash
  make install-backend
  make db-migrate
  ```
  Migrations run against Neon from your machine; the backend Docker image does not include `backend/scripts/`.
```

### 5) If “uploads succeed but nothing processes”, start the worker

The worker is intentionally not auto-started by HTTP traffic:

```10:20:deploy/fly/worker/fly.toml
[processes]
  worker = "celery -A app.workers.celery_app worker --loglevel=info"

# Worker has no public HTTP service — omit [http_service]
# It will NOT auto-start from browser traffic; scale manually (§5d).
```

If you want ingestion to work, the worker must be running (and pointed at the same `REDIS_URL` and `DATABASE_URL` as the API).

## Concrete “fix plan” (in order)

1. Use `/health` to confirm whether the DB check is failing and read the error detail.
2. Fix `DATABASE_URL` on **both** `scrutinize-api` and `scrutinize-worker` if needed (pooled Neon URL + `sslmode=require`).
3. Apply migrations to Neon for the currently deployed backend code.
4. Ensure `CLOUDINARY_*` are present on the API (uploads depend on Cloudinary).
5. Scale `scrutinize-worker` to 1 when you want ingestion; scale back to 0 to save money when not ingesting.

## Why “creating a Fly deploy token” didn’t break anything by itself

Creating a deploy token (for GitHub Actions) does not change any running Fly machines or app secrets. The breakage happens when a new image is deployed or when secrets/DB credentials drift.

If this issue started immediately after the first GitHub Actions deploy ran, the most likely explanation is “new backend image + migrations not applied” or “the API app was redeployed but the required Fly secrets were never set (or were set on the wrong app)”.

