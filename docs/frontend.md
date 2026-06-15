# Frontend — Scrutinize

UI specification for the React SPA (`frontend/`). Phase 0 implements connectivity only; Phase 3 adds search and upload flows.

## Phase 0 (implemented)

- Vite + React 19 + Tailwind CSS 4
- Polls `GET /health` every 15s
- Shows **API connected** when all dependency checks pass (`database`, `redis`, `qdrant`)
- Configured via `VITE_API_URL` (default `http://localhost:8000`)

## Phase 3 (planned)

| Surface | Behaviour |
|---|---|
| Search box | Chat-style input → `POST /search`; modality chips (All / Text / Audio / Video) |
| Results | Text snippet cards; audio/video players seek to `start_time` |
| Upload | Drag-and-drop → `POST /upload`; poll `GET /status/{job_id}` |
| Library | `GET /library` — file list with status and segment counts |

See [M7 module doc](modules/m7-frontend.md) for package layout and commands.
