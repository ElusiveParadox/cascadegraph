"""Offline, explicit data-only cutover tools. Never invoked by app startup."""

import argparse
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import Analysis
from .storage_connection import SCHEMA, connection, lock

TABLES = ("sessions", "analyses", "simulations")


def live_snapshot(db):
    """Read one consistent snapshot without changing the source."""
    now = datetime.now(UTC)
    sessions = [dict(r) for r in db.execute(
        "SELECT id, created_at FROM sessions WHERE created_at > ?",
        ((now - timedelta(hours=25)).isoformat(),))]
    owners = {r["id"] for r in sessions}
    analyses = [dict(r) for r in db.execute(
        "SELECT id, owner, data, expires_at FROM analyses WHERE expires_at > ?", (now.isoformat(),))
        if r["owner"] in owners]
    ids = {r["id"] for r in analyses}
    simulations = [dict(r) for r in db.execute("SELECT id, analysis_id, data FROM simulations")
                   if r["analysis_id"] in ids]
    snapshot = dict(zip(TABLES, (sessions, analyses, simulations), strict=True))
    validate(snapshot)
    return snapshot


def validate(snapshot):
    for row in snapshot["sessions"]:
        created = datetime.fromisoformat(row["created_at"])
        if created.tzinfo is None or created > datetime.now(UTC):
            raise ValueError("Invalid session creation time")
    for row in snapshot["analyses"]:
        data = Analysis.model_validate_json(row["data"])
        if data.id != row["id"] or data.expires_at != row["expires_at"]:
            raise ValueError("Analysis metadata does not match payload")
        created, expiry = map(datetime.fromisoformat, (data.created_at, data.expires_at))
        if created.tzinfo is None or expiry.tzinfo is None or not created < expiry <= created + timedelta(hours=24, seconds=1):
            raise ValueError("Invalid analysis retention window")
    for row in snapshot["simulations"]:
        data = json.loads(row["data"])
        if data["id"] != row["id"] or data["analysis_id"] != row["analysis_id"]:
            raise ValueError("Simulation metadata does not match payload")


def insert_snapshot(db, snapshot):
    """Empty target only: never overwrite another owner's record or replay deletes."""
    for table in TABLES:
        if db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
            raise ValueError("Target must be empty; refusing to merge or overwrite history")
    for table in TABLES:
        for row in snapshot[table]:
            placeholders = ",".join("?" for _ in row)
            db.execute(f"INSERT INTO {table} ({','.join(row)}) VALUES ({placeholders})", tuple(row.values()))
    # Compare full payloads, not just counts; failure rolls back the transaction.
    for table in TABLES:
        actual = {r["id"]: dict(r) for r in db.execute(f"SELECT * FROM {table}")}
        expected = {r["id"]: r for r in snapshot[table]}
        if actual != expected:
            raise ValueError("Snapshot verification failed")


def write_backup(path, snapshot):
    """Exclusive 0600 SQLite snapshot. Contains session bearer tokens: never publish."""
    path = Path(path)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with connection("sqlite", path) as db:
            insert_snapshot(db, snapshot)
            db.execute("CREATE TABLE backup_window (discard_after TEXT NOT NULL)")
            db.execute("INSERT INTO backup_window VALUES (?)",
                       ((datetime.now(UTC) + timedelta(minutes=15)).isoformat(),))
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def read_sqlite(path):
    path = Path(path).resolve(strict=True)
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='backup_window'").fetchone():
            deadline = db.execute("SELECT discard_after FROM backup_window").fetchone()[0]
            if datetime.fromisoformat(deadline) <= datetime.now(UTC):
                raise ValueError("Backup cutover window expired; take a fresh authoritative snapshot")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("SQLite foreign key check failed")
        return live_snapshot(db)


def import_sqlite(source, backup):
    snapshot = read_sqlite(source)
    write_backup(backup, snapshot)
    with connection("postgres") as db:
        lock(db)
        insert_snapshot(db, snapshot)
    return {table: len(rows) for table, rows in snapshot.items()}


def export_sqlite(target):
    """Fresh PG->SQLite snapshot for code rollback, not a replay of the old file."""
    with connection("postgres") as db:
        lock(db)
        snapshot = live_snapshot(db)
        write_backup(target, snapshot)
    return {table: len(rows) for table, rows in snapshot.items()}


def init_development():
    # Publish owns production DDL. No app entrypoint/build invokes this function.
    # REPLIT_ENVIRONMENT describes the platform, NOT this app's deployment.
    if os.getenv("REPLIT_DEPLOYMENT") == "1":
        raise ValueError("Production schema is managed by Publish")
    with connection("postgres") as db:
        db.connection.execute(SCHEMA.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-development")
    imp = sub.add_parser("import-sqlite")
    imp.add_argument("--source", required=True)
    imp.add_argument("--backup", required=True)
    imp.add_argument("--quiesced", action="store_true", required=True)
    exp = sub.add_parser("export-sqlite")
    exp.add_argument("--target", required=True)
    exp.add_argument("--quiesced", action="store_true", required=True)
    args = parser.parse_args()
    try:
        if args.command == "init-development":
            init_development()
        elif args.command == "import-sqlite":
            print(import_sqlite(args.source, args.backup))
        else:
            print(export_sqlite(args.target))
    except Exception:
        # Driver errors can contain connection details. Do not log them.
        parser.exit(1, "Storage operation failed; check configuration, empty target, source integrity and cutover window.\n")


if __name__ == "__main__":
    main()
