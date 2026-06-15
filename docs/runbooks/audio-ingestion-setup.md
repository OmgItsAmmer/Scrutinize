# Runbook — Audio Ingestion (M3)

Manual setup and verification for the audio ingestion pipeline: Whisper transcription → 15–30s windows → embeddings → Qdrant + Neon.

**Used by:** `POST /upload` (`.mp3`, `.wav`, `.m4a`), Celery `process_audio`, `backend/scripts/check_audio_ingestion.py`.

---

## Prerequisites

- Scrutinize stack running (`docker compose up`) or local backend + worker + Redis + Qdrant
- Neon schema applied (`make db-migrate`) — no extra migration required; `segments.start_time` / `end_time` already exist
- `.env` configured:
  - `DATABASE_URL` (Neon)
  - `OPENAI_API_KEY` (Whisper)
  - `CLOUDINARY_*` (raw audio storage)
  - `QDRANT_URL`, `REDIS_URL`

---

## Database schema

Audio segments use the existing `segments` table:

| Column | Audio usage |
|---|---|
| `content` | Transcript text for the window |
| `start_time` | Window start (seconds) |
| `end_time` | Window end (seconds) |
| `modality` | `audio` |

`files.duration_seconds` is populated via `ffprobe` after download.

See [schema.md](../db/schema.md) — **no migration needed for M3**.

---

## Supported formats

| Extension | Notes |
|---|---|
| `.mp3` | Primary demo format |
| `.wav` | Uncompressed |
| `.m4a` | AAC in MP4 container |

Cloudinary upload uses `resource_type=video` (Cloudinary treats audio as video resources).

---

## Configuration (optional)

```env
WHISPER_MODEL=whisper-1
AUDIO_SEGMENT_MIN_SECONDS=15
AUDIO_SEGMENT_MAX_SECONDS=30
MAX_UPLOAD_BYTES=10485760
```

---

## Manual checks

### 1. Cloudinary credentials

```bash
make cloudinary-smoke
```

### 2. Full audio pipeline (local file)

Uploads to Cloudinary, runs Whisper + embedding inline (no Celery):

```bash
cd backend
python scripts/check_audio_ingestion.py path/to/sample.mp3
```

Use `--skip-upload` to test with a local `file://` path (Whisper/ffprobe only; Cloudinary not required).

### 3. Via API + worker

```bash
curl -F "file=@sample.mp3" http://localhost:8000/upload
curl http://localhost:8000/status/{job_id}
```

Ensure the **worker** container is running — processing happens asynchronously.

### 4. Qdrant verification

```bash
curl http://localhost:6333/collections/segments
```

`points_count` should increase after a successful job.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Job stays `pending` | Worker not running | `docker compose up worker` |
| `OPENAI_API_KEY is required` | Missing key in `.env` | Set key; restart backend/worker |
| Whisper timeout / rate limit | File too long | Use shorter demo clip (< 5 min) |
| `ffmpeg failed` on audio | Corrupt file | Re-encode with `ffmpeg -i in.mp3 -c copy out.mp3` |

---

## Related

- [Cloudinary setup](cloudinary-setup.md)
- [Video ingestion (M4)](video-ingestion-setup.md)
- [Architecture §5.2](../architecture/architecture.md)
