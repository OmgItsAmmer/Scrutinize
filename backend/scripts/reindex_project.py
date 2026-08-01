"""Stage a per-project reindex rollout (V5 M7): re-parse/re-chunk/re-enrich/re-embed
every text file in a project via the reindex_file Celery task.

Usage:
    python backend/scripts/reindex_project.py <project_id> [--dry-run] [--sync]

--dry-run  List the files that would be reindexed without dispatching anything.
--sync     Run reindex_file synchronously in-process instead of enqueuing on Celery
           (useful for local testing without a running worker).
"""

from __future__ import annotations

import argparse
import sys
from uuid import UUID

from sqlmodel import Session

from app.core.config import reload_settings
from app.core.database import get_engine, init_db
from app.models.file import FileModality
from app.services.job_orchestrator import JobOrchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_id", type=str)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sync", action="store_true")
    args = parser.parse_args()

    project_id = UUID(args.project_id)
    reload_settings()
    init_db()

    with Session(get_engine()) as session:
        orchestrator = JobOrchestrator(session)
        files = [
            f
            for f in orchestrator.list_files(limit=10_000, project_id=project_id)
            if f.modality == FileModality.TEXT
        ]

    if not files:
        print(f"No text files found for project {project_id}")
        return 0

    print(f"Found {len(files)} text file(s) to reindex for project {project_id}")
    if args.dry_run:
        for f in files:
            print(f"  [dry-run] {f.id} {f.filename}")
        return 0

    if args.sync:
        from app.workers.tasks import reindex_file

        for f in files:
            print(f"Reindexing {f.id} ({f.filename}) synchronously...")
            result = reindex_file.run(str(f.id))
            print(f"  -> {result}")
    else:
        from app.workers.tasks import reindex_file

        for f in files:
            async_result = reindex_file.delay(str(f.id))
            print(f"Enqueued reindex for {f.id} ({f.filename}) -> task {async_result.id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
