import io
import zipfile

from fastapi.testclient import TestClient

from cascadegraph_runtime.app import app
from cascadegraph_runtime.security import MAX_BODY


def create(client):
    response = client.post("/api/v1/analyses", json={"source_type": "sample"})
    assert response.status_code == 201, response.text
    return response.json()


def test_complete_flow_and_ownership(client):
    a = create(client)
    assert len(a["nodes"]) == 3
    assert client.get("/api/v1/analyses").json()[0]["id"] == a["id"]
    r = client.post(f"/api/v1/analyses/{a['id']}/simulations", json={
        "mode": "intermittent", "requests": 10, "candidate_attempts": 1
    })
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["candidate"]["amplification"] <= s["baseline"]["amplification"]
    assert client.get(f"/api/v1/simulations/{s['id']}").json() == s
    report = client.get(f"/api/v1/analyses/{a['id']}/report").json()
    assert len(report["simulations"]) == 1
    with TestClient(app) as other:
        assert other.get(f"/api/v1/analyses/{a['id']}").status_code == 404
        assert other.get(f"/api/v1/simulations/{s['id']}").status_code == 404
        assert other.delete(f"/api/v1/analyses/{a['id']}").status_code == 404
    assert client.delete(f"/api/v1/analyses/{a['id']}").status_code == 204
    assert client.get(f"/api/v1/simulations/{s['id']}").status_code == 404


def test_confirm_preserves_source_and_snapshot(client):
    a = create(client)
    p = next(p for p in a["policies"] if p["framework"] == "tenacity")
    response = client.patch(f"/api/v1/analyses/{a['id']}/policies/{p['id']}",
                            json={"max_total_attempts": 1, "note": "Confirmed test alternative"})
    assert response.status_code == 200
    updated = next(x for x in response.json()["policies"] if x["id"] == p["id"])
    assert updated["source_value"] == 3 and updated["max_total_attempts"] == 1
    assert updated["confirmed"]
    edge = a["edges"][0]
    assert client.post(f"/api/v1/analyses/{a['id']}/edges/{edge['id']}/confirm",
                       json={"note": "Reviewed static endpoint"}).json()["edges"][0]["confirmed"]


def test_archive_and_invalid_requests(client):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("compose.yml", "services:\n  a: {}\n")
    r = client.post("/api/v1/analyses/archive", files={"file": ("sample.zip", stream.getvalue(), "application/zip")})
    assert r.status_code == 201
    assert r.json()["status"] == "partial"
    r = client.post("/api/v1/analyses", json={"source_type": "github", "repository_url": "http://169.254.169.254"})
    assert r.status_code == 422
    assert client.post("/api/v1/analyses", json={"source_type": "sample"},
                       headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/v1/analyses/archive", files={"file": ("x.zip", b"bad")}).status_code == 422


def test_review_refreshes_findings_but_preserves_old_run(client):
    a = create(client)
    policy = next(p for p in a["policies"] if p["symbol"] == "call_order")
    before = client.post(f"/api/v1/analyses/{a['id']}/simulations",
                         json={"mode": "healthy", "requests": 2}).json()
    for attempts in (2, 4):
        response = client.patch(f"/api/v1/analyses/{a['id']}/policies/{policy['id']}",
                                json={"max_total_attempts": attempts, "note": "Verified reviewer correction"})
        assert response.status_code == 200
        report = client.get(f"/api/v1/analyses/{a['id']}/report").json()
        details = [f["detail"] for f in report["analysis"]["findings"]
                   if f["title"] == "Multiple attempts configured" and "call_order " in f["detail"]]
        assert not details if attempts == 2 else "4 total attempts" in details[0]
        saved = next(p for p in report["analysis"]["policies"] if p["id"] == policy["id"])
        assert saved["source_value"] == 3
    previous = client.get(f"/api/v1/simulations/{before['id']}").json()
    assert next(p for p in previous["policies"] if p["id"] == policy["id"])["max_total_attempts"] == 3


def test_finite_inputs_and_limits(client):
    a = create(client)
    assert client.post(f"/api/v1/analyses/{a['id']}/simulations",
                       json={"requests": 501}).status_code == 422
    assert client.post(f"/api/v1/analyses/{a['id']}/simulations",
                       content='{"arrival_rate":NaN}', headers={"Content-Type": "application/json"}).status_code == 422
    assert client.post("/api/v1/analyses", content=b"", headers={"Content-Length": str(MAX_BODY + 1)}).status_code == 413


def test_status_and_cookie(client):
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    assert "HttpOnly" in r.headers["set-cookie"]
    assert r.headers["cache-control"] == "no-store"
    assert client.get("/api/healthz").json() == {"status": "ok"}
    assert client.get("/api/v1/health/ready").status_code == 200


def test_rate_limit(client):
    for _ in range(20):
        assert client.post("/api/v1/analyses", json={"source_type": "bad"}).status_code == 422
    assert client.post("/api/v1/analyses", json={"source_type": "bad"}).status_code == 429
