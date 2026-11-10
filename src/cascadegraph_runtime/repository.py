"""Bounded GitHub snapshots. Never use the creator's OAuth or execute Git."""

import asyncio
import ipaddress
import logging
import re
import socket
from urllib.parse import parse_qs, quote, urlsplit

import httpx

from .models import RepositorySource
from .security import MAX_ARCHIVE, InputError, ingest_zip

HOSTS = {"api.github.com", "codeload.github.com"}
# HTTP client INFO logs include temporary signed archive URLs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
OWNER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")
REF = re.compile(r"[A-Za-z0-9_./-]{1,200}\Z")


def parse_repository_url(value: str) -> tuple[str, str, str]:
    value = value.strip()
    try:
        url = urlsplit(value)
        if (
            url.scheme != "https" or url.hostname != "github.com"
            or url.username or url.password or url.port is not None
            or url.query or url.fragment or "%" in url.path
        ):
            raise InputError("Use an https://github.com/owner/repository URL without credentials, query or fragment")
    except ValueError as exc:
        raise InputError("Invalid GitHub repository URL") from exc
    parts = url.path.strip("/").split("/")
    if len(parts) != 2:
        raise InputError("Use the repository's root URL; put its branch/tag in the separate reference field")
    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not OWNER.fullmatch(owner) or not REPO.fullmatch(repo) or repo in {".", ".."}:
        raise InputError("Invalid GitHub owner or repository name")
    return owner, repo, f"https://github.com/{owner}/{repo}"


def validate_ref(value: str) -> str:
    value = value.strip() or "HEAD"
    if not REF.fullmatch(value) or ".." in value or value.startswith("/") or value.endswith("/"):
        raise InputError("Reference must be a bounded branch, tag or commit SHA")
    return value


async def public_host(host: str):
    if host not in HOSTS:
        raise InputError("Repository download host is not allowed")
    try:
        results = await asyncio.to_thread(socket.getaddrinfo, host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise InputError("GitHub could not be resolved; try again or upload source files") from exc
    if not results or any(not ipaddress.ip_address(item[4][0]).is_global for item in results):
        raise InputError("Non-public repository network destinations are forbidden")


async def bounded_response(
    client: httpx.AsyncClient, url: str, limit: int, accept: str = "application/zip", *,
    headers: dict | None = None, signed_archive: bool = False,
) -> bytes:
    target = urlsplit(url)
    if (target.scheme != "https" or target.netloc not in HOSTS or target.fragment
            or (target.query and not signed_archive)):
        raise InputError("Only credential-free HTTPS requests to fixed GitHub hosts are allowed")
    await public_host(target.hostname)
    async with client.stream("GET", url, headers={"Accept": accept, **(headers or {})}) as response:
        if response.is_redirect:
            raise InputError("GitHub redirected this repository; use its current canonical repository URL")
        if response.status_code == 404:
            raise InputError("Repository/reference not found or not authorized. Connect GitHub or upload ZIP/source files")
        if response.status_code == 401:
            raise InputError("GitHub authorization expired or was revoked. Reconnect or upload source files")
        if response.status_code in {403, 429}:
            raise InputError("GitHub's public download/rate limit was reached. Try later or upload a ZIP/source files")
        if response.status_code != 200:
            raise InputError("GitHub source retrieval failed; try later or upload a ZIP/source files")
        try:
            size = int(response.headers.get("content-length", "0"))
        except ValueError as exc:
            raise InputError("Invalid GitHub response size") from exc
        if size < 0 or size > limit:
            raise InputError("GitHub snapshot exceeds the download limit; upload only the relevant source files")
        raw = bytearray()
        async for chunk in response.aiter_bytes(65536):
            raw.extend(chunk)
            if len(raw) > limit:
                raise InputError("GitHub snapshot exceeds the download limit; upload only the relevant source files")
        return bytes(raw)


async def private_archive(client, owner, repo, commit, token):
    """Only this endpoint may supply one strictly validated signed codeload URL."""
    await public_host("api.github.com")
    url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{commit}"
    async with client.stream("GET", url, headers={"Authorization": f"Bearer {token}"}) as response:
        if response.status_code != 302:
            raise InputError("GitHub archive access denied or unavailable. Reconnect, check permissions or upload files.")
        target = response.headers.get("location", "")
    parsed = urlsplit(target)
    allowed_paths = {f"/{owner}/{repo}/legacy.zip/{commit}", f"/{owner}/{repo}/zip/{commit}"}
    if (parsed.scheme != "https" or parsed.netloc != "codeload.github.com" or parsed.path not in allowed_paths
            or parsed.fragment or len(target) > 4096
            or set(parse_qs(parsed.query, keep_blank_values=True)) - {"token"}):
        raise InputError("GitHub returned an unsafe archive destination. Upload source files instead.")
    # No bearer token is ever sent to codeload, and no further redirects are followed.
    return await bounded_response(client, target, MAX_ARCHIVE, signed_archive=True)


async def fetch_repository(repository_url: str, ref: str = "", *, access_token: str = "") -> tuple[dict[str, str], RepositorySource]:
    owner, repo, canonical = parse_repository_url(repository_url)
    owner, repo = quote(owner, safe=""), quote(repo, safe="")
    ref = validate_ref(ref)

    async def retrieve():
        # Ignore ambient proxy credentials. Auth is explicit, per request, API-only.
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10, connect=5), follow_redirects=False, trust_env=False,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "CascadeGraph-Public-Analyzer"},
        ) as client:
            metadata = await bounded_response(
                client, f"https://api.github.com/repos/{owner}/{repo}/commits/{quote(ref, safe='')}",
                256, "application/vnd.github.sha",
                headers={"Authorization": f"Bearer {access_token}"} if access_token else None,
            )
            try:
                commit = metadata.decode("ascii").strip()
                if not re.fullmatch(r"[a-fA-F0-9]{40}", commit):
                    raise ValueError("Unexpected commit")
            except (ValueError, UnicodeError) as exc:
                raise InputError("GitHub returned invalid commit metadata") from exc
            if access_token:
                archive = await private_archive(client, owner, repo, commit, access_token)
            else:
                archive = await bounded_response(
                    client, f"https://codeload.github.com/{owner}/{repo}/zip/{commit}", MAX_ARCHIVE,
                )
            return ingest_zip(archive), RepositorySource(
                repository_url=canonical, commit_sha=commit.lower(), ref=ref,
            )
    try:
        return await asyncio.wait_for(retrieve(), timeout=45)
    except (httpx.HTTPError, TimeoutError) as exc:
        raise InputError("GitHub retrieval timed out or failed. Retry, or upload the ZIP/source files instead") from exc
