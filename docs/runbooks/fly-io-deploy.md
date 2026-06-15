# Runbook — Deploy Scrutinize on Fly.io

Deploy the full Scrutinize stack to [Fly.io](https://fly.io): FastAPI backend, Celery worker, React frontend, plus Redis and Qdrant. Neon, Cloudinary, and OpenAI stay as external managed services (same as local Docker Compose).

**Used by:** M0 production hosting, demo deployments, CI smoke targets against a live URL.

---

## Architecture on Fly.io

```text
                    ┌─────────────────────────────────────────┐
                    │           External (unchanged)           │
                    │  Neon · Cloudinary · OpenAI              │
                    └─────────────────────────────────────────┘
                                        ▲
          ┌─────────────────────────────┼─────────────────────────────┐
          │                             │                             │
   scrutinize-web              scrutinize-api                 scrutinize-worker
   (React static)              (FastAPI + /health)            (Celery + FFmpeg)
          │                             │                             │
          └─────────────── HTTPS ───────┘                             │
                                        │                             │
                    Fly private network (.internal)                     │
                    ┌───────────────────┴───────────────────┐         │
                    │  scrutinize-redis (Upstash)           │◄────────┘
                    │  scrutinize-qdrant (volume-backed)    │◄────────┘
                    └───────────────────────────────────────┘
```

| Fly app | Image / build | Role |
|---|---|---|
| `scrutinize-api` | `backend/Dockerfile` | Public HTTPS API (`:8000`) |
| `scrutinize-worker` | `backend/Dockerfile` (worker CMD) | Background ingestion (Whisper, FFmpeg, embeddings) |
| `scrutinize-web` | Production frontend Dockerfile (see §5) | Static React UI |
| `scrutinize-redis` | Upstash via `fly redis create` | Celery broker + result backend |
| `scrutinize-qdrant` | `qdrant/qdrant:v1.18.2` + volume | Vector store (match `docker-compose.yml`) |

Keep Qdrant at **v1.18.x** — it must stay compatible with `qdrant-client` in `backend/pyproject.toml`.

---

## Prerequisites

- [Fly.io account](https://fly.io/app/sign-up) and billing enabled (worker + Qdrant need more than the smallest free allowance for video jobs)
- [`flyctl` installed](https://fly.io/docs/hands-on/install-flyctl/) and logged in (`fly auth login`)
- Scrutinize repo cloned locally
- External services already configured:
  - [Neon](https://neon.tech) — pooled `DATABASE_URL` (see [README](../../README.md#quick-start))
  - [Cloudinary](cloudinary-setup.md) — `CLOUDINARY_*`
  - OpenAI — `OPENAI_API_KEY` (Phase 1+ ingestion and search)
- Neon schema applied **before** first deploy:

  ```bash
  make install-backend
  make db-migrate
  ```

  Migrations run against Neon from your machine; the backend Docker image does not include `backend/scripts/`.

---

## 1. Install and authenticate Fly CLI

```powershell
# Windows (PowerShell) — see fly.io docs for other platforms
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"

fly version
fly auth login
```

Pick a Fly **organization** when prompted (`fly orgs list` to inspect).

---

## 2. Provision Redis (Upstash)

From repo root:

```bash
fly redis create --name scrutinize-redis --region ord --no-replicas
```

Save the printed **`REDIS_URL`** (TLS URL is fine for Celery). Example:

```text
redis://default:PASSWORD@fly-scrutinize-redis.upstash.io:6379
```

You will set this secret on both `scrutinize-api` and `scrutinize-worker`.

---

## 3. Provision Qdrant (self-hosted on Fly)

### 3a. Create the app and volume

```bash
fly apps create scrutinize-qdrant
fly volumes create qdrant_data --size 10 --region ord -a scrutinize-qdrant
```

Use the same **region** (`ord`, `iad`, etc.) for all Scrutinize apps to keep private networking latency low.

### 3b. Add `fly.toml` for Qdrant

Create `deploy/fly/qdrant/fly.toml` (or any path outside the backend build context):

```toml
app = "scrutinize-qdrant"
primary_region = "ord"

[build]
  image = "qdrant/qdrant:v1.18.2"

[mounts]
  source = "qdrant_data"
  destination = "/qdrant/storage"

[[services]]
  protocol = "tcp"
  internal_port = 6333
  processes = ["app"]

  [[services.ports]]
    port = 6333

[checks]
  [checks.http]
    grace_period = "30s"
    interval = "15s"
    method = "GET"
    path = "/collections"
    port = 6333
    timeout = "5s"
    type = "http"
```

Deploy:

```bash
fly deploy -c deploy/fly/qdrant/fly.toml -a scrutinize-qdrant
```

Internal base URL for backend and worker:

```text
http://scrutinize-qdrant.internal:6333
```

**Alternative:** [Qdrant Cloud](https://cloud.qdrant.io/) — set `QDRANT_URL` to the cloud cluster HTTPS URL and skip this app.

---

## 4. Deploy the backend API

### 4a. Create the app

```bash
fly apps create scrutinize-api
```

### 4b. Add `deploy/fly/api/fly.toml`

```toml
app = "scrutinize-api"
primary_region = "ord"

[build]
  dockerfile = "../../../backend/Dockerfile"
  context = "../../../backend"

[env]
  ENVIRONMENT = "production"
  DEBUG = "false"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 1

  [http_service.concurrency]
    type = "requests"
    hard_limit = 50
    soft_limit = 40

[[vm]]
  memory = "512mb"
  cpu_kind = "shared"
  cpus = 1

[checks]
  [checks.health]
    grace_period = "20s"
    interval = "15s"
    method = "GET"
    path = "/health"
    port = 8000
    timeout = "5s"
    type = "http"
```

Adjust `context` / `dockerfile` paths if you place `fly.toml` elsewhere.

### 4c. Set secrets

Replace placeholders with real values. Run from repo root:

```bash
fly secrets set -a scrutinize-api \
  DATABASE_URL="postgresql+psycopg://USER:PASSWORD@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require" \
  REDIS_URL="redis://default:PASSWORD@fly-scrutinize-redis.upstash.io:6379" \
  QDRANT_URL="http://scrutinize-qdrant.internal:6333" \
  OPENAI_API_KEY="sk-..." \
  CLOUDINARY_CLOUD_NAME="your_cloud" \
  CLOUDINARY_API_KEY="..." \
  CLOUDINARY_API_SECRET="..." \
  CLOUDINARY_FOLDER="scrutinize" \
  CORS_ORIGINS='["https://scrutinize-web.fly.dev"]'
```

Notes:

- **`CORS_ORIGINS`** must be a JSON array string. Add custom domains when you attach them.
- Set `CORS_ORIGINS` again after the frontend app exists (replace `scrutinize-web.fly.dev` with your actual hostname).
- Never commit secrets to git.

### 4d. Deploy

```bash
fly deploy -c deploy/fly/api/fly.toml -a scrutinize-api
```

Verify:

```bash
fly open /health -a scrutinize-api
curl -s https://scrutinize-api.fly.dev/health | jq .
```

Expect `"status": "ok"` (or equivalent) with database, Redis, and Qdrant checks passing.

---

## 5. Deploy the Celery worker

Video ingestion runs FFmpeg inside the worker container (same image as the API). Give it more memory than the API.

### 5a. Create the app

```bash
fly apps create scrutinize-worker
```

### 5b. Add `deploy/fly/worker/fly.toml`

```toml
app = "scrutinize-worker"
primary_region = "ord"

[build]
  dockerfile = "../../../backend/Dockerfile"
  context = "../../../backend"

[env]
  ENVIRONMENT = "production"

[processes]
  worker = "celery -A app.workers.celery_app worker --loglevel=info"

[[vm]]
  memory = "2gb"
  cpu_kind = "shared"
  cpus = 2

# Worker has no public HTTP service — omit [http_service]
```

### 5c. Set secrets (same connectivity as API)

```bash
fly secrets set -a scrutinize-worker \
  DATABASE_URL="postgresql+psycopg://..." \
  REDIS_URL="redis://..." \
  QDRANT_URL="http://scrutinize-qdrant.internal:6333" \
  OPENAI_API_KEY="sk-..." \
  CLOUDINARY_CLOUD_NAME="..." \
  CLOUDINARY_API_KEY="..." \
  CLOUDINARY_API_SECRET="..." \
  CLOUDINARY_FOLDER="scrutinize"
```

### 5d. Deploy and scale

```bash
fly deploy -c deploy/fly/worker/fly.toml -a scrutinize-worker
fly scale count worker=1 -a scrutinize-worker
fly logs -a scrutinize-worker
```

Look for `celery@... ready.` in logs. Increase `worker` count if upload queues back up.

---

## 6. Deploy the frontend

The repo’s `frontend/Dockerfile` runs the Vite **dev** server. Production on Fly needs a static build baked in at image build time.

### 6a. Create production assets

Add `frontend/nginx.conf`:

```nginx
server {
    listen 8080;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Add `frontend/Dockerfile.prod`:

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
```

### 6b. Create the Fly app

```bash
fly apps create scrutinize-web
```

### 6c. Add `deploy/fly/web/fly.toml`

```toml
app = "scrutinize-web"
primary_region = "ord"

[build]
  dockerfile = "../../../frontend/Dockerfile.prod"
  context = "../../../frontend"
  [build.args]
    VITE_API_URL = "https://scrutinize-api.fly.dev"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 1

[[vm]]
  memory = "256mb"
  cpu_kind = "shared"
  cpus = 1
```

`VITE_API_URL` is **build-time only**. Rebuild and redeploy the frontend whenever the API hostname changes.

### 6d. Deploy

```bash
fly deploy -c deploy/fly/web/fly.toml -a scrutinize-web
fly open -a scrutinize-web
```

### 6e. Update API CORS

After you know the frontend URL:

```bash
fly secrets set -a scrutinize-api \
  CORS_ORIGINS='["https://scrutinize-web.fly.dev"]'
```

Redeploy is not required for secret-only CORS changes on running machines — Fly restarts VMs when secrets change.

---

## 7. Post-deploy verification

| Check | Command / action | Expected |
|---|---|---|
| API health | `curl https://scrutinize-api.fly.dev/health` | All dependency checks green |
| UI connectivity | Open `https://scrutinize-web.fly.dev` | Green **API connected** badge |
| Worker | `fly logs -a scrutinize-worker` | Celery worker ready, no import errors |
| Upload smoke | Upload a small `.txt` via UI | Job reaches `indexed`; Qdrant point count increases |
| Search smoke | Run a query after indexing | `/search` returns results |

Optional CLI checks (from a machine with repo + `.env` pointing at production URLs):

```bash
cd backend
python scripts/cloudinary_smoke.py
python scripts/check_text_ingestion.py path/to/sample.txt
```

---

## 8. Custom domains (optional)

```bash
fly certs add app.yourdomain.com -a scrutinize-web
fly certs add api.yourdomain.com -a scrutinize-api
```

After DNS validates:

1. Rebuild frontend with `VITE_API_URL=https://api.yourdomain.com`.
2. Update `CORS_ORIGINS` on `scrutinize-api` to include `https://app.yourdomain.com`.

---

## 9. Operations

### Logs

```bash
fly logs -a scrutinize-api
fly logs -a scrutinize-worker
fly logs -a scrutinize-qdrant
```

### SSH into a machine

```bash
fly ssh console -a scrutinize-api
```

### Scale

```bash
# More API capacity
fly scale count 2 -a scrutinize-api

# Heavier ingestion throughput
fly scale count worker=2 -a scrutinize-worker
fly scale vm shared-cpu-2x --memory 4096 -a scrutinize-worker
```

### Redeploy after code changes

```bash
fly deploy -c deploy/fly/api/fly.toml -a scrutinize-api
fly deploy -c deploy/fly/worker/fly.toml -a scrutinize-worker
fly deploy -c deploy/fly/web/fly.toml -a scrutinize-web
```

### Database migrations

Run locally against Neon (recommended):

```bash
make db-migrate
```

Neon is shared across local and Fly environments; one migration applies everywhere.

---

## 10. Environment variable reference (Fly)

| Variable | Apps | Source |
|---|---|---|
| `DATABASE_URL` | api, worker | Neon pooled connection string |
| `REDIS_URL` | api, worker | `fly redis create` output |
| `QDRANT_URL` | api, worker | `http://scrutinize-qdrant.internal:6333` or Qdrant Cloud |
| `OPENAI_API_KEY` | api, worker | OpenAI dashboard |
| `CLOUDINARY_*` | api, worker | [cloudinary-setup.md](cloudinary-setup.md) |
| `CORS_ORIGINS` | api | JSON array of frontend origin(s) |
| `ENVIRONMENT` | api, worker | `production` |
| `VITE_API_URL` | web (build arg) | Public API URL |

Optional tuning vars from `.env.example` (`WHISPER_MODEL`, `VIDEO_MAX_KEYFRAMES`, etc.) can be set with `fly secrets set` on the worker when needed.

---

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/health` fails on `database` | Wrong or missing `DATABASE_URL` | Use Neon **pooled** URL with `sslmode=require` |
| `/health` fails on `redis` | Bad `REDIS_URL` or Redis app deleted | Recreate Upstash Redis; update secrets on api + worker |
| `/health` fails on `qdrant` | Qdrant not on private network or wrong URL | Use `.internal` hostname; confirm `scrutinize-qdrant` is running |
| Frontend shows API disconnected | Wrong `VITE_API_URL` at build time | Rebuild frontend with correct API URL |
| Browser CORS error | `CORS_ORIGINS` missing frontend origin | `fly secrets set CORS_ORIGINS='["https://…"]' -a scrutinize-api` |
| Uploads stay `pending` | Worker down or not consuming Redis | Check `fly logs -a scrutinize-worker`; verify shared `REDIS_URL` |
| Video jobs fail with OOM | Worker too small | Scale worker to 2–4 GB RAM (`fly scale vm`) |
| Qdrant version mismatch | Image newer than client | Pin `qdrant/qdrant:v1.18.2`; wipe volume only if schema incompatible |
| `DATABASE_URL is required` on boot | Secret not set on app | `fly secrets list -a scrutinize-api` |
| FFmpeg errors in worker logs | Missing in image | Backend Dockerfile already installs `ffmpeg`; redeploy worker |

---

## 12. Cost and sizing notes

- **Minimum demo stack:** api (512 MB) + worker (2 GB) + web (256 MB) + Qdrant volume (10 GB) + Upstash Redis — monitor Fly usage dashboard.
- **Auto-stop:** `[http_service]` apps can scale to zero when idle; set `min_machines_running = 1` for demos that must stay warm.
- **Worker:** Keep at least one worker running if you rely on background indexing; it is not fronted by HTTP and will not auto-start from browser traffic alone unless you configure [Fly Machines schedules](https://fly.io/docs/apps/scale-count/) or leave `min_machines_running` equivalent via always-on scaling.

---

## Related docs

- [Cloudinary setup](cloudinary-setup.md)
- [Audio ingestion setup](audio-ingestion-setup.md)
- [Video ingestion setup](video-ingestion-setup.md)
- [Architecture](../architecture/architecture.md)
- [M0 — Infrastructure](../modules/m0-infrastructure.md)
- [README — Quick start](../../README.md)
