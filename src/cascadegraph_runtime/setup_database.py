"""Explicit development-only schema setup. Never called by API startup/build."""

import os
from pathlib import Path

import psycopg


def main():
    if os.getenv("REPLIT_DEPLOYMENT") == "1":
        raise SystemExit("Production schema changes belong to Replit Publish, not this development command.")
    schema = Path(__file__).resolve().parents[2] / "schema" / "postgresql.sql"
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as db:
        db.execute(schema.read_text())
    print("Development PostgreSQL schema is ready.")


if __name__ == "__main__":
    main()
