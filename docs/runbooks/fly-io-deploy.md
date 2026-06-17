# Runbook — Deploy Scrutinize on [Fly.io](http://Fly.io)

Deploy the Scrutinize backend stack to [Fly.io](https://fly.io): FastAPI API, Celery worker, Redis, and Qdrant. The React frontend deploys to [Vercel](https://vercel.com) (free tier). Neon, Cloudinary, and OpenAI stay as external managed services (same as local Docker Compose).

**Used by:** M0 production hosting, demo deployments, CI smoke targets against a live URL.

This runbook defaults to the **budget profile** — the lowest-cost setup suitable for personal use, prototypes, and low-traffic demos. An **always-on profile** is documented where configs differ (§12).

---

## Deployment profiles


|                      | **Budget (default)**                                       | **Always-on**                                   |
| -------------------- | ---------------------------------------------------------- | ----------------------------------------------- |
| **Typical Fly bill** | ~$3–8/mo idle; bursts when you use the app                 | ~$23–33/mo                                      |
| **Frontend**         | [Vercel](https://vercel.com) free tier                     | Vercel (same)                                   |
| **Qdrant**           | [Qdrant Cloud](https://cloud.qdrant.io/) free tier (HTTPS) | Self-hosted `scrutinize-qdrant` on Fly + volume |
| **Redis**            | Self-hosted on Fly (auto-stop)                             | Self-hosted on Fly (always-on)                  |
| **API**              | Scale to zero (`min_machines_running = 0`)                 | Always warm (`min_machines_running = 1`)        |
| **Worker**           | Scale **0 ↔ 1** manually around ingestion                  | Always running (`worker=1`)                     |
| **API VM**           | 256 MB shared-cpu-1x                                       | 512 MB shared-cpu-1x                            |
| **Worker VM**        | 1 GB for text; 2 GB only for video                         | 2 GB shared-cpu-2x                              |
| **Best for**         | Personal projects, occasional uploads                      | Demos that must stay warm, heavier ingestion    |


External costs (Neon, Cloudinary, OpenAI, Vercel) are usage-based or free-tier where noted. Use [Neon free tier](https://neon.tech) and Vercel Hobby where possible.

### Budget quick checklist

1. Neon schema applied (`make db-migrate`) — free tier OK.
2. Qdrant Cloud free cluster → HTTPS `QDRANT_URL` (skip §3b).
3. Provision self-hosted Redis on Fly with auto-stop (§2).
4. Deploy API on Fly with `min_machines_running = 0` (§4).
5. Deploy frontend on Vercel with `VITE_API_URL` pointing at the Fly API (§6).
6. Set `CORS_ORIGINS` on the API to your Vercel URL (§4c, §6c).
7. Deploy worker, then **`fly scale count worker=0 -a scrutinize-worker --yes`** until you need ingestion (§5).
8. Before uploads: `fly scale count worker=1 -a scrutinize-worker --yes`.

---

## Architecture

### Budget profile

```text
  Vercel (frontend)                    Fly.io (backend)
  ┌─────────────────┐                  ┌─────────────────────────────────────────┐
  │ React static    │──── HTTPS ──────►│ scrutinize-api (FastAPI, auto-stop)     │
  │ VITE_API_URL    │                  │ scrutinize-worker (Celery, scale 0↔1)   │
  └─────────────────┘                  │ scrutinize-redis (Fly Machine, auto-stop)│
                                       └─────────────────────────────────────────┘
                                                        ▲
                    ┌───────────────────────────────────┴───────────────────────┐
                    │  External: Neon · Cloudinary · OpenAI · Qdrant Cloud     │
                    └─────────────────────────────────────────────────────────┘
```

### Always-on profile (adds self-hosted Qdrant on Fly)

```text
  Vercel (frontend)                    Fly.io (backend)
  ┌─────────────────┐                  ┌─────────────────────────────────────────┐
  │ React static    │──── HTTPS ──────►│ scrutinize-api                          │
  └─────────────────┘                  │ scrutinize-worker                       │
                                       │ scrutinize-redis · scrutinize-qdrant    │
                                       └─────────────────────────────────────────┘
                                                        ▲
                    ┌───────────────────────────────────┴───────────────────────┐
                    │  External: Neon · Cloudinary · OpenAI                    │
                    └─────────────────────────────────────────────────────────┘
```


| Component           | Platform       | Role                           | Budget                      |
| ------------------- | -------------- | ------------------------------ | --------------------------- |
| Frontend            | **Vercel**     | Static React UI (Vite build)   | Hobby / free tier           |
| `scrutinize-api`    | Fly            | Public HTTPS API (`:8000`)     | auto-stop, 256 MB           |
| `scrutinize-worker` | Fly            | Background ingestion           | scale 0↔1                   |
| `scrutinize-redis`  | Fly            | Celery broker + result backend | auto-stop, 256 MB           |
| `scrutinize-qdrant` | Fly (optional) | Vector store                   | **skip** — use Qdrant Cloud |


Keep Qdrant at **v1.18.x** when self-hosting — it must stay compatible with `qdrant-client` in `backend/pyproject.toml`. Qdrant Cloud manages version compatibility for managed clusters.

### How the worker is used (not connected to Vercel)

The browser **only** talks to the Fly API (`VITE_API_URL` on Vercel). The worker has **no public URL** and is **never** configured on Vercel.

```text
Upload flow:

  Vercel UI  ──POST /upload──►  scrutinize-api
                                    │
                                    ├─► Cloudinary (store file)
                                    ├─► Neon (create file + job rows)
                                    └─► Redis (enqueue Celery task via task.delay)

  scrutinize-worker  ◄──poll Redis──  picks up task
        │
        ├─► Cloudinary (download file)
        ├─► OpenAI (transcribe / embed / caption)
        ├─► Qdrant (store vectors)
        └─► Neon (update job status → indexed | failed)

  Vercel UI  ──GET /jobs/{id}──►  scrutinize-api  (poll every 2s until done)
  Vercel UI  ──POST /search──►   scrutinize-api  (search uses Qdrant; no worker needed)
```

| User action | Frontend calls | Worker involved? |
|---|---|---|
| Health / library / search | API only | No |
| Upload file | `POST /upload` → API enqueues to Redis | **Yes** — must be running (`worker=1`) |
| Watch upload progress | `GET /jobs/{id}` → API reads Neon | No (worker already updated Neon) |

If the worker is scaled to **0**, uploads succeed but jobs stay **pending** until you start it (§5d). Search works without the worker as long as content was already indexed.

---

## Prerequisites

- [Fly.io account](https://fly.io/app/sign-up) with billing enabled (pay-as-you-go; no permanent free tier for new orgs)
- [Vercel account](https://vercel.com/signup) (Hobby tier is sufficient)
- `[flyctl` installed]([https://fly.io/docs/hands-on/install-flyctl/](https://fly.io/docs/hands-on/install-flyctl/)) and logged in (`fly auth login`)
- Scrutinize repo cloned locally
- External services already configured:
  - [Neon](https://neon.tech) — pooled `DATABASE_URL` (free tier OK for budget; see [README](../../README.md#quick-start))
  - [Qdrant Cloud](https://cloud.qdrant.io/) — free cluster for budget profile (§3a)
  - [Cloudinary](cloudinary-setup.md) — `CLOUDINARY_`*
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

## 2. Provision Redis (Self-hosted on Fly)

Running Redis as a Fly Machine allows it to **auto-stop** when the API is idle, keeping costs nearly zero (~$0.15/mo for rootfs storage).

### 2a. Create the app and allocate private IP

Fly Proxy needs a **Flycast** (private IPv6) address to handle internal auto-start/auto-stop.

```bash
fly apps create scrutinize-redis
fly ips allocate-v6 --private -a scrutinize-redis
```

### 2b. Add `deploy/fly/redis/fly.toml`

Create `deploy/fly/redis/fly.toml`:

```toml
app = "scrutinize-redis"
primary_region = "ord"

[build]
  image = "redis:alpine"

[env]
  # Optional: set a password if you want more than network-level security
  # REDIS_PASSWORD = "..."

[[services]]
  internal_port = 6379
  protocol = "tcp"
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 0

  [[services.ports]]
    port = 6379

[[vm]]
  memory = "256mb"
  cpu_kind = "shared"
  cpus = 1
```

### 2c. Deploy

```bash
fly deploy -c deploy/fly/redis/fly.toml -a scrutinize-redis
```

Internal connection string for API and worker:

```text
redis://scrutinize-redis.flycast:6379
```

*Note: If you set a password, use `redis://:PASSWORD@scrutinize-redis.flycast:6379`.*

---

## 3. Provision Qdrant

### 3a. Budget — Qdrant Cloud free tier (recommended)

Skip running Qdrant on Fly entirely. This removes an always-on VM and persistent volume (~$8–10/mo saved).

1. Sign up at [Qdrant Cloud](https://cloud.qdrant.io/) (no credit card for free tier).
2. Create a **Free** cluster (0.5 vCPU, 1 GB RAM, 4 GB disk — enough for demos and ~1M vectors at 768 dims).
3. Copy the cluster **HTTPS URL** and API key if required by your client config.

Set on API and worker secrets:

```text
QDRANT_URL="https://YOUR-CLUSTER-ID.region.aws.cloud.qdrant.io"
```

Notes:

- Free clusters **suspend after ~1 week of inactivity**; wake the cluster in the Qdrant Cloud console before deploy or health checks.
- If you outgrow free tier, upgrade in Qdrant Cloud or switch to §3b.

### 3b. Always-on — self-hosted on Fly (optional)

Use this when you need private-network Qdrant, larger storage, or no external vector dependency.

```bash
fly apps create scrutinize-qdrant
fly volumes create qdrant_data --size 10 --region ord -a scrutinize-qdrant
```

Use the same **region** (`ord`, `iad`, etc.) for all Scrutinize apps to keep private networking latency low. Smallest practical volume is 1 GB (~$0.15/mo); 10 GB is the runbook default for growth.

#### Add `fly.toml` for Qdrant

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

---

## 4. Deploy the backend API

### 4a. Create the app

```bash
fly apps create scrutinize-api
```

### 4b. Add `deploy/fly/api/fly.toml`

Budget defaults below. For always-on, set `min_machines_running = 1` and `memory = "512mb"`.

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
  min_machines_running = 0   # budget: scale to zero; use 1 for always-on

  [http_service.concurrency]
    type = "requests"
    hard_limit = 50
    soft_limit = 40

[[vm]]
  memory = "256mb"           # budget; use "512mb" for always-on
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
  REDIS_URL="redis://scrutinize-redis.flycast:6379" \
  QDRANT_URL="https://YOUR-CLUSTER-ID.region.aws.cloud.qdrant.io" \
  OPENAI_API_KEY="sk-..." \
  CLOUDINARY_CLOUD_NAME="your_cloud" \
  CLOUDINARY_API_KEY="..." \
  CLOUDINARY_API_SECRET="..." \
  CLOUDINARY_FOLDER="scrutinize" \
  CORS_ORIGINS='["https://YOUR-PROJECT.vercel.app"]'
```

For self-hosted Qdrant (§3b), use `QDRANT_URL="http://scrutinize-qdrant.internal:6333"` instead.

Notes:

- **`CORS_ORIGINS`** — JSON array or comma-separated list. PowerShell examples:
  ```powershell
  # JSON array (preferred)
  fly secrets set -a scrutinize-api CORS_ORIGINS='["https://your-app.vercel.app"]'

  # Comma-separated (also works)
  fly secrets set -a scrutinize-api CORS_ORIGINS="https://your-app.vercel.app"
  ```
  Use your **Vercel** URL, not `scrutinize-api.fly.dev`. After changing secrets, redeploy the API.
- Set `CORS_ORIGINS` after the first Vercel deploy when you know the hostname (§6c).
- Never commit secrets to git.

### 4d. Deploy

Run from the `**backend**` directory (Fly uses the current directory as build context; running from repo root sends an empty context and the build fails):

```bash
cd backend
fly deploy --config ../deploy/fly/api/fly.toml --ha=false
```

Or from repo root in one line:

```powershell
# PowerShell
cd backend; fly deploy --config ../deploy/fly/api/fly.toml --ha=false; cd ..
```

```bash
# bash
cd backend && fly deploy --config ../deploy/fly/api/fly.toml --ha=false
```

Verify:

```bash
fly open /health -a scrutinize-api
curl -s https://scrutinize-api.fly.dev/health | jq .
```

Expect `"status": "ok"` (or equivalent) with database, Redis, and Qdrant checks passing.

---

## 5. Deploy the Celery worker

Video ingestion runs FFmpeg inside the worker container (same image as the API). The worker is the **largest Fly cost** when always on (~$13/mo at 2 GB). Budget profile keeps it **scaled to zero** until you ingest.

### 5a. Create the app

```bash
fly apps create scrutinize-worker
```

### 5b. Add `deploy/fly/worker/fly.toml`

**Budget (text-only ingestion):** 1 GB / 1 shared CPU. **Video or always-on:** use 2 GB / 2 CPUs.

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
  memory = "1gb"             # budget text-only; use "2gb" for video / always-on
  cpu_kind = "shared"
  cpus = 1                   # use 2 with 2gb for video

# Worker has no public HTTP service — omit [http_service]
# It will NOT auto-start from browser traffic; scale manually (§5d).
```

### 5c. Set secrets (same connectivity as API)

```bash
fly secrets set -a scrutinize-worker \
  DATABASE_URL="postgresql+psycopg://..." \
  REDIS_URL="redis://scrutinize-redis.flycast:6379" \
  QDRANT_URL="https://YOUR-CLUSTER-ID.region.aws.cloud.qdrant.io" \
  OPENAI_API_KEY="sk-..." \
  CLOUDINARY_CLOUD_NAME="..." \
  CLOUDINARY_API_KEY="..." \
  CLOUDINARY_API_SECRET="..." \
  CLOUDINARY_FOLDER="scrutinize"
```

### 5d. Deploy and scale

From `**backend**`:

```bash
cd backend
fly deploy --config ../deploy/fly/worker/fly.toml --ha=false
```

**Budget — start stopped (no compute cost):**

```bash
fly scale count worker=0 -a scrutinize-worker --yes
```

**Before uploads / indexing, start the worker:**

```bash
fly scale count worker=1 -a scrutinize-worker --yes
fly logs -a scrutinize-worker
```

**When finished, stop again to save cost:**

```bash
fly scale count worker=0 -a scrutinize-worker --yes
```

**Always-on — keep one worker running:**

```bash
fly scale count worker=1 -a scrutinize-worker --yes
fly logs -a scrutinize-worker
```

Look for `celery@... ready.` in logs. Increase `worker` count if upload queues back up.

---

## 6. Deploy the frontend (Vercel)

The frontend is a Vite + React SPA in `frontend/`. Vercel serves the static `dist/` output on its CDN — no Fly app or Docker image needed. This removes ~$2/mo from the Fly bill and avoids frontend cold starts.

Deploy the **API first** (§4) so you have a stable `VITE_API_URL`.

### 6a. Connect the repo (dashboard)

1. [New Project](https://vercel.com/new) → import the Scrutinize Git repository.
2. **Root Directory:** `frontend` (monorepo — do not use repo root).
3. **Framework Preset:** Vite (auto-detected).
4. **Build Command:** `npm run build` (default).
5. **Output Directory:** `dist` (default for Vite).

### 6b. Environment variables

Add in Vercel **Project → Settings → Environment Variables**:


| Name           | Value                            | Environments                     |
| -------------- | -------------------------------- | -------------------------------- |
| `VITE_API_URL` | `https://scrutinize-api.fly.dev` | Production, Preview, Development |


`VITE_API_URL` is **baked in at build time**. Redeploy after changing it or when the API hostname changes.

### 6c. Deploy and update API CORS

Deploy from the dashboard (or CLI below). Note the production URL, e.g. `https://scrutinize.vercel.app`.

**Landing page wake:** On first load the SPA calls `GET /health` against `VITE_API_URL`. That wakes the Fly API and Redis (auto-start). The worker still requires `fly scale count worker=1` before uploads (§9).

Update API CORS to allow that origin:

```bash
fly secrets set -a scrutinize-api \
  CORS_ORIGINS='["https://scrutinize.vercel.app"]'
```

Fly restarts API machines when secrets change — no redeploy required.

To allow **preview deployments** (PR branches), include each origin in the JSON array or add preview URLs as you use them.

### 6d. CLI alternative

From repo root:

```bash
cd frontend
npx vercel login
npx vercel link          # link to a Vercel project
npx vercel env add VITE_API_URL production   # paste https://scrutinize-api.fly.dev
npx vercel --prod
```

### 6e. Custom domain (optional)

In Vercel **Project → Settings → Domains**, add e.g. `app.yourdomain.com`. Then add that origin to `CORS_ORIGINS` on the API:

```bash
fly secrets set -a scrutinize-api \
  CORS_ORIGINS='["https://app.yourdomain.com","https://scrutinize.vercel.app"]'
```

Redeploy the frontend on Vercel if you change `VITE_API_URL` to a custom API domain.

---

## 7. Post-deploy verification


| Check           | Command / action                                                | Expected                                                           |
| --------------- | --------------------------------------------------------------- | ------------------------------------------------------------------ |
| API health      | `curl https://scrutinize-api.fly.dev/health`                    | All dependency checks green (first request may cold-start ~5–15 s) |
| UI connectivity | Open your Vercel URL                                            | Green **API connected** badge                                      |
| Worker          | `fly scale count worker=1` then `fly logs -a scrutinize-worker` | Celery worker ready, no import errors                              |
| Upload smoke    | Start worker (§5d), upload a small `.txt` via UI                | Job reaches `indexed`; Qdrant point count increases                |
| Search smoke    | Run a query after indexing                                      | `/search` returns results                                          |


Optional CLI checks (from a machine with repo + `.env` pointing at production URLs):

```bash
cd backend
python scripts/cloudinary_smoke.py
python scripts/check_text_ingestion.py path/to/sample.txt
```

---

## 8. Custom domains (optional)

**API (Fly):**

```bash
fly certs add api.yourdomain.com -a scrutinize-api
```

**Frontend (Vercel):** add `app.yourdomain.com` in Vercel **Settings → Domains**.

After DNS validates:

1. Set `VITE_API_URL=https://api.yourdomain.com` in Vercel and redeploy the frontend.
2. Update `CORS_ORIGINS` on `scrutinize-api`:
  ```bash
   fly secrets set -a scrutinize-api \
     CORS_ORIGINS='["https://app.yourdomain.com"]'
  ```

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

### Sleep all services (zero compute cost)

Stops all Fly compute. You pay only rootfs storage (~$0.15/GB/mo per machine image).

```bash
# Worker — only app that must be scaled manually (no HTTP front door)
fly scale count worker=0 -a scrutinize-worker --yes

# API — auto-stops on idle; force-stop now if you want zero immediately
fly machine list -q -a scrutinize-api | ForEach-Object { fly machine stop $_ -a scrutinize-api }

# Redis — auto-stops on idle; force-stop now
fly machine list -q -a scrutinize-redis | ForEach-Object { fly machine stop $_ -a scrutinize-redis }

# Optional: self-hosted Qdrant (always-on profile only)
fly machine list -q -a scrutinize-qdrant | ForEach-Object { fly machine stop $_ -a scrutinize-qdrant }
```

**PowerShell one-liner (all Scrutinize apps):**

```powershell
fly scale count worker=0 -a scrutinize-worker --yes; fly machine list -q -a scrutinize-api | ForEach-Object { fly machine stop $_ -a scrutinize-api }; fly machine list -q -a scrutinize-redis | ForEach-Object { fly machine stop $_ -a scrutinize-redis }
```

**Why machines stay running:** If the API `fly.toml` includes a `[checks]` block hitting `/health` every 15 s, Fly keeps the API awake and each check pings Redis (waking Redis too). Budget config omits `[checks]` — redeploy the API after changing `deploy/fly/api/fly.toml`. A browser tab left open also polls `/health` every 2 min and can delay auto-stop until the tab is closed.

Verify everything is stopped:

```bash
fly status -a scrutinize-api
fly status -a scrutinize-worker
fly status -a scrutinize-redis
```

Expect **worker** with no machines; **api** and **redis** machines in `stopped` state.

### Wake all services (on request)

The Vercel frontend calls `GET /health` as soon as the app loads. That HTTPS request **auto-starts the API** (`min_machines_running = 0` + `auto_start_machines = true`). The health check connects to Redis over `.flycast`, which **auto-starts Redis** too.

First request after sleep may take **5–15 s** (cold start). The UI retries automatically.

```bash
# Same as opening the landing page — wakes API + Redis
curl -s https://scrutinize-api.fly.dev/health | jq .

# Worker does NOT auto-start from browser traffic — scale up before uploads
fly scale count worker=1 -a scrutinize-worker --yes
fly logs -a scrutinize-worker   # wait for "celery@... ready."
```

**Typical demo flow:**

1. Open your Vercel URL → API + Redis wake from `/health`.
2. Before uploading: `fly scale count worker=1 -a scrutinize-worker --yes`.
3. When done indexing: `fly scale count worker=0 -a scrutinize-worker --yes` to save cost.

PowerShell one-liner to wake API + Redis + worker:

```powershell
curl -s https://scrutinize-api.fly.dev/health; fly scale count worker=1 -a scrutinize-worker --yes
```

### Scale (capacity tuning)

```bash
# Budget: start worker only when ingesting
fly scale count worker=1 -a scrutinize-worker --yes
fly scale count worker=0 -a scrutinize-worker --yes

# More API capacity
fly scale count 2 -a scrutinize-api --yes

# Heavier ingestion throughput (always-on profile)
fly scale count worker=2 -a scrutinize-worker --yes
fly scale vm shared-cpu-2x --memory 4096 -a scrutinize-worker
```

### Avoid surprise charges

- Do **not** allocate a **dedicated IPv4** ($2/mo) unless required — shared IPv4 is fine.
- Use **one region** for all Fly apps.
- Delete unused apps and volumes (`fly apps destroy`, `fly volumes list`).
- Monitor usage: [Fly usage dashboard](https://fly.io/dashboard/personal/usage).

### Redeploy after code changes

```bash
# Backend (Fly) — run from backend/
cd backend
fly deploy --config ../deploy/fly/api/fly.toml
fly deploy --config ../deploy/fly/worker/fly.toml

# Frontend (Vercel) — push to Git or:
cd frontend && npx vercel --prod
```

### Database migrations

Run locally against Neon (recommended):

```bash
make db-migrate
```

Neon is shared across local and Fly environments; one migration applies everywhere.

---

## 10. Environment variable reference

### Fly (api, worker)


| Variable         | Apps        | Source                                                                            |
| ---------------- | ----------- | --------------------------------------------------------------------------------- |
| `DATABASE_URL`   | api, worker | Neon pooled connection string (free tier OK)                                      |
| `REDIS_URL`      | api, worker | `redis://scrutinize-redis.flycast:6379` (§2c)                                     |
| `QDRANT_URL`     | api, worker | Qdrant Cloud HTTPS URL (budget) or `http://scrutinize-qdrant.internal:6333` (§3b) |
| `OPENAI_API_KEY` | api, worker | OpenAI dashboard                                                                  |
| `CLOUDINARY_*`   | api, worker | [cloudinary-setup.md](cloudinary-setup.md)                                        |
| `CORS_ORIGINS`   | api         | JSON array of Vercel (and custom) frontend origin(s)                              |
| `ENVIRONMENT`    | api, worker | `production`                                                                      |


### Vercel (frontend)


| Variable       | Source                                                    |
| -------------- | --------------------------------------------------------- |
| `VITE_API_URL` | Public Fly API URL, e.g. `https://scrutinize-api.fly.dev` |


Optional tuning vars from `.env.example` (`WHISPER_MODEL`, `VIDEO_MAX_KEYFRAMES`, etc.) can be set with `fly secrets set` on the worker when needed.

---

## 11. Troubleshooting


| Symptom                            | Likely cause                                       | Fix                                                                                                                                            |
| ---------------------------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| App exits code 1 / `SettingsError` parsing `cors_origins` | Bad `CORS_ORIGINS` quoting on Fly | `fly secrets set -a scrutinize-api CORS_ORIGINS='["https://your-app.vercel.app"]'` then redeploy API |
| Machines restarting / rate limit   | Crash loop + auto-start storm                      | Fix startup error; wait ~10 min for rate limit; avoid hammering `/health` until stable |
| First API call slow (~5–15 s)      | Budget API auto-stop cold start                    | Expected; retry or set `min_machines_running = 1` on api                                                                                       |
| `/health` fails on `database`      | Wrong or missing `DATABASE_URL`                    | Use Neon **pooled** URL with `sslmode=require`                                                                                                 |
| `/health` fails on `redis`         | Redis Machine stopped or bad URL                   | Ensure `REDIS_URL` uses `.flycast`. Fly Proxy should start it automatically on connection. Check `fly status -a scrutinize-redis`.             |
| `/health` fails on `qdrant`        | Qdrant Cloud suspended or wrong URL                | Wake cluster in Qdrant Cloud console; verify HTTPS `QDRANT_URL`. Self-hosted: use `.internal` hostname; confirm `scrutinize-qdrant` is running |
| Frontend shows API disconnected    | Wrong `VITE_API_URL` on Vercel                     | Set env var in Vercel and **redeploy** (build-time variable)                                                                                   |
| Browser CORS error                 | `CORS_ORIGINS` missing Vercel origin               | Add exact origin (no trailing slash): `fly secrets set CORS_ORIGINS='["https://….vercel.app"]' -a scrutinize-api`                              |
| CORS on preview deploys            | Preview URL not in `CORS_ORIGINS`                  | Add preview hostname to JSON array or test on production URL only                                                                              |
| Uploads stay `pending`             | Worker scaled to 0 (budget) or not consuming Redis | `fly scale count worker=1 -a scrutinize-worker`; check logs; verify shared `REDIS_URL`                                                         |
| Video jobs fail with OOM           | Worker too small                                   | Scale worker VM to 2–4 GB RAM (`fly scale vm shared-cpu-2x --memory 2048`)                                                                     |
| Qdrant version mismatch            | Image newer than client (self-hosted)              | Pin `qdrant/qdrant:v1.18.2`; wipe volume only if schema incompatible                                                                           |
| `DATABASE_URL is required` on boot | Secret not set on app                              | `fly secrets list -a scrutinize-api`                                                                                                           |
| FFmpeg errors in worker logs       | Missing in image                                   | Backend Dockerfile already installs `ffmpeg`; redeploy worker                                                                                  |


---

## 12. Cost and sizing notes

Fly bills pay-as-you-go per organization. Stopped machines incur **rootfs storage** (~$0.15/GB/mo) but no compute. See [Fly pricing](https://fly.io/docs/about/pricing/).

### Budget profile (~$3–8/mo on Fly + $0 Vercel)


| Component | Platform     | Config                             | Approx. cost               |
| --------- | ------------ | ---------------------------------- | -------------------------- |
| Frontend  | Vercel       | Hobby / CDN                        | $0                         |
| API       | Fly          | 256 MB, scale to zero              | ~$0–2/mo                   |
| Worker    | Fly          | 1 GB, scaled to 0 most of the time | ~$0–4/mo                   |
| Redis     | Fly          | 256 MB, scale to zero              | ~$0.15/mo (rootfs storage) |
| Qdrant    | Qdrant Cloud | free                               | $0                         |
| Postgres  | Neon         | free tier                          | $0                         |


**Typical usage pattern:** Vercel serves UI instantly; API cold-starts on first request; API triggers Redis cold-start via Flycast; scale worker to 1 before uploads, back to 0 when done.

### Always-on profile (~$23–33/mo on Fly + $0 Vercel)


| Component | Platform | Config                             | Approx. cost |
| --------- | -------- | ---------------------------------- | ------------ |
| Frontend  | Vercel   | Hobby                              | $0           |
| API       | Fly      | 512 MB, `min_machines_running = 1` | ~$3/mo       |
| Worker    | Fly      | 2 GB shared-cpu-2x, always on      | ~$13/mo      |
| Qdrant    | Fly      | VM + 10 GB volume                  | ~$8–10/mo    |
| Redis     | Fly      | 256 MB, always on                  | ~$2/mo       |


### Cost levers (biggest savings first)

1. **Frontend on Vercel** instead of Fly — saves ~$2/mo and removes UI cold starts.
2. **Qdrant Cloud free** instead of self-hosted Fly Qdrant — saves VM + volume.
3. **Worker scale 0↔1** — saves ~$13/mo vs always-on 2 GB worker.
4. `**min_machines_running = 0`** on API — saves ~$2/mo vs always warm.
5. **Redis auto-stop** — saves ~$2/mo vs always-on Redis.
6. **Smallest VMs** — 256 MB API/Redis, 1 GB worker for text-only.
7. **Single region** (`ord`) — no cross-region egress.
8. **No dedicated IPv4** — avoid $2/mo per address.

### Auto-stop behavior

- The **API** scales to zero when idle if `auto_stop_machines = "stop"` and `min_machines_running = 0`. First request after idle triggers auto-start (~5–15 s cold start).
- **Redis** also scales to zero and is triggered by the API connecting to its `.flycast` address.
- The **frontend on Vercel** is always served from the CDN — no cold start for static assets.
- **Worker** has no HTTP front door — it does **not** auto-start from browser traffic. Use manual scale (§5d) or [Fly Machines schedules](https://fly.io/docs/apps/scale-count/) for always-on indexing without 24/7 cost.

### When to upgrade from budget

- API must stay warm → `min_machines_running = 1` on api.
- Continuous background indexing → keep `worker=1`.
- Video ingestion → worker 2 GB / 2 CPUs minimum.
- Large vector libraries → Qdrant Cloud paid tier or self-hosted §3b.

---

## Related docs

- [Cloudinary setup](cloudinary-setup.md)
- [Audio ingestion setup](audio-ingestion-setup.md)
- [Video ingestion setup](video-ingestion-setup.md)
- [Architecture](../architecture/architecture.md)
- [M0 — Infrastructure](../modules/m0-infrastructure.md)
- [README — Quick start](../../README.md)

