#!/usr/bin/env python3
"""Update existing projects in Neon Postgres to refresh their system_prompt_overrides."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlmodel import Session, select
from app.core.database import get_engine
from app.models.project import Project
from app.services.v2.prompt_generator import build_deterministic_prompts, load_prompt


def main() -> None:
    engine = get_engine()
    with Session(engine) as session:
        projects = session.exec(select(Project)).all()
        print(f"Found {len(projects)} existing projects in database.")

        decision_prompt = load_prompt("decision_agent_system.txt")

        for project in projects:
            settings = dict(project.settings or {})
            description = settings.get("description", project.name)
            
            deterministic = build_deterministic_prompts(project.name, description)
            
            overrides = dict(settings.get("system_prompt_overrides", {}))
            overrides["gate"] = deterministic["gate"]
            overrides["rewriter"] = deterministic["rewriter"]
            overrides["synthesis"] = deterministic["synthesis"]
            overrides["decision"] = decision_prompt

            settings["system_prompt_overrides"] = overrides
            project.settings = settings
            session.add(project)
            print(f"Updated prompt overrides for project: '{project.name}' (ID: {project.id})")

        session.commit()
        print("All existing projects successfully updated in Neon database!")


if __name__ == "__main__":
    main()
