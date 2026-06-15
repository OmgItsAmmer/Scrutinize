# M7 — Frontend

**Status:** Implemented (Phase 0 scaffold)  
**Location:** `frontend/`

## Purpose

React SPA — currently a health dashboard that confirms connectivity to the M1 backend. Upload and search UI are not built yet (see [plan.md](../plan.md)).

## Package layout

```text
frontend/
├── src/
│   ├── App.tsx           # Health dashboard (only page)
│   ├── main.tsx          # React 19 root
│   ├── index.css         # Tailwind base (slate dark theme)
│   └── vite-env.d.ts
├── index.html
├── vite.config.ts        # @vitejs/plugin-react + @tailwindcss/vite
├── package.json          # React 19, Vite 6, Tailwind 4
├── tsconfig.json
├── Dockerfile            # node:22-alpine, npm run dev
├── .dockerignore
└── package-lock.json
```

## Implemented behaviour

`App.tsx`:

1. Reads `VITE_API_URL` (fallback `http://localhost:8000`).
2. Fetches `GET /health` on mount and every **15 seconds**.
3. Shows badge:
   - **API connected** when `health.status === "ok"`
   - **API unavailable** otherwise
4. Renders service name, version, and per-check status for `database`, `redis`, `qdrant`.
5. Shows error message if fetch fails.

No routing, upload, search, or library views exist yet.

## Configuration

| Variable | Default | Set in |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | `.env` / Docker Compose `frontend.environment` |

Docker Compose sets `VITE_API_URL: http://localhost:8000` so the browser (on the host) reaches the published backend port.

## Commands

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
npm run build        # tsc -b && vite build → dist/
npm run preview      # preview production build
```

Via Docker: `docker compose up --build` (includes frontend service).

## Dependencies

| Module | Why |
|---|---|
| **M0** | Docker service, `VITE_API_URL` |
| **M1** | `GET /health` endpoint |

## Tests

No frontend unit/E2E tests yet. Stack-level check: `tests/system/test_stack_smoke.py` hits `/health` via `VITE_API_URL`.
