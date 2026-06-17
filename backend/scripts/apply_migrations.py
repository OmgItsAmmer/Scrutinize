#!/usr/bin/env python3
"""Apply SQL migrations to Neon Postgres via DATABASE_URL."""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "migrations"


def _load_database_url() -> str:
    try:
        from app.core.config import get_settings

        return get_settings().database_url
    except Exception:
        import os

        url = os.getenv("DATABASE_URL", "").strip()
        if not url:
            print("DATABASE_URL is required (Neon connection string).", file=sys.stderr)
            sys.exit(1)
        return url


def _to_psycopg_dsn(url: str) -> str:
    return (
        url.replace("postgresql+psycopg://", "postgresql://")
        .replace("postgres://", "postgresql://")
    )


def apply_migration(path: Path, dsn: str) -> None:
    sql = path.read_text(encoding="utf-8")
    with psycopg.connect(_to_psycopg_dsn(dsn)) as conn:
        conn.run(sql)
    print(f"Applied {path.name}")


def main() -> None:
    database_url = _load_database_url()
    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migrations:
        print(f"No migrations found in {MIGRATIONS_DIR}", file=sys.stderr)
        sys.exit(1)
    for migration in migrations:
        apply_migration(migration, database_url)


if __name__ == "__main__":
    main()
