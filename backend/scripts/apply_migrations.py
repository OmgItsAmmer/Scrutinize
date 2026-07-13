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


def main() -> None:
    database_url = _load_database_url()
    dsn = _to_psycopg_dsn(database_url)
    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migrations:
        print(f"No migrations found in {MIGRATIONS_DIR}", file=sys.stderr)
        sys.exit(1)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS migration_history (
                    name VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            cur.execute("SELECT COUNT(*) FROM migration_history;")
            count = cur.fetchone()[0]
            if count == 0:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'users'
                    );
                """)
                users_exists = cur.fetchone()[0]
                if users_exists:
                    print("Existing database detected. Backfilling migration history...")
                    for migration in migrations:
                        if migration.name <= "010_person_auth.sql":
                            cur.execute(
                                "INSERT INTO migration_history (name) VALUES (%s) ON CONFLICT DO NOTHING;",
                                (migration.name,)
                            )
                    conn.commit()

    for migration in migrations:
        migration_name = migration.name
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM migration_history WHERE name = %s;", (migration_name,))
                if cur.fetchone():
                    print(f"Skipping {migration_name} (already applied)")
                    continue
            sql = migration.read_text(encoding="utf-8")
            conn.execute(sql)
            with conn.cursor() as cur:
                cur.execute("INSERT INTO migration_history (name) VALUES (%s);", (migration_name,))
            conn.commit()
            print(f"Applied {migration_name}")



if __name__ == "__main__":
    main()
