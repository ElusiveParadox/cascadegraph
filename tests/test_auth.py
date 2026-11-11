"""Real signed session-cookie verification, ownership separation and logout."""

import asyncio
import hashlib
import json
import logging
import sqlite3
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from cascadegraph_runtime import auth, store
from cascadegraph_runtime.app import app


@pytest.fixture(scope="module")
def signing_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key, key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def session_token(key, sub="user_AuthTestA", **claims):
    payload = {
        "sub": sub, "sid": "sess_testing", "iss": "https://test.clerk.accounts.dev",
        "azp": "http://testserver", "iat": int(time.time()), "nbf": int(time.time()) - 1,
        "exp": int(time.time()) + 300,
    }
    payload.update(claims)
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": "unit-test-key"})


def request(token=None, **headers):
    if token:
        headers["cookie"] = "__session=" + token
    return Request({
        "type": "http", "method": "GET", "path": "/api/v1/analyses", "query_string": b"",
        "scheme": "http", "server": ("testserver", 80),
        "headers": [(k.encode(), v.encode()) for k, v in {"host": "testserver", **headers}.items()],
    })


@pytest.fixture
def local_auth(monkeypatch, tmp_path, signing_key):
    monkeypatch.setenv("CASCADEGRAPH_DB_PATH", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("CLERK_SECRET_KEY", "unit-test-placeholder")

    async def public_key(self, kid):
        return signing_key[1]

    monkeypatch.setattr(auth.AuthVerifier, "_public_key", public_key)
    with TestClient(app) as client:
        yield client


def test_real_cookie_signature_and_authorized_party(local_auth, signing_key):
    client = local_auth
    key = signing_key[0]
    client.cookies.set("__session", session_token(key))
    assert client.get("/api/v1/analyses").status_code == 200
    for invalid in [
        session_token(key, exp=int(time.time()) - 60),
        session_token(key, azp="https://attacker.example"),
        session_token(key, sub="not-a-clerk-user"),
        session_token(rsa.generate_private_key(public_exponent=65537, key_size=2048)),
        "not.a.jwt",
    ]:
        client.cookies.set("__session", invalid)
        result = client.get("/api/v1/analyses")
        assert result.status_code == 401
        assert not result.headers.get("set-cookie")  # Never silently become a new guest.
        assert invalid not in result.text
    assert client.get("/api/v1/health/live").status_code == 200


def test_account_history_survives_browser_changes_and_rejects_other_owners(local_auth, signing_key):
    client = local_auth
    key = signing_key[0]
    client.cookies.set("__session", session_token(key))
    created = client.post("/api/v1/analyses", json={"source_type": "sample", "use_ai": False})
    assert created.status_code == 201, created.text
    aid = created.json()["id"]
    client.cookies.clear()
    client.cookies.set("__session", session_token(key))
    assert client.get(f"/api/v1/analyses/{aid}").status_code == 200
    client.cookies.set("__session", session_token(key, sub="user_AuthTestB"))
    assert client.get(f"/api/v1/analyses/{aid}").status_code == 404
    assert client.delete(f"/api/v1/analyses/{aid}").status_code == 404
    client.cookies.clear()
    guessed = "acct:" + hashlib.sha256(b"user_AuthTestA").hexdigest()[:58]
    client.cookies.set("cg_session", guessed)
    assert client.get(f"/api/v1/analyses/{aid}").status_code == 404
    assert all(row["id"] != aid for row in client.get("/api/v1/analyses").json())
    # A browser-supplied bearer token must not override cookie identity.
    result = client.get(f"/api/v1/analyses/{aid}",
                        headers={"authorization": "Bearer " + session_token(key)})
    assert result.status_code == 404
    client.cookies.clear()
    client.cookies.set("__session", session_token(key))
    assert client.delete(f"/api/v1/analyses/{aid}").status_code == 204


def test_logout_clears_guest_cookie_even_when_verification_fails(local_auth):
    client = local_auth
    client.cookies.set("__session", "invalid")
    client.cookies.set("cg_session", "old-browser-owner", path="/api")
    assert client.post("/api/v1/auth/sign-out", headers={"origin": "https://attacker.example"}).status_code == 403
    response = client.post("/api/v1/auth/sign-out")
    assert response.status_code == 204
    assert "cg_session=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert "Path=/api" in response.headers["set-cookie"]
    assert response.content == b""


def test_async_jwks_fetch_is_cached_bounded_and_sanitized(monkeypatch, signing_key):
    monkeypatch.setenv("CLERK_SECRET_KEY", "unit-test-placeholder")

    async def scenario():
        verifier = auth.AuthVerifier()
        await verifier.client.aclose()
        calls = []
        jwk = jwt.algorithms.RSAAlgorithm.to_jwk(signing_key[0].public_key(), as_dict=True)
        jwk["kid"] = "unit-test-key"

        def handler(req):
            calls.append(req.url)
            return httpx.Response(200, json={"keys": [jwk]})

        verifier.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            token = session_token(signing_key[0])
            owners = await asyncio.gather(*(verifier.owner(request(token)) for _ in range(8)))
            assert len(set(owners)) == 1
            assert len(calls) == 1
            assert len(owners[0]) == 63
            with pytest.raises(HTTPException) as missing:
                await verifier._public_key("unknown-kid")
            assert missing.value.status_code == 401
            assert len(calls) == 1
            assert await verifier.owner(request(authorization="Bearer " + token)) is None
        finally:
            await verifier.close()
    asyncio.run(scenario())


def test_proxy_uses_fixed_upstream_and_preserves_cookies(monkeypatch, local_auth):
    monkeypatch.setenv("REPLIT_DEPLOYMENT", "1")
    real_client = httpx.AsyncClient
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, stream=httpx.ByteStream(b'{"ok":true}'), headers=[
            ("set-cookie", "one=a; Path=/"), ("set-cookie", "two=b; Path=/"),
            ("content-type", "application/json"), ("transfer-encoding", "chunked"),
        ])

    monkeypatch.setattr(auth.httpx, "AsyncClient",
                        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    response = local_auth.get("/api/__clerk/v1/environment?test=1",
                              headers={"x-forwarded-host": "app.example, internal", "x-forwarded-proto": "https"})
    assert response.status_code == 200
    assert response.content == b'{"ok":true}'
    assert len(response.headers.get_list("set-cookie")) == 2
    assert response.headers["content-length"] == "11"
    assert "transfer-encoding" not in response.headers
    assert str(seen[0].url) == "https://frontend-api.clerk.dev/v1/environment?test=1"
    assert seen[0].headers["clerk-proxy-url"] == "https://app.example/api/__clerk"

    # Host-like and protocol-relative paths remain paths at the fixed upstream.
    for path in ("//127.0.0.1/admin", "/https://attacker.example/x", "/@attacker.example/x"):
        result = local_auth.get("/api/__clerk" + path + "?url=https://attacker.example")
        assert result.status_code == 200
        assert seen[-1].url.scheme == "https"
        assert seen[-1].url.host == "frontend-api.clerk.dev"
        assert seen[-1].url.port is None


def test_account_resolver_rejects_arbitrary_owner(local_auth):
    with pytest.raises(ValueError):
        store.resolve_account("guest-id")


def test_application_api_rejects_and_never_echoes_passwords(local_auth, caplog):
    caplog.set_level(logging.INFO)
    canary = "test-only-password-canary-not-a-real-credential"
    for field in ("password", "password_hash", "passwordDigest"):
        result = local_auth.post("/api/v1/analyses", json={
            "source_type": "sample", "use_ai": False, field: canary,
        })
        assert result.status_code == 422
        assert canary not in result.text
    assert canary not in caplog.text
    assert local_auth.get("/api/v1/analyses").json() == []
    assert canary not in database_dump()


def database_dump():
    """Inspect every local-test table, not just the current owner's history."""
    with sqlite3.connect(store.database_path()) as db:
        return "\n".join(db.iterdump())


@pytest.mark.parametrize("outcome", ["complete", "invalid", "expired", "transport"])
def test_recovery_proxy_keeps_credentials_transient(monkeypatch, local_auth, caplog, outcome):
    """Exercise production proxy wiring locally; never contact a real provider."""
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("REPLIT_DEPLOYMENT", "1")
    # Populate an isolated test store before proving the proxy leaves it untouched.
    assert local_auth.get("/api/v1/analyses").status_code == 200
    before = database_dump()
    canary = "test-only-reset-password-canary-not-a-real-credential"
    body = ("code=424242&password=" + canary).encode()
    real_client = httpx.AsyncClient
    seen = []

    def handler(req):
        seen.append(req)
        assert req.method == "POST"
        assert req.url.host == "frontend-api.clerk.dev"
        assert req.content == body
        if outcome == "transport":
            # Even an exception containing sensitive bytes must not be logged.
            raise httpx.ReadError(canary, request=req)
        if outcome == "complete":
            status, payload = 200, {"response": {"status": "complete"}}
        else:
            code = "form_code_incorrect" if outcome == "invalid" else "verification_expired"
            status, payload = 422, {"errors": [{"code": code, "message": "Request a new code"}]}
        # The proxy consumes wire bytes; json= pre-consumes a mock response.
        return httpx.Response(status, stream=httpx.ByteStream(json.dumps(payload).encode()),
                              headers={"content-type": "application/json"})

    monkeypatch.setattr(auth.httpx, "AsyncClient",
                        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    response = local_auth.post(
        "/api/__clerk/v1/client/sign_ins/test-only/reset_password",
        content=body, headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert len(seen) == 1  # Password-changing requests are never replayed.
    assert response.status_code == (502 if outcome == "transport" else 200 if outcome == "complete" else 422)
    assert response.headers["cache-control"] == "no-store"
    assert canary not in response.text
    assert canary not in str(response.headers)
    assert canary not in caplog.text
    assert before == database_dump()


def test_new_session_after_recovery_retains_only_original_account(local_auth, signing_key):
    """Signed local fixtures verify ownership, not Clerk's password reset itself."""
    key = signing_key[0]
    local_auth.cookies.set("__session", session_token(key, sid="sess_before_recovery"))
    created = local_auth.post("/api/v1/analyses", json={"source_type": "sample", "use_ai": False})
    assert created.status_code == 201
    aid = created.json()["id"]
    local_auth.cookies.clear()
    local_auth.cookies.set("__session", session_token(key, sid="sess_after_recovery"))
    assert local_auth.get(f"/api/v1/analyses/{aid}").status_code == 200
    assert any(row["id"] == aid for row in local_auth.get("/api/v1/analyses").json())
    local_auth.cookies.set("__session", session_token(key, sub="user_OtherRecovery", sid="sess_other"))
    assert local_auth.get(f"/api/v1/analyses/{aid}").status_code == 404
    local_auth.cookies.set("__session", session_token(key, sid="sess_after_recovery",
                                                    exp=int(time.time()) - 60))
    expired = local_auth.get(f"/api/v1/analyses/{aid}")
    assert expired.status_code == 401
    assert not expired.headers.get("set-cookie")
    local_auth.cookies.clear()
    assert local_auth.get(f"/api/v1/analyses/{aid}").status_code == 404
