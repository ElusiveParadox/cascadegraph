"""Explicit backend selection. PostgreSQL never falls back to a local file."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .security import ROOT

SCHEMA = Path(__file__).with_name("storage_schema.sql")


class StorageUnavailable(RuntimeError):
    """A failed database connection/transaction, never an empty history result."""


def backend():
    value = os.getenv("CASCADEGRAPH_STORAGE", "sqlite")
    if value not in {"sqlite", "postgres"}:
        raise ValueError("CASCADEGRAPH_STORAGE must be sqlite or postgres")
    return value


class Postgres:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=()):
        # All callers use fixed SQL, with values bound separately.
        return self.connection.execute(sql.replace("?", "%s"), params)


@contextmanager
def connection(kind=None, path=None):
    kind = kind or backend()
    if kind == "postgres":
        if not os.getenv("DATABASE_URL"):
            raise StorageUnavailable("PostgreSQL selected but DATABASE_URL is missing")
        try:
            with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row, connect_timeout=5) as db:
                db.execute("SET statement_timeout = '10s'")
                db.execute("SET lock_timeout = '5s'")
                yield Postgres(db)
        except (psycopg.OperationalError, psycopg.InterfaceError):
            # Rollback/close happens before translation. Do not expose driver
            # messages (which may contain DSNs), retry writes or change backend.
            raise StorageUnavailable("PostgreSQL history storage unavailable") from None
    elif kind == "sqlite":
        path = path or os.getenv("CASCADEGRAPH_DB_PATH", str(ROOT / "cascadegraph.sqlite3"))
        db = sqlite3.connect(path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.executescript(SCHEMA.read_text())
            # Serialize read-check-write operations, like PostgreSQL advisory lock.
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
    else:
        raise ValueError("Unknown storage backend")


def lock(db):
    if isinstance(db, Postgres):
        # One bounded demo store, shared across processes/replicas. This also
        # serializes capacity checks, ownership checks, deletion and cutovers.
        db.execute("SELECT pg_advisory_xact_lock(74209531)")
