"""Real signed session-cookie verification, ownership separation and logout."""

import asyncio
import hashlib
import json
import logging
import sqlite3
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace

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


class ControlledStream(httpx.AsyncByteStream):
    """Raw provider bytes with observable entry/cleanup and no real network."""

    def __init__(self, chunks=(), *, stalled=False, trickle=False):
        self.chunks = chunks
        self.stalled = stalled
        self.trickle = trickle
        self.entered = asyncio.Event()
        self.closed = False
        self.reads = 0

    async def __aiter__(self):
        self.entered.set()
        for chunk in self.chunks:
            self.reads += 1
            yield chunk
        if self.stalled:
            await asyncio.Event().wait()
        while self.trickle:
            await asyncio.sleep(0.005)
            self.reads += 1
            yield b" "

    async def aclose(self):
        self.closed = True


@asynccontextmanager
async def mocked_verifier(monkeypatch, handler):
    monkeypatch.setenv("CLERK_SECRET_KEY", "unit-test-placeholder")
    verifier = auth.AuthVerifier()
    await verifier.client.aclose()
    verifier.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        yield verifier
    finally:
        await verifier.close()
    assert verifier.client.is_closed


def jwks_response(signing_key):
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(signing_key[0].public_key(), as_dict=True)
    jwk["kid"] = "unit-test-key"
    return httpx.Response(200, json={"keys": [jwk]})


@pytest.mark.parametrize("stage", ["headers", "body"])
def test_jwks_stalls_have_total_deadline_and_release_lock(monkeypatch, signing_key, stage):
    monkeypatch.setattr(auth, "JWKS_DEADLINE", 0.05)
    monkeypatch.setattr(auth, "JWKS_FAILURE_COOLDOWN", 60)

    async def scenario():
        stream = ControlledStream(trickle=True)
        calls = 0
        recovered = False

        async def handler(req):
            nonlocal calls
            calls += 1
            if recovered:
                return jwks_response(signing_key)
            if stage == "headers":
                await asyncio.Event().wait()
            return httpx.Response(200, stream=stream)

        async with mocked_verifier(monkeypatch, handler) as verifier:
            start = time.monotonic()
            with pytest.raises(HTTPException) as error:
                await asyncio.wait_for(verifier.owner(request(session_token(signing_key[0]))), 0.8)
            assert time.monotonic() - start < 0.8
            assert error.value.status_code == 503
            assert error.value.detail == "Sign-in verification is temporarily unavailable"
            assert not verifier.lock.locked()
            assert verifier.keys == {}
            if stage == "body":
                assert stream.reads > 1  # Active trickle must not reset the whole-operation budget.
                assert stream.closed
            with pytest.raises(HTTPException) as cooled:
                await verifier._public_key("unit-test-key")
            assert cooled.value.status_code == 503
            assert calls == 1
            verifier.failed_until = 0  # Advance only this verifier, never the process clock.
            recovered = True
            assert await verifier.owner(request(session_token(signing_key[0]))) == (
                "acct:" + hashlib.sha256(b"user_AuthTestA").hexdigest()[:58]
            )
    asyncio.run(scenario())


def test_jwks_failure_cooldown_covers_already_queued_callers(monkeypatch, signing_key, caplog):
    monkeypatch.setattr(auth, "JWKS_FAILURE_COOLDOWN", 60)
    caplog.set_level(logging.INFO)
    canary = "test-only-upstream-secret-canary"

    async def scenario():
        entered, fail = asyncio.Event(), asyncio.Event()
        calls = 0

        async def handler(req):
            nonlocal calls
            calls += 1
            entered.set()
            await fail.wait()
            raise httpx.ReadError(canary, request=req)

        async with mocked_verifier(monkeypatch, handler) as verifier:
            token = session_token(signing_key[0])
            first = asyncio.create_task(verifier.owner(request(token)))
            await asyncio.wait_for(entered.wait(), 0.8)
            queued = [asyncio.create_task(verifier.owner(request(token))) for _ in range(7)]
            await asyncio.sleep(0)  # All seven enter lock acquisition before failure.
            fail.set()
            results = await asyncio.wait_for(asyncio.gather(first, *queued, return_exceptions=True), 0.8)
            assert all(isinstance(result, HTTPException) and result.status_code == 503 for result in results)
            assert all(result.detail == "Sign-in verification is temporarily unavailable" for result in results)
            assert calls == 1
            assert not verifier.lock.locked()
            assert canary not in caplog.text
    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["fetch", "admission"])
def test_jwks_cancellation_propagates_without_poisoning_lock(monkeypatch, signing_key, stage):
    async def scenario():
        stream = ControlledStream(stalled=True)
        calls = 0
        recovered = False

        def handler(req):
            nonlocal calls
            calls += 1
            if recovered:
                return jwks_response(signing_key)
            return httpx.Response(200, stream=stream)

        async with mocked_verifier(monkeypatch, handler) as verifier:
            if stage == "admission":
                await verifier.lock.acquire()
            task = asyncio.create_task(verifier._public_key("unit-test-key"))
            try:
                if stage == "fetch":
                    await asyncio.wait_for(stream.entered.wait(), 0.8)
                else:
                    await asyncio.sleep(0)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert verifier.failed_until == 0
                if stage == "admission":
                    assert verifier.lock.locked()  # The cancelled waiter did not release someone else's lock.
                    assert calls == 0
                else:
                    assert stream.closed
                    assert not verifier.lock.locked()
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                if verifier.lock.locked():
                    verifier.lock.release()
            recovered = True
            assert await verifier._public_key("unit-test-key") == signing_key[1]
    asyncio.run(scenario())


def test_jwks_admission_is_bounded_and_cached_owner_survives_failure(monkeypatch, signing_key):
    monkeypatch.setattr(auth, "AUTH_ADMISSION_TIMEOUT", 0.03)

    async def scenario():
        def forbidden(req):
            pytest.fail("Cached identity and lock saturation must not contact the provider")

        async with mocked_verifier(monkeypatch, forbidden) as verifier:
            await verifier.lock.acquire()
            try:
                with pytest.raises(HTTPException) as error:
                    await asyncio.wait_for(verifier._public_key("unknown"), 0.8)
                assert error.value.status_code == 503
                assert error.value.detail == "Sign-in verification is busy; retry shortly"
                assert verifier.lock.locked()
                verifier.keys = {"unit-test-key": signing_key[1]}
                verifier.fetched_at = time.monotonic()
                verifier.failed_until = time.monotonic() + 60
                owner = await verifier.owner(request(session_token(signing_key[0])))
                assert owner == "acct:" + hashlib.sha256(b"user_AuthTestA").hexdigest()[:58]
                assert await verifier.owner(request(authorization="Bearer " + session_token(signing_key[0]))) is None
            finally:
                verifier.lock.release()
    asyncio.run(scenario())


def proxy_request(verifier, receive=None):
    return Request({
        "type": "http", "method": "POST", "path": "/api/__clerk/v1/client/sign_ins",
        "query_string": b"", "scheme": "https", "server": ("app.example", 443),
        "headers": [(b"host", b"app.example")],
        "app": SimpleNamespace(state=SimpleNamespace(auth=verifier)),
    }, receive=receive or empty_body)


async def empty_body():
    return {"type": "http.request", "body": b"", "more_body": False}


async def assert_slots_available(verifier, count=8):
    # Public semaphore operations prove neither leaks nor over-release.
    for _ in range(count):
        await asyncio.wait_for(verifier.proxy_slots.acquire(), 0.8)
    assert verifier.proxy_slots.locked()
    for _ in range(count):
        verifier.proxy_slots.release()


@pytest.mark.parametrize("failure", ["oversized", "trickle", "transport"])
def test_proxy_stream_failures_are_bounded_closed_and_recover(monkeypatch, failure, caplog):
    monkeypatch.setenv("REPLIT_DEPLOYMENT", "1")
    monkeypatch.setenv("CLERK_SECRET_KEY", "unit-test-placeholder")
    monkeypatch.setattr(auth, "PROXY_DEADLINE", 0.06)
    monkeypatch.setattr(auth, "PROXY_RESPONSE_LIMIT", 32)
    caplog.set_level(logging.INFO)

    async def scenario():
        verifier = auth.AuthVerifier()
        real_client = httpx.AsyncClient
        stream = ControlledStream([b"a" * 16, b"b" * 17, b"must-not-read"], trickle=failure == "trickle")
        if failure != "oversized":
            stream.chunks = ()
        calls = []

        def handler(req):
            calls.append(req)
            if failure == "transport" and len(calls) == 1:
                raise httpx.ReadError("test-only-sensitive-upstream-detail", request=req)
            return httpx.Response(200, stream=stream if len(calls) == 1 else httpx.ByteStream(b"ok"))

        monkeypatch.setattr(auth.httpx, "AsyncClient",
                            lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
        try:
            result = await asyncio.wait_for(auth.clerk_proxy(proxy_request(verifier)), 0.8)
            assert result.status_code == (504 if failure == "trickle" else 502)
            assert result.body == b""
            assert not result.headers.get("set-cookie")
            assert len(calls) == 1  # No replay of credential-bearing POSTs.
            if failure != "transport":
                assert stream.closed
                if failure == "oversized":
                    assert stream.reads == 2
                else:
                    assert stream.reads > 1
            assert "test-only-sensitive-upstream-detail" not in caplog.text
            await assert_slots_available(verifier)
            recovered = await auth.clerk_proxy(proxy_request(verifier))
            assert recovered.status_code == 200
            assert recovered.body == b"ok"
            await assert_slots_available(verifier)
        finally:
            await verifier.close()
    asyncio.run(scenario())


def test_proxy_saturation_keeps_liveness_working_and_releases_cancelled_slot(monkeypatch):
    monkeypatch.setenv("REPLIT_DEPLOYMENT", "1")
    monkeypatch.setenv("CLERK_SECRET_KEY", "unit-test-placeholder")
    monkeypatch.setattr(auth, "AUTH_ADMISSION_TIMEOUT", 0.03)

    async def scenario():
        verifier = auth.AuthVerifier()
        monkeypatch.setattr(app.state, "auth", verifier, raising=False)
        real_client = httpx.AsyncClient
        streams = []

        def handler(req):
            stream = ControlledStream(stalled=True)
            streams.append(stream)
            return httpx.Response(200, stream=stream)

        monkeypatch.setattr(auth.httpx, "AsyncClient",
                            lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
        tasks = []
        try:
            tasks = [asyncio.create_task(auth.clerk_proxy(proxy_request(verifier))) for _ in range(8)]
            async with real_client(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                for _ in range(100):
                    if len(streams) == 8 and all(s.entered.is_set() for s in streams):
                        break
                    await asyncio.sleep(0.001)
                assert len(streams) == 8
                assert all(s.entered.is_set() for s in streams)
                result = await asyncio.wait_for(client.get("/api/__clerk/v1/environment"), 0.8)
                assert result.status_code == 503
                assert result.content == b""
                assert result.headers["cache-control"] == "no-store"
                assert not result.headers.get("set-cookie")
                assert len(streams) == 8
                live = await asyncio.wait_for(client.get("/api/v1/health/live"), 0.8)
                assert live.status_code == 200
                assert live.json() == {"status": "ok"}
                assert not live.headers.get("set-cookie")
                tasks[0].cancel()
                with pytest.raises(asyncio.CancelledError):
                    await tasks[0]
                assert streams[0].closed
                # The recovered slot really admits another request, not just a counter inspection.
                monkeypatch.setattr(auth.httpx, "AsyncClient", lambda **kwargs: real_client(
                    transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=httpx.ByteStream(b"ok"))),
                    **kwargs,
                ))
                assert (await client.get("/api/__clerk/v1/environment")).content == b"ok"
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            assert all(s.closed for s in streams)
            await assert_slots_available(verifier)
            await verifier.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["admission", "upload", "response"])
def test_proxy_cancellation_never_leaks_or_over_releases_admission(monkeypatch, stage):
    monkeypatch.setenv("REPLIT_DEPLOYMENT", "1")
    monkeypatch.setenv("CLERK_SECRET_KEY", "unit-test-placeholder")

    async def scenario():
        verifier = auth.AuthVerifier()
        real_client = httpx.AsyncClient
        stream = ControlledStream(stalled=True)
        upload_entered = asyncio.Event()
        calls = 0

        def handler(req):
            nonlocal calls
            calls += 1
            return httpx.Response(200, stream=stream)

        async def slow_upload():
            upload_entered.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(auth.httpx, "AsyncClient",
                            lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
        if stage == "admission":
            for _ in range(8):
                await verifier.proxy_slots.acquire()
        task = asyncio.create_task(auth.clerk_proxy(proxy_request(
            verifier, slow_upload if stage == "upload" else None,
        )))
        try:
            if stage == "response":
                await asyncio.wait_for(stream.entered.wait(), 0.8)
            elif stage == "upload":
                await asyncio.wait_for(upload_entered.wait(), 0.8)
            else:
                await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            if stage == "admission":
                assert verifier.proxy_slots.locked()
            if stage == "response":
                assert stream.closed
            assert calls == (1 if stage == "response" else 0)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if stage == "admission":
                for _ in range(8):
                    verifier.proxy_slots.release()
            await assert_slots_available(verifier)
            await verifier.close()
    asyncio.run(scenario())


def test_jwks_outage_never_reassigns_history_and_liveness_bypasses_it(monkeypatch, tmp_path, signing_key):
    monkeypatch.setenv("CASCADEGRAPH_DB_PATH", str(tmp_path / "outage.sqlite3"))
    monkeypatch.setenv("CLERK_SECRET_KEY", "unit-test-placeholder")
    monkeypatch.setattr(auth, "JWKS_DEADLINE", 0.05)
    monkeypatch.setattr(auth, "JWKS_FAILURE_COOLDOWN", 60)

    async def scenario():
        failing = False
        entered = asyncio.Event()
        calls = 0

        async def handler(req):
            nonlocal calls
            calls += 1
            if failing:
                entered.set()
                await asyncio.Event().wait()
            return jwks_response(signing_key)

        async with app.router.lifespan_context(app):
            verifier = app.state.auth
            await verifier.client.aclose()
            verifier.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                token = session_token(signing_key[0])
                client.cookies.set("__session", token)
                created = await client.post("/api/v1/analyses", json={"source_type": "sample", "use_ai": False})
                assert created.status_code == 201
                aid = created.json()["id"]
                client.cookies.set("cg_session", "existing-browser-cookie", path="/api")
                before_cookies = dict(client.cookies)
                before = database_dump()
                failing = True
                verifier.fetched_at = float("-inf")
                pending = asyncio.create_task(client.get(f"/api/v1/analyses/{aid}"))
                try:
                    await asyncio.wait_for(entered.wait(), 0.8)
                    live = await asyncio.wait_for(client.get("/api/v1/health/live"), 0.8)
                    assert live.status_code == 200
                    assert not live.headers.get("set-cookie")
                    failed = await asyncio.wait_for(pending, 0.8)
                    for result in (failed, await client.get("/api/v1/analyses")):
                        assert result.status_code == 503
                        assert result.json() == {"error": "Sign-in verification is temporarily unavailable"}
                        assert result.headers["cache-control"] == "no-store"
                        assert not result.headers.get("set-cookie")
                        assert token not in result.text
                    assert calls == 2  # Initial success and one stalled refresh, never a retry storm.
                    assert before == database_dump()
                    assert dict(client.cookies) == before_cookies
                    assert not verifier.lock.locked()
                finally:
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)
                failing = False
                verifier.failed_until = 0
                assert (await client.get(f"/api/v1/analyses/{aid}")).status_code == 200
                client.cookies.set("__session", session_token(signing_key[0], sub="user_OutageOther"))
                assert (await client.get(f"/api/v1/analyses/{aid}")).status_code == 404
                client.cookies.clear()
                assert (await client.get(f"/api/v1/analyses/{aid}", headers={
                    "authorization": "Bearer " + token, "x-user-id": "user_AuthTestA",
                })).status_code == 404
                client.cookies.clear()
                client.cookies.set("__session", token)
                assert (await client.get(f"/api/v1/analyses/{aid}")).status_code == 200
    asyncio.run(scenario())
