"""Real isolated SQLite workers, deterministic faults, no shared database outages."""

import asyncio
import multiprocessing
import sqlite3
import time

import httpx
import pytest
from storage_faults import fault

from cascadegraph_runtime import store
from cascadegraph_runtime.app import app
from cascadegraph_runtime.storage_execution import (
    CAPACITY,
    OPERATION_SECONDS,
    SHUTDOWN_SECONDS,
    StorageExecutor,
    StorageOverloaded,
    StorageUnavailable,
    StorageUncertain,
)


async def until_file(path):
    deadline = time.monotonic() + 2
    while not path.exists():
        assert time.monotonic() < deadline, "worker did not reach synchronization point"
        await asyncio.sleep(0.005)


def assert_drained(executor):
    assert executor.active == 0
    assert not [p for p in multiprocessing.active_children() if p.name == "cascadegraph-storage"]


@pytest.mark.parametrize("stage", ["acquisition", "connect", "query", "commit", "committed"])
def test_deadlines_heartbeat_and_single_invocation(tmp_path, monkeypatch, stage):
    monkeypatch.setenv("CASCADEGRAPH_DB_PATH", str(tmp_path / "db.sqlite3"))
    store.initialize()
    marker, calls = tmp_path / "started", tmp_path / "calls"

    async def scenario():
        executor = StorageExecutor()
        beats = 0

        async def heartbeat():
            nonlocal beats
            while True:
                beats += 1
                await asyncio.sleep(0.01)

        pulse = asyncio.create_task(heartbeat())
        start = time.monotonic()
        try:
            with pytest.raises(StorageUncertain):
                await executor.run(fault, store.resolve_session, ("",), stage, str(marker), str(calls), mutation=True)
            assert marker.exists()
            assert time.monotonic() - start < OPERATION_SECONDS + 0.6
            assert beats >= 15
            assert calls.read_text() == "invoked\n"
            assert_drained(executor)
            # A timed-out commit may have succeeded: never claim rollback.
            assert len(store.list_analyses("unknown")) == 0
            assert await executor.run(store.probe) is None
        finally:
            pulse.cancel()
            await asyncio.gather(pulse, return_exceptions=True)
            await executor.close()
        assert_drained(executor)

    asyncio.run(scenario())


def test_saturation_cancellation_and_shutdown(tmp_path, monkeypatch):
    monkeypatch.setenv("CASCADEGRAPH_DB_PATH", str(tmp_path / "db.sqlite3"))
    store.initialize()

    async def scenario():
        executor = StorageExecutor()
        markers = [tmp_path / str(i) for i in range(CAPACITY)]
        tasks = [asyncio.create_task(executor.run(
            fault, store.probe, (), "connect", str(marker), str(tmp_path / f"calls{i}"),
        )) for i, marker in enumerate(markers)]
        await asyncio.gather(*(until_file(marker) for marker in markers))
        before = time.monotonic()
        burst = await asyncio.gather(*(executor.run(store.create_session, mutation=True) for _ in range(8)),
                                     return_exceptions=True)
        assert all(isinstance(result, StorageOverloaded) for result in burst)
        assert time.monotonic() - before < 0.1
        assert executor.active == CAPACITY
        tasks[0].cancel()
        await asyncio.gather(tasks[0], return_exceptions=True)
        assert executor.active == CAPACITY - 1
        assert await executor.run(store.probe) is None
        before = time.monotonic()
        await executor.close()
        await asyncio.gather(*tasks, return_exceptions=True)
        assert time.monotonic() - before < SHUTDOWN_SECONDS
        assert_drained(executor)
        with store.database() as db:
            assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
        with pytest.raises(StorageUnavailable):
            await executor.run(store.probe)

    asyncio.run(scenario())


def test_cancel_before_start_and_repeated_cancel_keep_accounting(tmp_path, monkeypatch):
    monkeypatch.setenv("CASCADEGRAPH_DB_PATH", str(tmp_path / "db.sqlite3"))
    store.initialize()

    async def scenario():
        executor = StorageExecutor()
        marker, calls = tmp_path / "started", tmp_path / "calls"
        pending = asyncio.create_task(executor.run(
            fault, store.create_session, (), "connect", str(marker), str(calls), mutation=True))
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        assert not calls.exists() and executor.active == 0
        running = asyncio.create_task(executor.run(
            fault, store.create_session, (), "connect", str(marker), str(calls), mutation=True))
        await until_file(marker)
        running.cancel()
        # Cancellation schedules cleanup, but does not release a still-live slot.
        assert executor.active == 1
        await asyncio.sleep(0)
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)
        await executor.close()
        assert calls.read_text() == "invoked\n"
        assert_drained(executor)
        with store.database() as db:
            assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0

    asyncio.run(scenario())


def test_readiness_does_not_initialize_or_mutate_storage(tmp_path, monkeypatch):
    path = tmp_path / "db.sqlite3"
    monkeypatch.setenv("CASCADEGRAPH_DB_PATH", str(path))
    with pytest.raises(sqlite3.OperationalError):
        store.probe()
    assert not path.exists()
    store.initialize()
    # Expired records must not be cleaned up by a health probe.
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO sessions VALUES ('expired', '2000-01-01')")
    before = path.read_bytes()
    store.probe()
    assert path.read_bytes() == before


def test_actual_sqlite_lock_and_query_deadlines(tmp_path, monkeypatch):
    monkeypatch.setenv("CASCADEGRAPH_DB_PATH", str(tmp_path / "db.sqlite3"))
    token = store.create_session()
    locked = sqlite3.connect(store.database_path())
    locked.execute("BEGIN EXCLUSIVE")

    async def scenario():
        executor = StorageExecutor()
        try:
            start = time.monotonic()
            with pytest.raises(StorageUnavailable):
                await executor.run(store.session_exists, token)
            assert time.monotonic() - start < 0.7
        finally:
            await executor.close()
        assert_drained(executor)

    try:
        asyncio.run(scenario())
    finally:
        locked.rollback()
        locked.close()
    # Real SQLite VM work is interrupted, not just the HTTP wait.
    before = time.monotonic()
    with pytest.raises(sqlite3.OperationalError):
        with store.database() as db:
            db.execute("""WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<100000000)
                          SELECT sum(x) FROM n""").fetchone()
    assert time.monotonic() - before < 0.7
    assert store.session_exists(token)


@pytest.mark.parametrize("cookie", ["existing", "new", "invalid", "oversized"])
def test_http_cookie_continuity_health_and_recovery(client, tmp_path, monkeypatch, cookie, caplog):
    created = client.post("/api/v1/analyses", json={"source_type": "sample"})
    aid = created.json()["id"]
    original_cookie = client.cookies.get("cg_session")
    cookies = {"existing": original_cookie, "new": "", "invalid": "not-a-session", "oversized": "a" * 100}
    original = app.state.storage.run
    calls = tmp_path / "calls"
    marker = tmp_path / "started"

    async def unavailable(function, *args, **kwargs):
        return await original(fault, function, args, "connect", str(marker), str(calls), **kwargs)

    monkeypatch.setattr(app.state.storage, "run", unavailable)
    headers = {"Cookie": f"cg_session={cookies[cookie]}"} if cookies[cookie] else {"Cookie": ""}
    before = time.monotonic()
    response = client.get("/api/v1/analyses", headers=headers)
    assert time.monotonic() - before < 1.5
    assert response.status_code == 503
    assert "set-cookie" not in response.headers
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["correlation_id"] == response.headers["x-correlation-id"]
    for path in ("/api/healthz", "/api/v1/health/live", "/api/v1/validation"):
        before = time.monotonic()
        healthy = client.get(path, headers=headers)
        assert healthy.status_code == 200
        assert time.monotonic() - before < 0.2
        assert "set-cookie" not in healthy.headers
    assert client.get("/api/v1/health/ready").status_code == 503
    count = calls.read_text().count("invoked")
    for _ in range(8):
        assert client.get("/api/v1/health/ready").status_code == 503
    assert calls.read_text().count("invoked") == count
    assert "private query credential source" not in caplog.text + response.text
    monkeypatch.setattr(app.state.storage, "run", original)
    time.sleep(0.51)
    assert client.get("/api/v1/health/ready").status_code == 200
    response = client.get(f"/api/v1/analyses/{aid}", headers={"Cookie": f"cg_session={original_cookie}"})
    assert response.status_code == 200
    assert response.json()["id"] == aid
    assert "set-cookie" not in response.headers
    foreign = client.get(f"/api/v1/analyses/{aid}", headers={"Cookie": "cg_session=foreign"})
    assert foreign.status_code == 404
    assert_drained(app.state.storage)


def test_uncertain_commit_is_not_replayed(client, tmp_path, monkeypatch):
    client.get("/api/v1/status")
    original = app.state.storage.run
    calls = tmp_path / "calls"

    async def injected(function, *args, **kwargs):
        if function == store.save_analysis:
            return await original(fault, function, args, "commit_error",
                                  str(tmp_path / "started"), str(calls), **kwargs)
        return await original(function, *args, **kwargs)

    monkeypatch.setattr(app.state.storage, "run", injected)
    response = client.post("/api/v1/analyses", json={"source_type": "sample"})
    assert response.status_code == 503
    assert response.json()["code"] == "STORAGE_OUTCOME_UNCERTAIN"
    assert "do not blindly replay" in response.json()["error"]
    assert "retry-after" not in response.headers
    assert "set-cookie" not in response.headers
    assert "private query" not in response.text
    assert calls.read_text() == "invoked\n"
    assert len(client.get("/api/v1/analyses").json()) == 1
    assert_drained(app.state.storage)


def test_concurrent_ownership_and_atomic_quotas(tmp_path, monkeypatch):
    monkeypatch.setenv("CASCADEGRAPH_DB_PATH", str(tmp_path / "db.sqlite3"))
    owner, foreign = store.create_session(), store.create_session()

    def data(i):
        return {"id": str(i), "expires_at": "2999-01-01", "policies": []}

    for i in range(19):
        store.save_analysis(owner, data(i))

    async def scenario():
        executor = StorageExecutor()
        try:
            results = await asyncio.gather(
                executor.run(store.save_analysis, owner, data(20), mutation=True),
                executor.run(store.save_analysis, owner, data(21), mutation=True), return_exceptions=True)
            assert sum(result is None for result in results) == 1
            assert sum(isinstance(result, ValueError) for result in results) == 1
            assert len(store.list_analyses(owner)) == 20
            results = await asyncio.gather(
                executor.run(store.get_analysis, foreign, "0"),
                executor.run(store.save_analysis, foreign, data(0), mutation=True), return_exceptions=True)
            assert results[0] is None
            assert isinstance(results[1], PermissionError)
            for i in range(19):
                store.save_simulation(owner, {"id": f"s{i}", "analysis_id": "0"})
            results = await asyncio.gather(
                *(executor.run(store.save_simulation, owner, {"id": f"s{i}", "analysis_id": "0"}, mutation=True)
                  for i in (20, 21)), return_exceptions=True)
            assert sum(result is None for result in results) == 1
            assert sum(isinstance(result, ValueError) for result in results) == 1
            assert store.simulations(foreign, "0") == []
            assert store.get_simulation(foreign, "s0") is None
            assert store.delete_analysis(foreign, "0") == 0
        finally:
            await executor.close()
        assert_drained(executor)

    asyncio.run(scenario())


def test_http_burst_is_bounded_and_live_during_outage(tmp_path, monkeypatch):
    monkeypatch.setenv("CASCADEGRAPH_DB_PATH", str(tmp_path / "db.sqlite3"))
    app.middleware_stack = None

    async def scenario():
        async with app.router.lifespan_context(app):
            original = app.state.storage.run
            marker = tmp_path / "started"

            async def injected(function, *args, **kwargs):
                return await original(fault, function, args, "connect", str(marker), str(tmp_path / "calls"), **kwargs)

            monkeypatch.setattr(app.state.storage, "run", injected)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as http:
                before = time.monotonic()
                requests = [asyncio.create_task(http.get("/api/v1/analyses")) for _ in range(10)]
                await until_file(marker)
                start = time.monotonic()
                live = await http.get("/api/v1/health/live")
                assert live.status_code == 200 and "set-cookie" not in live.headers
                assert time.monotonic() - start < 0.15
                results = await asyncio.gather(*requests)
                assert time.monotonic() - before < 1.5
                assert all(r.status_code == 503 and "set-cookie" not in r.headers for r in results)
                assert sum(r.json()["code"] == "STORAGE_OVERLOADED" for r in results) == 8
                assert_drained(app.state.storage)
        assert_drained(app.state.storage)

    asyncio.run(scenario())
