"""Session-owned SQLite snapshots, short TTL and cascading deletion."""

import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .security import ROOT


@contextmanager
def database():
    path = Path(os.getenv("CASCADEGRAPH_DB_PATH", str(ROOT / "cascadegraph.sqlite3")))
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS analyses (
          id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
          data TEXT NOT NULL, expires_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS simulations (
          id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
          data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS analyses_owner ON analyses(owner);
    """)
    now = datetime.now(UTC).isoformat()
    db.execute("DELETE FROM analyses WHERE expires_at < ?", (now,))
    db.execute("DELETE FROM sessions WHERE created_at < ?", ((datetime.now(UTC) - timedelta(hours=25)).isoformat(),))
    db.commit()
    try:
        yield db
        db.commit()
    finally:
        db.close()


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
    if not get_analysis(owner, data["analysis_id"]):
        raise PermissionError("Analysis unavailable")
    with database() as db:
        if db.execute("SELECT count(*) FROM simulations WHERE analysis_id=?", (data["analysis_id"],)).fetchone()[0] >= 20:
            raise ValueError("Simulation limit of 20 per analysis reached")
        db.execute("INSERT INTO simulations VALUES (?,?,?)", (data["id"], data["analysis_id"], json.dumps(data)))


def simulations(owner, aid):
    if not get_analysis(owner, aid):
        return []
    with database() as db:
        return [json.loads(r["data"]) for r in db.execute("SELECT data FROM simulations WHERE analysis_id=? ORDER BY rowid", (aid,))]


def get_simulation(owner, sid):
    with database() as db:
        row = db.execute("""SELECT simulations.data FROM simulations JOIN analyses
            ON analyses.id=simulations.analysis_id WHERE simulations.id=? AND analyses.owner=?""", (sid, owner)).fetchone()
        return json.loads(row["data"]) if row else None
