# Runbook — Video Ingestion (M4)

Manual setup and verification for the video pipeline: FFmpeg audio/keyframes → Whisper → GPT-4o-mini vision captions → merged segments → embeddings.

**Used by:** `POST /upload` (`.mp4`, `.mov`), Celery `process_video`, `backend/scripts/check_video_ingestion.py`.

---

## Prerequisites

Everything in [audio-ingestion-setup.md](audio-ingestion-setup.md), plus:

- **FFmpeg** installed on the host (local scripts) and in the Docker image (worker)
- OpenAI access to **Whisper** and **GPT-4o-mini** (vision)

---

## Database schema

Video segments use the same `segments` table with `modality=video` and populated `start_time` / `end_time`. Merged segment `content` includes transcript text plus `Visual: …` captions when keyframes fall in the window.

**No migration required** — see [schema.md](../db/schema.md).

---

## FFmpeg

### Docker (recommended)

The backend/worker image installs FFmpeg automatically (`backend/Dockerfile`).

### Local Windows / macOS

1. Install FFmpeg and ensure `ffmpeg` and `ffprobe` are on `PATH`.
2. Verify:

```bash
cd backend
python scripts/check_ffmpeg.py
```

Override binary paths if needed:

```env
FFMPEG_PATH=C:/ffmpeg/bin/ffmpeg.exe
FFPROBE_PATH=C:/ffmpeg/bin/ffprobe.exe
```

---

## Supported formats

| Extension | Notes |
|---|---|
| `.mp4` | Primary demo format |
| `.mov` | QuickTime |

---

## Configuration (optional)

```env
VISION_MODEL=gpt-4o-mini
VIDEO_KEYFRAME_INTERVAL_SECONDS=5
VIDEO_MAX_KEYFRAMES=15
AUDIO_SEGMENT_MIN_SECONDS=15
AUDIO_SEGMENT_MAX_SECONDS=30
```

`VIDEO_MAX_KEYFRAMES` caps vision API cost (see plan.md risks).

---

## Pipeline summary

1. Download video from Cloudinary
2. `ffprobe` → `files.duration_seconds`
3. FFmpeg extract mono 16 kHz WAV → Whisper transcript windows
4. FFmpeg extract keyframes every `VIDEO_KEYFRAME_INTERVAL_SECONDS` (max `VIDEO_MAX_KEYFRAMES`)
5. GPT-4o-mini captions each keyframe
6. Merge transcript windows + in-window captions → embed → Qdrant + Neon

---

## Manual checks

### 1. FFmpeg available

```bash
make check-ffmpeg
```

### 2. Full video pipeline (local file)

```bash
cd backend
python scripts/check_video_ingestion.py path/to/clip.mp4
```

Short clips (< 30 s, ≤ 15 keyframes) keep cost low. Use `--skip-upload` for local-only media paths.

### 3. Via API + worker

```bash
curl -F "file=@clip.mp4" http://localhost:8000/upload
curl http://localhost:8000/status/{job_id}
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ffmpeg not found` | Not installed locally | Run `check_ffmpeg.py`; install FFmpeg |
| Job `failed` + vision error | Invalid keyframe image | Check source video; reduce keyframes |
| High OpenAI cost | Long video, many keyframes | Lower `VIDEO_MAX_KEYFRAMES` or use shorter clip |
| Empty segments | Silent video, no captions | Expected for blank video; use content with speech or visuals |

---

## Related

- [Audio ingestion (M3)](audio-ingestion-setup.md)
- [Cloudinary setup](cloudinary-setup.md)
- [Architecture §5.3](../architecture/architecture.md)
