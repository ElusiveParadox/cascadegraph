"""Session-owned SQLite snapshots, short TTL and cascading deletion."""

import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .security import ROOT
from .storage_execution import StorageUncertain

LOCK_SECONDS = 0.1
TRANSACTION_SECONDS = 0.4


def database_path():
    return Path(os.getenv("CASCADEGRAPH_DB_PATH", str(ROOT / "cascadegraph.sqlite3")))


@contextmanager
def database():
    deadline = time.monotonic() + TRANSACTION_SECONDS
    db = sqlite3.connect(database_path(), timeout=LOCK_SECONDS)
    try:
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 100)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        schema = """
        CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS analyses (
          id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
          data TEXT NOT NULL, expires_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS simulations (
          id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
          data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS analyses_owner ON analyses(owner);
        """
        # executescript implicitly commits; individual DDL preserves atomic quotas.
        for statement in schema.split(";"):
            if statement.strip():
                db.execute(statement)
        now = datetime.now(UTC).isoformat()
        db.execute("DELETE FROM analyses WHERE expires_at < ?", (now,))
        db.execute("DELETE FROM sessions WHERE created_at < ?", ((datetime.now(UTC) - timedelta(hours=25)).isoformat(),))
        yield db
        if time.monotonic() >= deadline:
            raise sqlite3.OperationalError("Operation deadline")
        try:
            db.commit()
        except Exception:
            raise StorageUncertain() from None
    finally:
        # Close rolls back an uncommitted transaction, including setup failures.
        db.close()


def initialize():
    with database():
        pass


def probe():
    # No schema creation, cleanup, sessions, or write locks on readiness.
    db = sqlite3.connect(f"{database_path().absolute().as_uri()}?mode=ro", uri=True, timeout=LOCK_SECONDS)
    deadline = time.monotonic() + TRANSACTION_SECONDS
    try:
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 100)
        db.execute("SELECT id FROM sessions LIMIT 1").fetchone()
    finally:
        db.close()


def resolve_session(token):
    with database() as db:
        if token and db.execute("SELECT 1 FROM sessions WHERE id=?", (token,)).fetchone():
            return token, False
        if db.execute("SELECT count(*) FROM sessions").fetchone()[0] >= 5000:
            raise ValueError("Demo session capacity reached; retry after retention cleanup")
        token = secrets.token_urlsafe(32)
        db.execute("INSERT INTO sessions VALUES (?,?)", (token, datetime.now(UTC).isoformat()))
        return token, True


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    with database() as db:
        if db.execute("SELECT count(*) FROM sessions").fetchone()[0] >= 5000:
            raise ValueError("Demo session capacity reached; retry after retention cleanup")
        db.execute("INSERT INTO sessions VALUES (?,?)", (token, datetime.now(UTC).isoformat()))
    return token


def session_exists(token: str) -> bool:
    with database() as db:
        return bool(db.execute("SELECT 1 FROM sessions WHERE id=?", (token,)).fetchone())


def save_analysis(owner, data):
    with database() as db:
        existing = db.execute("SELECT owner FROM analyses WHERE id=?", (data["id"],)).fetchone()
        if existing and existing["owner"] != owner:
            raise PermissionError("Analysis owner mismatch")
        if not existing and db.execute("SELECT count(*) FROM analyses WHERE owner=?", (owner,)).fetchone()[0] >= 20:
            raise ValueError("Delete an analysis before exceeding 20 analyses per session")
        db.execute("INSERT INTO analyses VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                   (data["id"], owner, json.dumps(data), data["expires_at"]))


def get_analysis(owner, aid):
    with database() as db:
        row = db.execute("SELECT data FROM analyses WHERE id=? AND owner=?", (aid, owner)).fetchone()
        return json.loads(row["data"]) if row else None


def list_analyses(owner):
    with database() as db:
        return [json.loads(r["data"]) for r in db.execute("SELECT data FROM analyses WHERE owner=? ORDER BY rowid DESC", (owner,))]


def delete_analysis(owner, aid):
    with database() as db:
        return db.execute("DELETE FROM analyses WHERE owner=? AND id=?", (owner, aid)).rowcount


def save_simulation(owner, data):
    with database() as db:
        if not db.execute("SELECT 1 FROM analyses WHERE id=? AND owner=?", (data["analysis_id"], owner)).fetchone():
            raise PermissionError("Analysis unavailable")
        if db.execute("SELECT count(*) FROM simulations WHERE analysis_id=?", (data["analysis_id"],)).fetchone()[0] >= 20:
            raise ValueError("Simulation limit of 20 per analysis reached")
        db.execute("INSERT INTO simulations VALUES (?,?,?)", (data["id"], data["analysis_id"], json.dumps(data)))


def simulations(owner, aid):
    with database() as db:
        return [json.loads(r["data"]) for r in db.execute(
            """SELECT s.data FROM simulations s JOIN analyses a ON a.id=s.analysis_id
            WHERE a.id=? AND a.owner=? ORDER BY s.rowid""", (aid, owner))]


def get_simulation(owner, sid):
    with database() as db:
        row = db.execute("""SELECT simulations.data FROM simulations JOIN analyses
            ON analyses.id=simulations.analysis_id WHERE simulations.id=? AND analyses.owner=?""", (sid, owner)).fetchone()
        return json.loads(row["data"]) if row else None
