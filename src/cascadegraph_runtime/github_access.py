"""GitHub App device authorization with a server-only encrypted credential vault.

No engineering connector, PAT, installation token or refresh token is used.
Restart/replica changes preserve unexpired connections; never silently fall back.
"""

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from dataclasses import asdict, dataclass, field
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from . import credential_vault as vault
from . import store
from .repository import public_host
from .security import InputError

MAX_SESSIONS = 1000
SESSION_TTL = 8 * 3600


@dataclass
class Device:
    code: str = field(repr=False)
    user_code: str
    expires: float
    interval: int
    client_id: str
    slug: str
    next_poll: float = 0


@dataclass
class Identity:
    token: str = field(repr=False)
    owner: str
    login: str
    expires: float
    client_id: str
    slug: str


class Pool:
    """No credential cache; every replica reads the authoritative vault."""

    def __init__(self, kind, model):
        self.kind, self.model = kind, model

    def get(self, handle):
        data = vault.fetch(self.kind, handle)
        return self.model(**data) if data else None

    def __getitem__(self, handle):
        value = self.get(handle)
        if value is None:
            raise KeyError(handle)
        return value

    def __setitem__(self, handle, value):
        vault.put(self.kind, handle, asdict(value))

    def __contains__(self, handle):
        return self.get(handle) is not None

    def __len__(self):
        return vault.count(self.kind)

    def pop(self, handle, default=None):
        vault.remove(self.kind, handle)
        return default


devices = Pool("device", Device)
identities = Pool("identity", Identity)


def configuration(client_id: str = "", slug: str = ""):
    client_id = client_id.strip() or os.getenv("GITHUB_APP_CLIENT_ID", "")
    slug = slug.strip() or os.getenv("GITHUB_APP_SLUG", "")
    if not re.fullmatch(r"Iv[0-9A-Za-z_.-]{4,100}", client_id) or not re.fullmatch(r"[a-z0-9-]{1,100}", slug):
        return None
    if not os.getenv("SESSION_SECRET"):
        return None
    return client_id, slug


def prune():
    vault.prune()


def identity(handle: str) -> Identity | None:
    return identities.get(handle) if len(handle) <= 64 else None


def status(handle: str):
    config = configuration()
    user = identity(handle)
    if user:
        config = user.client_id, user.slug
    return {
        "configured": bool(config), "connected": bool(user), "login": user.login if user else "",
        "setup_available": bool(os.getenv("SESSION_SECRET")),
        "install_url": f"https://github.com/apps/{config[1]}/installations/new" if config else "",
        "revoke_url": "https://github.com/settings/apps/authorizations",
    }


async def provider(method: str, path: str, *, token: str = "", data=None):
    """Fixed provider destinations, bounded JSON, no redirect or raw errors."""
    host = "github.com" if path.startswith("/login/") else "api.github.com"
    if host == "api.github.com":
        await public_host(host)
    headers = {"Accept": "application/json", "User-Agent": "CascadeGraph"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
            async with client.stream(method, f"https://{host}{path}", headers=headers, data=data) as response:
                if response.status_code == 401:
                    # Invalidate this credential on every replica, not just here.
                    vault.revoke(token)
                    raise HTTPException(401, "GitHub authorization expired or was revoked. Reconnect or upload files.")
                if response.status_code in {403, 404}:
                    raise HTTPException(403, "GitHub access denied. Check selected repositories, organization approval or SSO.")
                if response.status_code == 429:
                    raise HTTPException(429, "GitHub rate limit reached. Retry later or upload files.")
                if response.status_code != 200:
                    raise HTTPException(502, "GitHub authorization service unavailable. Retry or upload files.")
                raw = bytearray()
                async for chunk in response.aiter_bytes(65536):
                    raw.extend(chunk)
                    if len(raw) > 1024 * 1024:
                        raise HTTPException(502, "GitHub response exceeds the authorization limit.")
                return json.loads(raw)
    except (httpx.HTTPError, TimeoutError, ValueError) as exc:
        raise HTTPException(502, "GitHub authorization service unavailable. Retry or upload files.") from exc


async def start_device(old_handle: str, client_id: str = "", slug: str = ""):
    config = configuration(client_id, slug)
    if not config:
        raise HTTPException(422, "Enter a valid GitHub App client ID and slug with Device flow enabled, or upload files.")
    prune()
    devices.pop(old_handle, None)
    if len(devices) >= MAX_SESSIONS or len(identities) >= MAX_SESSIONS:
        raise HTTPException(429, "GitHub connection capacity reached. Try later.")
    result = await provider("POST", "/login/device/code", data={"client_id": config[0]})
    try:
        code, user_code = result["device_code"], result["user_code"]
        if not isinstance(code, str) or len(code) > 1024 or not re.fullmatch(r"[A-Za-z0-9-]{4,32}", user_code):
            raise ValueError()
        interval = max(5, min(60, int(result.get("interval", 5))))
        expires_in = max(1, min(900, int(result["expires_in"])))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(502, "GitHub returned an invalid device authorization.") from exc
    handle = secrets.token_urlsafe(32)
    devices[handle] = Device(code, user_code, time.time() + expires_in, interval, *config)
    return handle, {"status": "pending", "user_code": user_code,
                    "verification_uri": "https://github.com/login/device", "interval": interval,
                    "expires_in": expires_in}


async def poll_device(handle: str):
    prune()
    with vault.claim(handle) as (payload, lease):
        if not payload:
            return None, {"status": "pending" if devices.get(handle) else "expired", "interval": 5}
        device = Device(**payload)
        now = time.time()
        if now < device.next_poll:
            return None, {"status": "pending", "interval": device.interval}
        device.next_poll = now + device.interval
        if not vault.update_claim(handle, lease, asdict(device)):
            return None, {"status": "expired", "interval": device.interval}
        token_requested_at = time.time()
        result = await provider("POST", "/login/oauth/access_token", data={
            "client_id": device.client_id, "device_code": device.code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        })
        error = result.get("error")
        if error in {"authorization_pending", "slow_down"}:
            if error == "slow_down":
                device.interval = min(60, device.interval + 5)
                device.next_poll = time.time() + device.interval
                vault.update_claim(handle, lease, asdict(device))
            return None, {"status": "pending", "interval": device.interval}
        if error:
            vault.cancel_claim(handle, lease)
            return None, {"status": "denied" if error == "access_denied" else "expired", "interval": 5}
        token = result.get("access_token", "")
        # A classic OAuth app or PAT cannot be accidentally used here.
        if not isinstance(token, str) or not token.startswith("ghu_") or len(token) > 512 or result.get("scope"):
            raise HTTPException(502, "Expected a fine-grained GitHub App authorization.")
        profile = await provider("GET", "/user", token=token)
        if not vault.update_claim(handle, lease, asdict(device)):
            return None, {"status": "expired", "interval": device.interval}
        if type(profile.get("id")) is not int or not re.fullmatch(r"[A-Za-z0-9-]{1,100}", profile.get("login", "")):
            raise HTTPException(502, "GitHub returned an invalid user identity.")
        secret = os.environ["SESSION_SECRET"]
        owner = hmac.new(secret.encode(), f"github-user:{profile['id']}".encode(), hashlib.sha256).hexdigest()
        store.ensure_account_session(owner)
        # Never retain a refresh token. Reauthorization is explicit.
        try:
            ttl = max(1, min(SESSION_TTL, int(result.get("expires_in", SESSION_TTL))))
        except (TypeError, ValueError) as exc:
            raise HTTPException(502, "GitHub returned invalid authorization expiry.") from exc
        auth_handle = secrets.token_urlsafe(32)
        user = Identity(token, owner, profile["login"], token_requested_at + ttl, device.client_id, device.slug)
        if not vault.complete(handle, lease, auth_handle, asdict(user)):
            return None, {"status": "expired", "interval": device.interval}
        return auth_handle, {"status": "connected", "interval": 5}


async def authorized_token(handle: str, owner: str, repo: str) -> str:
    """Recheck the live intersection of user membership and app selection per import."""
    user = identity(handle)
    if not user:
        raise HTTPException(401, "Connect your GitHub account first, or upload source files.")
    target = f"{owner}/{repo}".lower()
    installs = await provider("GET", "/user/installations?per_page=100", token=user.token)
    for installation in installs.get("installations", [])[:100]:
        permissions = installation.get("permissions", {})
        # Refuse all-repository installs and any write or unrelated grant.
        if (installation.get("repository_selection") != "selected" or installation.get("suspended_at")
                or permissions.get("contents") != "read"
                or any(k not in {"contents", "metadata"} or v != "read" for k, v in permissions.items())):
            continue
        iid = installation.get("id")
        if type(iid) is not int:
            continue
        for page in range(1, 21):
            result = await provider("GET", f"/user/installations/{iid}/repositories?" +
                                    urlencode({"per_page": 100, "page": page}), token=user.token)
            repositories = result.get("repositories", [])
            if any(r.get("full_name", "").lower() == target for r in repositories):
                # Disconnection while a provider request was in flight must fail closed.
                if not identity(handle):
                    raise HTTPException(401, "GitHub was disconnected. Reconnect or upload files.")
                return user.token
            if len(repositories) < 100:
                break
    raise InputError("Repository is not authorized. Install the read-only GitHub App on selected repositories, "
                     "check your own access/organization approval, then retry. Uploads remain available.")
