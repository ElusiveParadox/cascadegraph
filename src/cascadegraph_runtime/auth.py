"""Cookie-only Clerk verification and the managed production Frontend API proxy."""

import asyncio
import hashlib
import os
import re
import time

import httpx
import jwt
from clerk_backend_api.security import authenticate_request
from clerk_backend_api.security.types import AuthenticateRequestOptions
from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException, Request
from starlette.responses import Response

PROXY_PATH = "/api/__clerk"
FAPI = "https://frontend-api.clerk.dev"
JWKS_DEADLINE = 3
AUTH_ADMISSION_TIMEOUT = 1
JWKS_FAILURE_COOLDOWN = 2
PROXY_DEADLINE = 30
PROXY_RESPONSE_LIMIT = 20 * 1024 * 1024
HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
               "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length"}


def public_origin(request):
    host = request.headers.get("x-forwarded-host", request.headers.get("host", "")).split(",")[0].strip()
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    if proto not in {"http", "https"} or not re.fullmatch(r"[A-Za-z0-9.:\-\[\]]+", host):
        raise HTTPException(400, "Invalid public origin")
    return f"{proto}://{host}"


class AuthVerifier:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=3, limits=httpx.Limits(max_connections=4))
        self.keys = {}
        self.fetched_at = float("-inf")
        self.failed_until = 0
        self.lock = asyncio.Lock()
        self.proxy_slots = asyncio.Semaphore(8)

    async def close(self):
        await self.client.aclose()

    async def _public_key(self, kid):
        now = time.monotonic()
        if kid in self.keys and now - self.fetched_at < 300:
            return self.keys[kid]
        if now < self.failed_until:
            raise HTTPException(503, "Sign-in verification is temporarily unavailable")
        try:
            await asyncio.wait_for(self.lock.acquire(), timeout=AUTH_ADMISSION_TIMEOUT)
        except TimeoutError:
            raise HTTPException(503, "Sign-in verification is busy; retry shortly") from None
        try:
            now = time.monotonic()
            # Callers queued before a failed fetch must observe its cooldown too.
            if kid in self.keys and now - self.fetched_at < 300:
                return self.keys[kid]
            if now < self.failed_until:
                raise HTTPException(503, "Sign-in verification is temporarily unavailable")
            # Unknown key IDs cannot force unbounded remote fetches.
            if now - self.fetched_at >= 30:
                try:
                    # HTTPX timeouts bound individual I/O waits, not a response
                    # that keeps trickling bytes indefinitely.
                    async with asyncio.timeout(JWKS_DEADLINE):
                        response = await self.client.get(
                            "https://api.clerk.com/v1/jwks",
                            headers={"Authorization": f"Bearer {os.environ['CLERK_SECRET_KEY']}"},
                        )
                    response.raise_for_status()
                    keys = {}
                    for item in response.json()["keys"]:
                        if item.get("kty") == "RSA" and isinstance(item.get("kid"), str):
                            key = jwt.algorithms.RSAAlgorithm.from_jwk(item)
                            keys[item["kid"]] = key.public_bytes(
                                serialization.Encoding.PEM,
                                serialization.PublicFormat.SubjectPublicKeyInfo,
                            ).decode()
                    if not keys:
                        raise ValueError("No verification keys")
                    self.keys, self.fetched_at = keys, now
                except (TimeoutError, httpx.HTTPError, jwt.PyJWTError, ValueError, KeyError, TypeError):
                    self.failed_until = time.monotonic() + JWKS_FAILURE_COOLDOWN
                    raise HTTPException(503, "Sign-in verification is temporarily unavailable") from None
            if kid not in self.keys:
                raise HTTPException(401, "Sign in again to continue")
            return self.keys[kid]
        finally:
            self.lock.release()

    async def owner(self, request):
        token = request.cookies.get("__session")
        if not token:
            return None
        if not os.getenv("CLERK_SECRET_KEY"):
            raise HTTPException(503, "Sign-in is not configured on this server")
        try:
            if len(token) > 8192:
                raise ValueError("Oversized token")
            kid = jwt.get_unverified_header(token).get("kid")
            if not isinstance(kid, str) or len(kid) > 256:
                raise ValueError("Invalid key ID")
        except (jwt.InvalidTokenError, ValueError):
            raise HTTPException(401, "Sign in again to continue") from None
        pem = await self._public_key(kid)
        # Explicitly ignore Authorization and all client-supplied identity headers.
        # SDK verification is networkless: our bounded async fetch owns JWKS I/O.
        state = authenticate_request(
            httpx.Request("GET", str(request.url), cookies={"__session": token}),
            AuthenticateRequestOptions(jwt_key=pem, authorized_parties=[public_origin(request)],
                                       accepts_token=["session_token"]),
        )
        subject = (state.payload or {}).get("sub")
        if not state.is_signed_in or not isinstance(subject, str) or not re.fullmatch(r"user_[A-Za-z0-9]{1,100}", subject):
            raise HTTPException(401, "Sign in again to continue")
        return "acct:" + hashlib.sha256(subject.encode()).hexdigest()[:58]


async def clerk_proxy(request: Request):
    # Mirrors the canonical Express proxy on the actual Python API service.
    # Development Clerk uses its Frontend API directly, never this proxy.
    if os.getenv("REPLIT_DEPLOYMENT") != "1" or not os.getenv("CLERK_SECRET_KEY"):
        return Response(status_code=404)
    try:
        async with asyncio.timeout(PROXY_DEADLINE):
            try:
                await asyncio.wait_for(request.app.state.auth.proxy_slots.acquire(), timeout=AUTH_ADMISSION_TIMEOUT)
            except TimeoutError:
                return Response(status_code=503)
            try:
                return await _proxy_bytes(request)
            finally:
                request.app.state.auth.proxy_slots.release()
    except TimeoutError:
        return Response(status_code=504)


async def _proxy_bytes(request):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 10 * 1024 * 1024:
            return Response(status_code=413)
    tail = request.url.path[len(PROXY_PATH):]
    # Copy path/query components only. Never join an untrusted URL string:
    # //host, @host, backslashes and encoded slashes cannot replace the origin.
    upstream = httpx.URL(FAPI).copy_with(path="/" + tail.lstrip("/"),
                                        query=request.url.query.encode("utf-8"))
    if upstream.scheme != "https" or upstream.host != "frontend-api.clerk.dev" or upstream.port not in {None, 443}:
        return Response(status_code=400)
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in HOP_HEADERS | {"clerk-secret-key", "clerk-proxy-url", "accept-encoding"}}
    headers.update({
        "Clerk-Proxy-Url": public_origin(request) + PROXY_PATH,
        "Clerk-Secret-Key": os.environ["CLERK_SECRET_KEY"],
        "Accept-Encoding": "identity",
        "X-Forwarded-For": request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else ""),
    })
    try:
        # Constant upstream: neither path nor host headers may select another server.
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            async with client.stream(request.method, upstream, headers=headers, content=bytes(body)) as remote:
                payload = bytearray()
                async for chunk in remote.aiter_raw():
                    payload.extend(chunk)
                    if len(payload) > PROXY_RESPONSE_LIMIT:
                        return Response(status_code=502)
                response = Response(bytes(payload), status_code=remote.status_code)
                response.raw_headers = [
                    (k, v) for k, v in remote.headers.raw if k.decode().lower() not in HOP_HEADERS
                ]
                # Preserve duplicate Set-Cookie headers and the raw encoded body.
                if remote.status_code >= 200 and remote.status_code not in {204, 304}:
                    response.headers["content-length"] = str(len(payload))
                return response
    except httpx.HTTPError:
        return Response(status_code=502)
