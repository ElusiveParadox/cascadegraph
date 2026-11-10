"""Lifecycle-owned async PostgreSQL pool with bounded work and no replay."""

import asyncio
import logging
import os
import time

import psycopg
from psycopg_pool import AsyncConnectionPool, PoolClosed, PoolTimeout

from . import postgres_store
from .storage_execution import StorageOverloaded, StorageUnavailable, StorageUncertain

CAPACITY = 8
WAITERS = 8
OPERATION_SECONDS = 5.0
PROBE_COOLDOWN_SECONDS = 0.5


class PostgresExecutor:
    def __init__(self):
        self.users = 0
        self.active = 0
        self._closed = False
        self._probe_running = False
        self._probe_failed_until = 0.0
        self._slots = asyncio.Semaphore(CAPACITY)
        self._pool = AsyncConnectionPool(
            conninfo=os.environ["DATABASE_URL"],
            min_size=0, max_size=CAPACITY, timeout=1, open=False,
            reconnect_timeout=2,
            kwargs={
                "connect_timeout": 2,
                "options": "-c statement_timeout=1500 -c lock_timeout=500 -c idle_in_transaction_session_timeout=3000",
            },
        )
        # Library reconnect warnings may include host/account details. Emit only
        # our sanitized operation failure codes at the HTTP boundary.
        pool_logger = logging.getLogger("psycopg.pool")
        if not any(isinstance(f, _SafePoolLog) for f in pool_logger.filters):
            pool_logger.addFilter(_SafePoolLog())

    async def run(self, function, *args, mutation=False):
        if self._closed:
            raise StorageUnavailable()
        if self.active >= CAPACITY + WAITERS:
            raise StorageOverloaded()
        self.active += 1
        committing = False
        try:
            await self._pool.open()
            async with asyncio.timeout(OPERATION_SECONDS):
                try:
                    await asyncio.wait_for(self._slots.acquire(), timeout=1)
                except TimeoutError:
                    raise StorageOverloaded() from None
                try:
                    async with self._pool.connection() as db:
                        result = await getattr(postgres_store, function.__name__)(db, *args)
                        committing = True
                    return result
                finally:
                    self._slots.release()
        except (ValueError, PermissionError, StorageUnavailable):
            raise
        except asyncio.CancelledError:
            # psycopg cancels the server query and rolls back before releasing
            # the connection. Nothing is queued for later automatic replay.
            raise
        except (psycopg.Error, PoolTimeout, PoolClosed, TimeoutError):
            if committing and mutation:
                raise StorageUncertain() from None
            raise StorageUnavailable() from None
        finally:
            self.active -= 1

    async def ready(self):
        from . import store

        if self._probe_running or time.monotonic() < self._probe_failed_until:
            raise StorageUnavailable()
        self._probe_running = True
        try:
            await self.run(store.probe)
        except BaseException:
            self._probe_failed_until = time.monotonic() + PROBE_COOLDOWN_SECONDS
            raise
        finally:
            self._probe_running = False

    async def close(self):
        self._closed = True
        deadline = time.monotonic() + OPERATION_SECONDS + 1
        while self.active and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        await self._pool.close(timeout=1)
        if self.active:
            raise RuntimeError("PostgreSQL shutdown did not drain within its budget")


class _SafePoolLog(logging.Filter):
    def filter(self, record):
        record.msg = "PostgreSQL pool connection unavailable"
        record.args = ()
        record.exc_info = None
        return True
