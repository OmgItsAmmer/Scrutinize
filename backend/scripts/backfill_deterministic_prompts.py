"""Backfill existing projects onto the fixed gate/rewriter/synthesis templates.

Projects created before the prompt-generation redesign have freeform,
LLM-generated 'gate'/'rewriter'/'synthesis' prompts stored in
project.settings["system_prompt_overrides"], which can silently omit
accuracy-critical instructions (see build_deterministic_prompts in
app/services/v2/prompt_generator.py for why these three are no longer
LLM-generated for new projects).

This script rewrites only those three keys for every existing project using
the same deterministic templates new projects get, leaving 'generic',
'decision', and 'visual_svg' (persona/tone-facing, still LLM-generated)
untouched. Idempotent — safe to re-run.

Usage:
    python scripts/backfill_deterministic_prompts.py [--dry-run] [--project-id UUID]
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from uuid import UUID

from sqlmodel import Session, select

from app.core.database import get_engine
from app.models.project import Project
from app.services.v2.prompt_generator import build_deterministic_prompts


def backfill(dry_run: bool = False, project_id: UUID | None = None) -> None:
    engine = get_engine()
    with Session(engine) as session:
        statement = select(Project)
        if project_id is not None:
            statement = statement.where(Project.id == project_id)
        projects = list(session.exec(statement).all())
        print(f"Found {len(projects)} project(s) to check.")

        updated = 0
        for project in projects:
            settings = dict(project.settings or {})
            overrides = dict(settings.get("system_prompt_overrides") or {})
            description = settings.get("description", "") or ""

            deterministic = build_deterministic_prompts(project.name, description)

            changed = any(
                overrides.get(key) != deterministic[key] for key in ("gate", "rewriter", "synthesis")
            )
            if not changed:
                print(f"Skipping {project.name} (ID: {project.id}): already up to date.")
                continue

            overrides["gate"] = deterministic["gate"]
            overrides["rewriter"] = deterministic["rewriter"]
            overrides["synthesis"] = deterministic["synthesis"]
            settings["system_prompt_overrides"] = overrides

            print(f"Updating {project.name} (ID: {project.id})...")
            if not dry_run:
                project.settings = settings
                session.add(project)
                session.commit()
            updated += 1

        verb = "Would update" if dry_run else "Updated"
        print(f"{verb} {updated}/{len(projects)} project(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to the database.")
    parser.add_argument("--project-id", type=str, default=None, help="Only backfill a single project by ID.")
    args = parser.parse_args()

    backfill(
        dry_run=args.dry_run,
        project_id=UUID(args.project_id) if args.project_id else None,
    )
