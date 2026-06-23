"""Print effective backend config (run after editing backend/.env)."""
from __future__ import annotations

import sys

from app.core.config import reload_settings
from app.services.vector_store import VectorStore


def main() -> int:
    settings = reload_settings()
    print("Effective config (from backend/.env):")
    print(f"  QDRANT_URL={settings.qdrant_url}")
    print(f"  QDRANT_API_KEY={'set' if settings.qdrant_api_key else 'not set'}")
    print(f"  REDIS_URL={settings.redis_url}")
    print(f"  CELERY_TASK_ALWAYS_EAGER={settings.task_always_eager}")

    try:
        store = VectorStore(settings)
        exists = store.collection_exists()
        count = store.count_points() if exists else 0
        print(f"  Qdrant OK — collection={settings.qdrant_collection} exists={exists} points={count}")
    except Exception as exc:
        print(f"  Qdrant FAILED — {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
