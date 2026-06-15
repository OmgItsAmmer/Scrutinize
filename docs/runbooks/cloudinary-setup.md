# Runbook — Cloudinary Setup

Configure Cloudinary as the object store for Scrutinize raw uploads (text, audio, video). The backend uploads server-side via the Cloudinary SDK; the frontend never receives API secrets.

**Used by:** M2–M4 ingestion (`/upload`), Qdrant payload `source_path`, media playback in M7.

---

## Prerequisites

- Cloudinary account ([cloudinary.com](https://cloudinary.com))
- Scrutinize repo cloned with `.env` created from `.env.example`
- Backend dependencies installed: `make install-backend`

---

## 1. Create or open a Cloudinary account

1. Sign up at [cloudinary.com/users/register_free](https://cloudinary.com/users/register_free).
2. Open the **Dashboard** for your cloud.

You need three values from the dashboard **Product environment credentials** panel:

| Credential | Env variable |
|---|---|
| Cloud name | `CLOUDINARY_CLOUD_NAME` |
| API Key | `CLOUDINARY_API_KEY` |
| API Secret | `CLOUDINARY_API_SECRET` |

Copy these into your repo-root `.env`:

```env
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=123456789012345
CLOUDINARY_API_SECRET=your_api_secret
CLOUDINARY_FOLDER=scrutinize
```

`CLOUDINARY_FOLDER` is optional (default `scrutinize`). Uploads land under `{folder}/{modality}/` e.g. `scrutinize/video/…`.

---

## 2. Enable required resource types

Scrutinize stores three modalities:

| Modality | Typical formats | Cloudinary `resource_type` |
|---|---|---|
| Text | `.txt`, `.md` | `raw` |
| Audio | `.mp3`, `.wav`, `.m4a` | `video` (Cloudinary treats audio as video resources) |
| Video | `.mp4`, `.mov` | `video` |

On the free tier, **video** and **raw** delivery are supported within plan limits. No extra dashboard toggle is required for basic uploads.

If uploads fail with a plan error, check **Settings → Upload → Upload presets** and your account usage limits.

---

## 3. Recommended dashboard settings

### Upload presets (optional)

Scrutinize uses **signed server-side uploads** (`backend/app/services/cloudinary_storage.py`). You do **not** need an unsigned upload preset for the API.

Optional: create a folder-only preset named `scrutinize` if you want dashboard-level defaults — not required for Phase 0/1.

### Security

1. **Settings → Security** — keep **Strict Transformations** enabled in production.
2. Never commit `CLOUDINARY_API_SECRET` to git (`.env` is gitignored).
3. Restrict API key IP allowlisting only if you have static egress IPs (optional; skip for local dev).

### Folder layout

Assets are organized as:

```text
scrutinize/
├── text/
├── audio/
└── video/
```

The `files.storage_path` column in Neon stores the Cloudinary **`secure_url`** (HTTPS playback/download link).

---

## 4. Verify configuration locally

### A. Environment loaded

From repo root:

```bash
docker compose config | findstr CLOUDINARY
```

Or inside Python:

```bash
cd backend
python -c "from app.core.config import get_settings; s=get_settings(); print(s.cloudinary_configured, s.cloudinary_cloud_name)"
```

Expected: `True` and your cloud name.

### B. Smoke upload (manual)

```bash
cd backend
python scripts/cloudinary_smoke.py
```

1. Confirm the script prints a `secure_url`.
2. Open the URL in a browser — you should see the text content.
3. In Cloudinary **Media Library**, find the asset under `scrutinize/text/`.

Delete the test asset from the Media Library when done.

---

## 5. Docker Compose

Backend and worker load Cloudinary credentials from `.env` via `env_file`:

```bash
docker compose up --build
```

No Cloudinary container runs locally — it is a hosted API.

---

## 6. CI / GitHub Actions

Add repository secrets for integration/system jobs that upload files (Phase 1+):

| Secret | Value |
|---|---|
| `CLOUDINARY_CLOUD_NAME` | Dashboard cloud name |
| `CLOUDINARY_API_KEY` | API key |
| `CLOUDINARY_API_SECRET` | API secret |

Workflow env mapping: `.github/workflows/ci.yml` passes these to test jobs alongside `DATABASE_URL` and `OPENAI_API_KEY`.

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Cloudinary is not configured` on startup | Missing env vars | Set all three `CLOUDINARY_*` credentials in `.env` |
| `Invalid Signature` | Wrong API secret or clock skew | Re-copy secret from dashboard; sync system time |
| Video upload fails, text works | Plan limit or file too large | Use shorter demo files; check Cloudinary usage |
| `secure_url` 404 in browser | Asset deleted or wrong `public_id` | Re-upload; verify Media Library path |
| Docker backend missing creds | `.env` not at repo root | Ensure `.env` sits beside `docker-compose.yml` |

---

## 8. Code reference

| File | Purpose |
|---|---|
| `backend/app/core/config.py` | `CLOUDINARY_*` settings |
| `backend/app/services/cloudinary_storage.py` | Upload/delete wrapper |
| `backend/app/core/deps.py` | `get_cloudinary_storage()` dependency |
| `backend/scripts/cloudinary_smoke.py` | Verify Cloudinary credentials |

---

## Related docs

- [Architecture — data layer](../architecture/architecture.md)
- [Project plan — Phase 1 ingestion](../plan.md)
- [M1 — Backend core](../modules/m1-backend-core.md)
- [M0 — Infrastructure](../modules/m0-infrastructure.md)
