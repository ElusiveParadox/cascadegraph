"""Real PostgreSQL tests: unique owners, never truncate a shared database."""

import asyncio
import os
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from cascadegraph_runtime import postgres_store, store
from cascadegraph_runtime.app import app
from cascadegraph_runtime.migrate_sqlite import migrate
from cascadegraph_runtime.postgres_execution import PostgresExecutor
from cascadegraph_runtime.storage_execution import StorageUnavailable, StorageUncertain

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="PostgreSQL URL not configured")


def snapshot(owner=None):
    return {
        "id": str(uuid.uuid4()), "name": "PostgreSQL integration fixture",
        "expires_at": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
        "owner_fixture": owner,
    }


def cleanup(*owners):
    with psycopg.connect(os.environ["DATABASE_URL"]) as db:
        db.execute("DELETE FROM cg_sessions WHERE id = ANY(%s)", (list(owners),))


def test_postgres_concurrent_reads_ownership_quota_and_cascades():
    async def scenario():
        executor = PostgresExecutor()
        owner = await executor.run(store.create_session, mutation=True)
        foreign = await executor.run(store.create_session, mutation=True)
        try:
            a = snapshot()
            await executor.run(store.save_analysis, owner, a, mutation=True)
            reads = await asyncio.gather(*(executor.run(store.get_analysis, owner, a["id"]) for _ in range(12)))
            assert all(row == a for row in reads)
            assert await executor.run(store.get_analysis, foreign, a["id"]) is None
            with pytest.raises(PermissionError):
                await executor.run(store.save_analysis, foreign, a, mutation=True)
            sim = {"id": str(uuid.uuid4()), "analysis_id": a["id"], "policies": [{"source_value": 3}]}
            await executor.run(store.save_simulation, owner, sim, mutation=True)
            a["name"] = "Corrected"
            await executor.run(store.save_analysis, owner, a, mutation=True)
            assert await executor.run(store.get_simulation, owner, sim["id"]) == sim
            assert await executor.run(store.get_simulation, foreign, sim["id"]) is None
            for _ in range(18):
                await executor.run(store.save_analysis, owner, snapshot(), mutation=True)
            # Both writes compete for the final quota slot; exactly one wins.
            results = await asyncio.gather(
                *(executor.run(store.save_analysis, owner, snapshot(), mutation=True) for _ in range(2)),
                return_exceptions=True,
            )
            assert sum(r is None for r in results) == 1
            assert sum(isinstance(r, ValueError) for r in results) == 1
            assert await executor.run(store.delete_analysis, foreign, a["id"], mutation=True) == 0
            assert await executor.run(store.delete_analysis, owner, a["id"], mutation=True) == 1
            assert await executor.run(store.get_simulation, owner, sim["id"]) is None
            assert len(await executor.run(store.list_analyses, owner)) == 19
        finally:
            await executor.close()
            cleanup(owner, foreign)
        assert executor.active == 0
    asyncio.run(scenario())


def test_postgres_lock_timeout_is_bounded_and_connection_recovers():
    async def scenario():
        executor = PostgresExecutor()
        owner = await executor.run(store.create_session, mutation=True)
        try:
            with psycopg.connect(os.environ["DATABASE_URL"]) as lock:
                lock.execute("SELECT id FROM cg_sessions WHERE id=%s FOR UPDATE", (owner,))
                before = time.monotonic()
                with pytest.raises(StorageUnavailable):
                    await executor.run(store.save_analysis, owner, snapshot(), mutation=True)
                assert time.monotonic() - before < 3
            assert await executor.run(store.list_analyses, owner) == []
            await executor.ready()
            await executor.run(store.save_analysis, owner, snapshot(), mutation=True)
            assert len(await executor.run(store.list_analyses, owner)) == 1
        finally:
            await executor.close()
            cleanup(owner)
    asyncio.run(scenario())


def test_postgres_import_is_atomic_repeatable_and_preserves_owner(tmp_path, monkeypatch):
    path = tmp_path / "legacy.sqlite3"
    monkeypatch.setenv("CASCADEGRAPH_DB_PATH", str(path))
    owner = store.create_session()
    a = snapshot()
    store.save_analysis(owner, a)
    sim = {"id": str(uuid.uuid4()), "analysis_id": a["id"]}
    store.save_simulation(owner, sim)
    before = path.read_bytes()
    try:
        with psycopg.connect(os.environ["DATABASE_URL"]) as db:
            assert migrate(db, path) == {"sessions": 1, "analyses": 1, "simulations": 1}
            assert not db.execute("SELECT 1 FROM cg_sessions WHERE id=%s", (owner,)).fetchone()
            migrate(db, path, apply=True)
        with psycopg.connect(os.environ["DATABASE_URL"]) as db:
            migrate(db, path, apply=True)
            assert db.execute("SELECT owner,data FROM cg_analyses WHERE id=%s", (a["id"],)).fetchone() == (owner, a)
            assert db.execute("SELECT count(*) FROM cg_simulations WHERE analysis_id=%s", (a["id"],)).fetchone()[0] == 1
        assert before == path.read_bytes()
        with sqlite3.connect(path) as old:
            old.execute("UPDATE analyses SET data=? WHERE id=?", ('{"changed":true}', a["id"]))
        with pytest.raises(ValueError), psycopg.connect(os.environ["DATABASE_URL"]) as db:
            migrate(db, path, apply=True)
        with psycopg.connect(os.environ["DATABASE_URL"]) as db:
            assert db.execute("SELECT data FROM cg_analyses WHERE id=%s", (a["id"],)).fetchone()[0] == a
    finally:
        cleanup(owner)


def test_postgres_http_restart_cookie_continuity_and_expiry(monkeypatch):
    monkeypatch.delenv("CASCADEGRAPH_DB_PATH", raising=False)
    app.middleware_stack = None
    owner = None
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/health/ready").status_code == 200
            assert "PostgreSQL" in client.get("/api/v1/status").json()["storage"]
            owner = client.cookies.get("cg_session")
            response = client.post("/api/v1/analyses", json={"source_type": "sample", "use_ai": False})
            assert response.status_code == 201, response.text
            a = response.json()
        # Fresh lifecycle/pool, same browser owner: analyses survive API restart.
        with TestClient(app) as client:
            client.cookies.set("cg_session", owner, path="/api")
            assert client.get(f"/api/v1/analyses/{a['id']}").status_code == 200
            with psycopg.connect(os.environ["DATABASE_URL"]) as db:
                db.execute("UPDATE cg_analyses SET expires_at=CURRENT_TIMESTAMP - INTERVAL '1 hour' WHERE id=%s",
                           (a["id"],))
            assert client.get(f"/api/v1/analyses/{a['id']}").status_code == 404
            assert client.get("/api/v1/analyses").json() == []
    finally:
        if owner:
            cleanup(owner)


def test_development_commands_refuse_deployment(monkeypatch):
    from cascadegraph_runtime.setup_database import main

    monkeypatch.setenv("REPLIT_DEPLOYMENT", "1")
    with pytest.raises(SystemExit, match="Publish"):
        main()


def test_postgres_schema_has_no_runtime_ddl():
    source = Path(__file__).resolve().parents[1] / "src/cascadegraph_runtime/postgres_store.py"
    assert "CREATE TABLE" not in source.read_text()


def test_postgres_ambiguous_commit_is_never_replayed(monkeypatch):
    async def scenario():
        executor = PostgresExecutor()
        calls = []

        async def operation(db, *args):
            calls.append("write")

        @asynccontextmanager
        async def lost_commit():
            yield object()
            raise psycopg.OperationalError("private database error must not escape")

        monkeypatch.setattr(postgres_store, "save_analysis", operation)
        monkeypatch.setattr(executor._pool, "connection", lost_commit)
        try:
            with pytest.raises(StorageUncertain) as error:
                await executor.run(store.save_analysis, "owner", {}, mutation=True)
            assert "private" not in str(error.value)
            assert calls == ["write"]
            assert executor.active == 0
        finally:
            await executor.close()
    asyncio.run(scenario())


def test_postgres_cancelled_mutations_do_not_run_later(monkeypatch):
    async def scenario():
        executor = PostgresExecutor()
        owner = await executor.run(store.create_session, mutation=True)
        a = snapshot()
        started = asyncio.Event()

        async def interrupted(db, owner, data):
            await db.execute(
                "INSERT INTO cg_analyses (id,owner,data,expires_at) VALUES (%s,%s,'{}',%s)",
                (data["id"], owner, data["expires_at"]),
            )
            started.set()
            await asyncio.sleep(10)

        monkeypatch.setattr(postgres_store, "save_analysis", interrupted)
        task = asyncio.create_task(executor.run(store.save_analysis, owner, a, mutation=True))
        try:
            await asyncio.wait_for(started.wait(), timeout=3)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert executor.active == 0
            assert await executor.run(store.get_analysis, owner, a["id"]) is None
            # Cancelled before admission: releasing capacity cannot start a write.
            executor._slots = asyncio.Semaphore(0)
            queued = asyncio.create_task(executor.run(store.save_analysis, owner, snapshot(), mutation=True))
            await asyncio.sleep(0.01)
            queued.cancel()
            with pytest.raises(asyncio.CancelledError):
                await queued
            executor._slots.release()
            assert executor.active == 0
        finally:
            await executor.close()
            cleanup(owner)
    asyncio.run(scenario())
