"""Bounded SQLite execution, isolated from the event loop and shared thread pool.

No admission queue: two running operations maximum. A process, unlike a thread,
can be stopped even when connect/fsync/commit is stuck outside SQLite's VM.
"""

import asyncio
import multiprocessing
import os
import pickle
import sqlite3
import tempfile
import threading
import time
from pathlib import Path

CAPACITY = 2
OPERATION_SECONDS = 0.8
REAP_SECONDS = 0.2
SHUTDOWN_SECONDS = 1.0
PROBE_COOLDOWN_SECONDS = 0.5


class StorageUnavailable(Exception):
    code = "STORAGE_UNAVAILABLE"


class StorageOverloaded(StorageUnavailable):
    code = "STORAGE_OVERLOADED"


class StorageUncertain(StorageUnavailable):
    code = "STORAGE_OUTCOME_UNCERTAIN"


def _execute(function, args, database_path, output, mutation):
    # Spawned children own all connections and transactions. No inherited handles.
    if database_path is not None:
        os.environ["CASCADEGRAPH_DB_PATH"] = database_path
    try:
        result = ("ok", function(*args))
    except ValueError as exc:
        result = ("invalid", str(exc))
    except PermissionError:
        result = ("forbidden", None)
    except StorageUncertain:
        result = ("uncertain", None)
    except sqlite3.Error:
        # The store converts commit errors to StorageUncertain; these failures
        # happened before commit and the connection has been closed/rolled back.
        result = ("unavailable", None)
    except BaseException:
        # Never serialize database errors, queries, paths, or exception tracebacks.
        result = ("uncertain" if mutation else "unavailable", None)
    with open(output, "wb") as file:
        pickle.dump(result, file)


class StorageExecutor:
    def __init__(self):
        self._context = multiprocessing.get_context("spawn")
        self._lock = threading.Lock()
        self._jobs = {}
        self._closed = False
        self._probe_running = False
        self._probe_failed_until = 0.0
        self.users = 0

    @property
    def active(self):
        with self._lock:
            return len(self._jobs)

    async def _reap(self, process, output):
        try:
            if process.is_alive():
                process.terminate()
            end = time.monotonic() + REAP_SECONDS
            while process.is_alive() and time.monotonic() < end:
                await asyncio.sleep(0.005)
            if process.is_alive():
                process.kill()
            # SIGKILL cannot interrupt uninterruptible kernel IO. Do not pretend
            # capacity was released or shutdown succeeded if the OS cannot reap.
            end = time.monotonic() + REAP_SECONDS
            while process.is_alive() and time.monotonic() < end:
                await asyncio.sleep(0.005)
            if process.is_alive():
                raise RuntimeError("Storage worker could not be stopped")
            process.join(timeout=0)
            process.close()
            Path(output).unlink(missing_ok=True)
            with self._lock:
                self._jobs.pop(output, None)
        except BaseException:
            # Failed cleanup remains accounted for; shutdown will fail explicitly.
            raise

    async def run(self, function, *args, mutation=False):
        # No await between admission and registration: cancellation cannot leave
        # a queued mutation which later starts. Lock also supports nested clients.
        deadline = time.monotonic() + OPERATION_SECONDS
        with self._lock:
            if self._closed:
                raise StorageUnavailable()
            if len(self._jobs) >= CAPACITY:
                raise StorageOverloaded()
            fd, output = tempfile.mkstemp(prefix="cg-storage-")
            os.close(fd)
            process = self._context.Process(
                target=_execute,
                args=(function, args, os.getenv("CASCADEGRAPH_DB_PATH"), output, mutation),
                name="cascadegraph-storage",
            )
            try:
                process.start()
            except Exception:
                Path(output).unlink(missing_ok=True)
                raise StorageUnavailable() from None
            self._jobs[output] = process
        try:
            while process.is_alive():
                if time.monotonic() >= deadline:
                    raise StorageUncertain() if mutation else StorageUnavailable()
                await asyncio.sleep(0.005)
            try:
                with open(output, "rb") as file:
                    status, value = pickle.load(file)
            except Exception:
                raise StorageUncertain() if mutation else StorageUnavailable() from None
            if status == "ok":
                return value
            if status == "invalid":
                raise ValueError(value)
            if status == "forbidden":
                raise PermissionError("Object unavailable")
            if status == "uncertain":
                raise StorageUncertain()
            raise StorageUnavailable()
        finally:
            cleanup = asyncio.create_task(self._reap(process, output))
            # A disconnected caller cannot free capacity while a worker is alive.
            await asyncio.shield(cleanup)

    async def ready(self):
        from . import store

        with self._lock:
            if self._probe_running or time.monotonic() < self._probe_failed_until:
                raise StorageUnavailable()
            self._probe_running = True
        try:
            await self.run(store.probe)
        except BaseException:
            with self._lock:
                self._probe_failed_until = time.monotonic() + PROBE_COOLDOWN_SECONDS
            raise
        finally:
            with self._lock:
                self._probe_running = False

    async def close(self):
        with self._lock:
            self._closed = True
            jobs = list(self._jobs.values())
        for process in jobs:
            if process.is_alive():
                process.terminate()
        deadline = time.monotonic() + SHUTDOWN_SECONDS
        while self.active and time.monotonic() < deadline:
            await asyncio.sleep(0.005)
        if self.active:
            for process in jobs:
                try:
                    if process.is_alive():
                        process.kill()
                except ValueError:
                    pass
            raise RuntimeError("Storage shutdown did not drain within its budget")
