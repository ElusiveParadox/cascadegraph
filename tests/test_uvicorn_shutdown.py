"""Real SIGTERM/disconnect regression; never target managed servers or shared DBs."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from cascadegraph_runtime.storage_execution import OPERATION_SECONDS, REAP_SECONDS, SHUTDOWN_SECONDS

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Process-group accounting uses Linux /proc")
LAUNCHER = Path(__file__).with_name("uvicorn_storage_server.py")
# The documented 1 s is the storage lifespan budget, not Uvicorn's HTTP drain.
# Allow one outstanding operation, TERM/KILL reaping, and scheduling overhead.
SERVER_SHUTDOWN_SECONDS = OPERATION_SECONDS + 2 * REAP_SECONDS + SHUTDOWN_SECONDS + 0.5


def wait_until(predicate, *, seconds=5):
    deadline = time.monotonic() + seconds
    while not predicate():
        assert time.monotonic() < deadline, "Timed out waiting for isolated server synchronization"
        time.sleep(0.005)


def group_members(group):
    """Include zombies: an unreaped database child must not count as clean exit."""
    members = set()
    for path in Path("/proc").glob("[0-9]*/stat"):
        try:
            # comm can contain spaces/parentheses; fields after the final ')' start at state.
            fields = path.read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) == group:
                members.add(int(path.parent.name))
        except (FileNotFoundError, ProcessLookupError):
            pass
    return members


class IsolatedServer:
    def __init__(self, directory):
        self.directory = directory
        self.process = None

    def __enter__(self):
        # Reserve an OS-selected port until launch. Only this subprocess receives signals.
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        self.log = (self.directory / f"server-{time.monotonic_ns()}.log").open("w+")
        env = {
            **os.environ,
            "PORT": str(port),
            "CASCADEGRAPH_DB_PATH": str(self.directory / "history.sqlite3"),
            "CG_TEST_DIRECTORY": str(self.directory),
            "LLM_ENABLED": "false",
        }
        self.process = subprocess.Popen(
            [sys.executable, str(LAUNCHER)], env=env,
            stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        self.client = httpx.Client(base_url=self.url, timeout=5, trust_env=False)

        def live():
            assert self.process.poll() is None, self.logs()
            try:
                return self.client.get("/api/v1/health/live").status_code == 200
            except httpx.TransportError:
                return False

        try:
            wait_until(live, seconds=10)
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise
        return self

    def logs(self):
        self.log.flush()
        return Path(self.log.name).read_text()

    def __exit__(self, *_):
        self.client.close()
        # Even failed assertions clean up only our newly created process group.
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=SERVER_SHUTDOWN_SECONDS)
            except subprocess.TimeoutExpired:
                pass
        if group_members(self.process.pid):
            os.killpg(self.process.pid, signal.SIGKILL)
        self.process.wait(timeout=5)
        self.log.close()

    def stop(self):
        started = time.monotonic()
        self.process.send_signal(signal.SIGTERM)
        self.process.wait(timeout=SERVER_SHUTDOWN_SECONDS)
        elapsed = time.monotonic() - started
        assert elapsed < SERVER_SHUTDOWN_SECONDS, self.logs()
        assert self.process.returncode in (0, -signal.SIGTERM), self.logs()
        closed = json.loads((self.directory / "closed").read_text())
        assert closed["seconds"] < SHUTDOWN_SECONDS
        assert closed["active"] == 0
        assert closed["children"] == []
        wait_until(lambda: not group_members(self.process.pid), seconds=1)
        logs = self.logs()
        assert "Application shutdown complete." in logs
        for error in ("Traceback", "ERROR:", "Task exception was never retrieved", "Task was destroyed"):
            assert error not in logs, logs


@pytest.mark.parametrize("stage", ["commit", "committed"])
def test_sigterm_disconnected_write_and_cookie_recovery(tmp_path, stage):
    control = tmp_path / "fault"
    blocked = tmp_path / "blocked"
    with IsolatedServer(tmp_path) as server:
        baseline = server.client.post("/api/v1/analyses", json={"source_type": "sample"})
        assert baseline.status_code == 201, baseline.text
        baseline_id = baseline.json()["id"]
        cookie = server.client.cookies["cg_session"]
        control.write_text(stage)

        # First observe the actual wire contract for the same ambiguous failure.
        uncertain = server.client.post("/api/v1/analyses", json={"source_type": "sample"})
        assert uncertain.status_code == 503
        assert uncertain.json()["code"] == "STORAGE_OUTCOME_UNCERTAIN"
        assert "do not blindly replay" in uncertain.json()["error"]
        assert uncertain.headers["cache-control"] == "no-store"
        assert uncertain.json()["correlation_id"] == uncertain.headers["x-correlation-id"]
        assert "retry-after" not in uncertain.headers
        assert "set-cookie" not in uncertain.headers
        assert server.client.cookies["cg_session"] == cookie
        blocked.unlink()

        # Send a complete mutation over a real TCP connection; do not consume a response.
        body = b'{"source_type":"sample"}'
        with socket.create_connection(("127.0.0.1", int(server.url.rsplit(":", 1)[1])), timeout=5) as caller:
            caller.sendall(
                b"POST /api/v1/analyses HTTP/1.1\r\nHost: localhost\r\n"
                + f"Cookie: cg_session={cookie}\r\n".encode()
                + b"Content-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\n\r\n".encode() + body
            )
            wait_until(blocked.exists)
            # The fault marker is written inside the worker's commit, not on admission.
            worker = int((tmp_path / "worker").read_text())
            assert worker in group_members(server.process.pid), "Database worker exited before disconnect"
            caller.shutdown(socket.SHUT_RDWR)
        # SIGTERM while the disconnected request still owns a blocked write.
        assert worker in group_members(server.process.pid), "Write was not in flight at SIGTERM"
        server.stop()
        assert not Path(f"/proc/{worker}").exists()
        assert not group_members(server.process.pid)

    writes = [json.loads(line) for line in (tmp_path / "writes").read_text().splitlines()]
    assert len(writes) == 2, "A mutation was transparently retried"
    assert (tmp_path / "calls").read_text() == "invoked\ninvoked\n"
    control.unlink()
    (tmp_path / "closed").unlink()
    with IsolatedServer(tmp_path) as restarted:
        headers = {"Cookie": f"cg_session={cookie}"}
        detail = restarted.client.get(f"/api/v1/analyses/{baseline_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["id"] == baseline_id
        assert "set-cookie" not in detail.headers
        history = restarted.client.get("/api/v1/analyses", headers=headers)
        assert history.status_code == 200
        assert "set-cookie" not in history.headers
        # Interrupted-before-commit and committed-but-unacknowledged outcomes differ.
        # Neither may be inferred as rolled back merely from disconnect/timeout.
        expected = {baseline_id}
        if stage == "committed":
            expected.update(write["id"] for write in writes)
        assert {item["id"] for item in history.json()} == expected
        foreign = restarted.client.get(
            f"/api/v1/analyses/{baseline_id}", headers={"Cookie": "cg_session=foreign"},
        )
        assert foreign.status_code == 404
        assert restarted.client.get("/api/v1/health/ready").status_code == 200
        restarted.stop()
    assert (tmp_path / "calls").read_text() == "invoked\ninvoked\n"
