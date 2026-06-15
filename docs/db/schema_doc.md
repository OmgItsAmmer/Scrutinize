# Database Schema Reference — Scrutinize

Human-readable reference for the **Neon Postgres** relational schema. Vector embeddings live in **Qdrant** (see [architecture.md](../architecture/architecture.md) §7); this database holds structured metadata, job state, and segment text mirrors.

**Canonical DDL:** [schema.md](schema.md) · **SQLModel models:** `backend/app/models/`

---

## Entity relationship

```text
files (1) ──< processing_jobs (many)
files (1) ──< segments (many)
```

Each `segments.id` will equal the corresponding Qdrant point id once ingestion (M2–M4) is implemented.

---

## `files`

Uploaded source file metadata. One row per user upload.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | PK | Primary key; referenced by jobs and segments |
| `filename` | TEXT | NOT NULL | Original display name (e.g. `bbq-day.mp4`) |
| `modality` | TEXT | NOT NULL | `text`, `audio`, or `video` |
| `storage_path` | TEXT | NOT NULL | Cloudinary `secure_url` for playback/download |
| `duration_seconds` | NUMERIC | YES | Media duration; null for plain text |
| `size_bytes` | BIGINT | YES | File size in bytes |
| `status` | TEXT | NOT NULL | Lifecycle: `uploaded` → `processing` → `indexed` \| `failed` |
| `uploaded_at` | TIMESTAMPTZ | NOT NULL | Upload timestamp (UTC) |

**Status flow**

```text
uploaded → processing → indexed
                     └→ failed
```

---

## `processing_jobs`

Async pipeline stage tracking. One file may have multiple jobs (transcription, captioning, embedding, etc.).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | PK | Returned to client as `job_id` for `/status/{job_id}` polling |
| `file_id` | UUID | FK → `files.id` | Parent file (CASCADE delete) |
| `stage` | TEXT | NOT NULL | Pipeline stage name (e.g. `transcription`, `embedding`) |
| `status` | TEXT | NOT NULL | `pending` → `running` → `done` \| `failed` |
| `error_message` | TEXT | YES | Populated when `status = failed` |
| `created_at` | TIMESTAMPTZ | NOT NULL | Job creation time |
| `updated_at` | TIMESTAMPTZ | NOT NULL | Last status change |

**Index:** `(file_id, status)` — efficient lookup of active/failed jobs per file.

---

## `segments`

Indexed content chunks mirrored from Qdrant payload for SQL queries, joins, and `/library` segment counts.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | PK | Same UUID as Qdrant point id |
| `file_id` | UUID | FK → `files.id` | Parent file |
| `modality` | TEXT | NOT NULL | `text`, `audio`, or `video` |
| `content` | TEXT | NOT NULL | Chunk text, transcript snippet, or merged caption |
| `start_time` | NUMERIC | YES | Start offset in seconds (null for plain text) |
| `end_time` | NUMERIC | YES | End offset in seconds (null for plain text) |
| `created_at` | TIMESTAMPTZ | NOT NULL | Row creation time |

**Index:** `(file_id)` — list all segments for a file.

---

## Production notes

- **Hosted DB:** [Neon](https://neon.tech) serverless Postgres — connection via `DATABASE_URL` (use pooled endpoint).
- **Schema bootstrap:** `make db-migrate` or SQLModel `create_all()` on backend startup.
- **Object storage:** Cloudinary for raw uploads (`CLOUDINARY_*`). Setup: [runbooks/cloudinary-setup.md](../runbooks/cloudinary-setup.md)
- **Migrations:** `backend/migrations/001_initial.sql`; future changes add numbered migration files.
