"""Lightweight spawn-safe fault injection; do not import the ASGI application."""

import sqlite3
import time
from pathlib import Path


def fault(function, args, stage, marker, calls):
    with open(calls, "a") as file:
        file.write("invoked\n")
    original = sqlite3.connect

    def stall():
        Path(marker).touch()
        time.sleep(10)

    class Connection:
        def __init__(self, db):
            object.__setattr__(self, "db", db)

        def __getattr__(self, key):
            return getattr(self.db, key)

        def __setattr__(self, key, value):
            setattr(self.db, key, value)

        def execute(self, sql, *parameters):
            if stage == "query" and sql.startswith("SELECT"):
                stall()
            return self.db.execute(sql, *parameters)

        def commit(self):
            if stage == "commit":
                stall()
            if stage == "committed":
                self.db.commit()
                stall()
            if stage == "commit_error":
                self.db.commit()
                raise sqlite3.OperationalError("private query credential source")
            return self.db.commit()

    def connect(*args, **kwargs):
        if stage == "connect":
            stall()
        return Connection(original(*args, **kwargs))

    if stage == "acquisition":
        stall()
    sqlite3.connect = connect
    return function(*args)
