# Scrutinize — Module Index

Reference for **implemented** modules only. Planned modules (M2–M6) are described in [plan.md](../plan.md).

| Module | Name | Doc |
|---|---|---|
| **M0** | Infrastructure & DevOps | [m0-infrastructure.md](m0-infrastructure.md) |
| **M1** | Backend Core | [m1-backend-core.md](m1-backend-core.md) |
| **M7** | Frontend | [m7-frontend.md](m7-frontend.md) |
| **M8** | QA, Docs & Demo | [m8-qa-docs-demo.md](m8-qa-docs-demo.md) |

## Dependency graph (implemented)

```text
M0 (infra: Docker, CI, Neon env, Cloudinary env)
 ├── M1 (FastAPI, Neon models, Celery, Cloudinary client)
 ├── M7 (React health dashboard → M1 /health)
 └── M8 (pytest tiers, docs)
```

## Related docs

- [Architecture](../architecture/architecture.md)
- [Project plan](../plan.md)
- [Database schema](../db/schema_doc.md)
- [Runbooks](../runbooks/README.md)
