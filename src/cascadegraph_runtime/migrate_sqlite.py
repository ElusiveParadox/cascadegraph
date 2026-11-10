"""One-time local SQLite -> development PostgreSQL copy; never deletes source."""

import argparse
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb


def migrate(db, source: Path, *, apply=False):
    now = datetime.now(UTC)
    counts = dict(sessions=0, analyses=0, simulations=0)
    # Read a consistent snapshot without modifying/checkpointing the old file.
    with sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True) as old:
        old.execute("BEGIN")
        sessions = dict(old.execute(
            "SELECT id,created_at FROM sessions WHERE created_at > ?",
            ((now - timedelta(hours=25)).isoformat(),),
        ))
        analyses = [r for r in old.execute(
            "SELECT id,owner,data,expires_at FROM analyses WHERE expires_at > ? ORDER BY rowid",
            (now.isoformat(),),
        ) if r[1] in sessions]
        aids = {r[0] for r in analyses}
        simulations = [r for r in old.execute(
            "SELECT id,analysis_id,data FROM simulations ORDER BY rowid",
        ) if r[1] in aids]
        counts.update(sessions=len(sessions), analyses=len(analyses), simulations=len(simulations))
        if not apply:
            return counts
        # The caller owns the single PostgreSQL transaction; any conflict
        # rolls back the entire import. Never overwrite newer PostgreSQL data.
        db.execute("SELECT pg_advisory_xact_lock(7070001)")
        for token, created in sessions.items():
            db.execute("INSERT INTO cg_sessions (id,created_at) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                       (token, created))
        for aid, owner, raw, expires in analyses:
            data = json.loads(raw)
            existing = db.execute("SELECT owner,data FROM cg_analyses WHERE id=%s", (aid,)).fetchone()
            if existing and (existing[0] != owner or existing[1] != data):
                raise ValueError("Existing PostgreSQL analysis conflicts with the import; nothing was overwritten.")
            db.execute(
                """INSERT INTO cg_analyses (id,owner,data,expires_at) VALUES (%s,%s,%s,%s)
                ON CONFLICT DO NOTHING""", (aid, owner, Jsonb(data), expires),
            )
        for sid, aid, raw in simulations:
            data = json.loads(raw)
            existing = db.execute("SELECT analysis_id,data FROM cg_simulations WHERE id=%s", (sid,)).fetchone()
            if existing and (existing[0] != aid or existing[1] != data):
                raise ValueError("Existing PostgreSQL simulation conflicts with the import; nothing was overwritten.")
            db.execute(
                "INSERT INTO cg_simulations (id,analysis_id,data) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                (sid, aid, Jsonb(data)),
            )
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--apply", action="store_true", help="Copy live records; default is a count-only dry run.")
    args = parser.parse_args()
    if os.getenv("REPLIT_DEPLOYMENT") == "1":
        raise SystemExit("This command copies local data to development only.")
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as db:
            counts = migrate(db, args.source, apply=args.apply)
    except (psycopg.Error, sqlite3.Error):
        raise SystemExit("Migration failed; PostgreSQL transaction rolled back. Source was not modified.") from None
    print(("Imported: " if args.apply else "Dry run: ") + json.dumps(counts))


if __name__ == "__main__":
    main()
