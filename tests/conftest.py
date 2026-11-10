import pytest
from fastapi.testclient import TestClient

from cascadegraph_runtime.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CASCADEGRAPH_DB_PATH", str(tmp_path / "test.sqlite3"))
    # Fresh middleware state isolates rate-limit tests.
    app.middleware_stack = None
    with TestClient(app) as c:
        yield c
