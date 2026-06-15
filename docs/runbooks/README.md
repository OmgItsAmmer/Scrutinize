# Runbooks — Scrutinize

Step-by-step setup guides for external services used by the project.

| Runbook | Service | Used for |
|---|---|---|
| [cloudinary-setup.md](cloudinary-setup.md) | Cloudinary | Raw file storage (text, audio, video uploads) |
| [audio-ingestion-setup.md](audio-ingestion-setup.md) | OpenAI Whisper | M3 audio transcription + indexing |
| [video-ingestion-setup.md](video-ingestion-setup.md) | FFmpeg + OpenAI Vision | M4 video extraction + captioning + indexing |

Related configuration (no runbook yet):

- **Neon** — relational database (`DATABASE_URL`); see [README.md](../../README.md#quick-start)
- **Qdrant / Redis** — local via `docker compose up`
