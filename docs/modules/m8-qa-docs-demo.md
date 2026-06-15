# M8 — QA, Docs & Demo

**Status:** Implemented (Phase 0 test suite + docs)  
**Location:** `tests/`, `docs/`, `README.md`

## Purpose

Test tiers, CI alignment, and project documentation for Scrutinize.

## Test layout

```text
tests/
├── conftest.py              # SQLite engine, mocks, TestClient fixtures
├── unit/
│   ├── test_health.py
│   ├── test_job_orchestrator.py
│   └── test_api_routes.py
├── integration/
│   └── test_health_integration.py
├── system/
│   └── test_stack_smoke.py
└── security/
    └── test_api_security.py
```

## Test tiers

| Tier | Marker | Directory | CI job |
|---|---|---|---|
| Unit | `@pytest.mark.unit` | `tests/unit/` | `unit-tests` |
| Integration | `@pytest.mark.integration` | `tests/integration/` | `integration-tests` |
| System | `@pytest.mark.system` | `tests/system/` | `system-tests` |
| Security | `@pytest.mark.security` | `tests/security/` | `security-tests` |

Config: `pytest.ini` (`pythonpath = backend`) + `[tool.pytest.ini_options]` in `backend/pyproject.toml`.

### conftest behaviour

- Sets `DATABASE_URL=sqlite://` when unset (avoids hanging on Postgres).
- Unit/security tests mock Redis and Qdrant health checks.
- Integration tests use real Redis/Qdrant probes when those services are reachable.
- `client` fixture: in-memory SQLite + FastAPI `TestClient` with session override.

## Implemented tests

| File | Tier | Asserts |
|---|---|---|
| `test_health.py` | unit | `build_health_response` ok/degraded aggregation |
| `test_job_orchestrator.py` | unit | Create/update job, missing job returns `None` |
| `test_api_routes.py` | unit | `/health` 200 + checks; `/status/{uuid}` 404 |
| `test_health_integration.py` | integration | `/health` with real check keys |
| `test_stack_smoke.py` | system | Live `GET /health` (CI or `RUN_SYSTEM_TESTS=1`) |
| `test_api_security.py` | security | No secret strings in `/health` body; safe 404 on unknown job |

## Run locally

```bash
make install-backend
make test-unit
make test-integration
make test-system          # needs stack up or RUN_SYSTEM_TESTS=1
make test-security
make lint                 # ruff — local only, not in CI
```

## CI/CD

See [M0 — Infrastructure](m0-infrastructure.md). Ruff is excluded from GitHub Actions.

## Documentation map

| Path | Content |
|---|---|
| `docs/architecture/architecture.md` | System design |
| `docs/plan.md` | Phases and future modules |
| `docs/modules/` | Implemented modules (M0, M1, M7, M8) |
| `docs/db/` | Neon schema DDL + reference |
| `docs/runbooks/` | Cloudinary setup |
| `docs/frontend.md` | UI spec (future phases) |
| `README.md` | Quick start |

## Dependencies

Validates **M0** (CI), **M1** (API/orchestrator/health), and **M7** (system smoke via `/health`).
