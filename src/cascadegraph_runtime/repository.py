"""Public GitHub snapshots only. Never use the creator's OAuth or execute Git."""

import asyncio
import ipaddress
import re
import socket
from urllib.parse import quote, urlsplit

import httpx

from .models import RepositorySource
from .security import MAX_ARCHIVE, InputError, ingest_zip

HOSTS = {"api.github.com", "codeload.github.com"}
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
            raise InputError("Use a public https://github.com/owner/repository URL without credentials, query or fragment")
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


async def bounded_response(client: httpx.AsyncClient, url: str, limit: int, accept: str = "application/zip") -> bytes:
    host = urlsplit(url).hostname
    await public_host(host)
    async with client.stream("GET", url, headers={"Accept": accept}) as response:
        if response.is_redirect:
            raise InputError("GitHub redirected this repository; use its current canonical repository URL")
        if response.status_code == 404:
            raise InputError("Public repository/reference not found. Private repositories require a ZIP or source-file upload")
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


async def fetch_repository(repository_url: str, ref: str = "") -> tuple[dict[str, str], RepositorySource]:
    owner, repo, canonical = parse_repository_url(repository_url)
    ref = validate_ref(ref)

    async def retrieve():
        # Explicitly ignore ambient proxy credentials and never attach a token.
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10, connect=5), follow_redirects=False, trust_env=False,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "CascadeGraph-Public-Analyzer"},
        ) as client:
            metadata = await bounded_response(
                client, f"https://api.github.com/repos/{owner}/{repo}/commits/{quote(ref, safe='')}",
                256, "application/vnd.github.sha",
            )
            try:
                commit = metadata.decode("ascii").strip()
                if not re.fullmatch(r"[a-fA-F0-9]{40}", commit):
                    raise ValueError("Unexpected commit")
            except (ValueError, UnicodeError) as exc:
                raise InputError("GitHub returned invalid commit metadata") from exc
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
