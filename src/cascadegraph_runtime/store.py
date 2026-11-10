"""Session-owned snapshots, unchanged TTL and atomic cascading deletion."""

import json
import secrets
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from .storage_connection import backend, connection, lock


@contextmanager
def database():
    with connection() as db:
        lock(db)
        cleanup(db)
        yield db


def cleanup(db):
    now = datetime.now(UTC)
    db.execute("DELETE FROM analyses WHERE expires_at <= ?", (now.isoformat(),))
    db.execute("DELETE FROM sessions WHERE created_at <= ?", ((now - timedelta(hours=25)).isoformat(),))


def purge():
    with database():
        pass


def description():
    mode = "PostgreSQL · durable across app updates" if backend() == "postgres" else "SQLite · ephemeral demo"
    return f"{mode} · session-owned · 24-hour retention"


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    with database() as db:
        if db.execute("SELECT count(*) AS total FROM sessions").fetchone()["total"] >= 5000:
            raise ValueError("Demo session capacity reached; retry after retention cleanup")
        db.execute("INSERT INTO sessions VALUES (?,?)", (token, datetime.now(UTC).isoformat()))
    return token


def session_exists(token: str) -> bool:
    with database() as db:
        return bool(db.execute("SELECT 1 FROM sessions WHERE id=?", (token,)).fetchone())


def ensure_account_session(owner: str):
    """Stable pseudonymous GitHub owner, without storing provider credentials."""
    with database() as db:
        if not db.execute("SELECT 1 FROM sessions WHERE id=?", (owner,)).fetchone():
            if db.execute("SELECT count(*) AS total FROM sessions").fetchone()["total"] >= 5000:
                raise ValueError("Session capacity reached")
            db.execute("INSERT INTO sessions VALUES (?,?)", (owner, datetime.now(UTC).isoformat()))
        else:
            db.execute("UPDATE sessions SET created_at=? WHERE id=?", (datetime.now(UTC).isoformat(), owner))


def save_analysis(owner, data, *, update_only=False):
    with database() as db:
        existing = db.execute("SELECT owner, expires_at FROM analyses WHERE id=?", (data["id"],)).fetchone()
        if existing and existing["owner"] != owner:
            raise PermissionError("Analysis owner mismatch")
        if update_only and not existing:
            raise PermissionError("Analysis unavailable")
        if not existing and db.execute(
            "SELECT count(*) AS total FROM analyses WHERE owner=?", (owner,)
        ).fetchone()["total"] >= 20:
            raise ValueError("Delete an analysis before exceeding 20 analyses per session")
        data = dict(data)
        if existing:
            data["expires_at"] = existing["expires_at"]
        expiry = datetime.fromisoformat(data["expires_at"])
        now = datetime.now(UTC)
        if expiry <= now or expiry > now + timedelta(hours=24):
            raise ValueError("Analysis must expire within 24 hours")
        db.execute("INSERT INTO analyses VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                   (data["id"], owner, json.dumps(data), data["expires_at"]))


def get_analysis(owner, aid):
    with database() as db:
        row = db.execute("SELECT data FROM analyses WHERE id=? AND owner=?", (aid, owner)).fetchone()
        return json.loads(row["data"]) if row else None


def list_analyses(owner):
    with database() as db:
        rows = [json.loads(r["data"]) for r in db.execute("SELECT data FROM analyses WHERE owner=?", (owner,))]
        return sorted(rows, key=lambda r: (r["created_at"], r["id"]), reverse=True)


def delete_analysis(owner, aid):
    with database() as db:
        return db.execute("DELETE FROM analyses WHERE owner=? AND id=?", (owner, aid)).rowcount


def save_simulation(owner, data):
    with database() as db:
        if not db.execute("SELECT 1 FROM analyses WHERE id=? AND owner=?", (data["analysis_id"], owner)).fetchone():
            raise PermissionError("Analysis unavailable")
        if db.execute(
            "SELECT count(*) AS total FROM simulations WHERE analysis_id=?", (data["analysis_id"],)
        ).fetchone()["total"] >= 20:
            raise ValueError("Simulation limit of 20 per analysis reached")
        db.execute("INSERT INTO simulations VALUES (?,?,?)", (data["id"], data["analysis_id"], json.dumps(data)))


def simulations(owner, aid):
    with database() as db:
        rows = [json.loads(r["data"]) for r in db.execute(
            """SELECT simulations.data FROM simulations JOIN analyses ON analyses.id=simulations.analysis_id
               WHERE analyses.id=? AND analyses.owner=?""", (aid, owner))]
        return sorted(rows, key=lambda r: (r["created_at"], r["id"]))


def get_simulation(owner, sid):
    with database() as db:
        row = db.execute("""SELECT simulations.data FROM simulations JOIN analyses
            ON analyses.id=simulations.analysis_id WHERE simulations.id=? AND analyses.owner=?""", (sid, owner)).fetchone()
        return json.loads(row["data"]) if row else None
