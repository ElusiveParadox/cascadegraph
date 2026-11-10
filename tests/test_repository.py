import asyncio
import io
import socket
import zipfile

import httpx
import pytest

from cascadegraph_runtime import repository
from cascadegraph_runtime.models import RepositorySource
from cascadegraph_runtime.security import MAX_ARCHIVE, InputError, ingest_zip, sample_files, validate_sources

SHA = "a" * 40


@pytest.mark.parametrize("url", [
    "http://github.com/a/b", "https://127.0.0.1/a/b", "https://169.254.169.254/a/b",
    "https://github.com.evil.test/a/b", "https://github.com@127.0.0.1/a/b",
    "https://token@github.com/a/b", "https://github.com:443/a/b",
    "https://github.com/a/b?access_token=x", "https://github.com/a/b#x",
    "https://github.com/a/%2e%2e", "file:///etc/passwd", "https://github.com/a/b/tree/main",
])
def test_repository_url_policy(url):
    with pytest.raises(InputError):
        repository.parse_repository_url(url)


def test_canonical_url_and_ref():
    assert repository.parse_repository_url("https://github.com/owner/repo.git/") == (
        "owner", "repo", "https://github.com/owner/repo",
    )
    assert repository.validate_ref("feature/retry") == "feature/retry"
    assert repository.validate_ref("") == "HEAD"
    for ref in ("../../main", "main?token=x", "/main", "main\nother"):
        with pytest.raises(InputError):
            repository.validate_ref(ref)


def dns_public(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
    ])


def test_private_dns_rejected(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
    ])
    with pytest.raises(InputError, match="Non-public"):
        asyncio.run(repository.public_host("api.github.com"))
    with pytest.raises(InputError, match="not allowed"):
        asyncio.run(repository.public_host("metadata.google.internal"))


@pytest.mark.parametrize("url", [
    "http://api.github.com/repos/a/b", "https://token@api.github.com/repos/a/b",
    "https://api.github.com:443/repos/a/b", "https://api.github.com/repos/a/b?token=x",
    "https://codeload.github.com.evil.test/a/b", "https://169.254.169.254/",
])
def test_outbound_url_policy_before_dns(monkeypatch, url):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: pytest.fail("Unsafe target must not resolve"))

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: pytest.fail("Must not fetch"))) as client:
            await repository.bounded_response(client, url, 256)
    with pytest.raises(InputError):
        asyncio.run(run())


def zip_sources(prefix="snapshot/sample-app/"):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for path, text in sample_files().items():
            archive.writestr(prefix + path, text)
    return stream.getvalue()


def test_fetch_pins_commit_and_does_not_send_credentials(monkeypatch):
    dns_public(monkeypatch)
    seen = []

    def handler(request):
        seen.append(str(request.url))
        assert "authorization" not in request.headers and "cookie" not in request.headers
        if request.url.host == "api.github.com":
            assert request.headers["accept"] == "application/vnd.github.sha"
            return httpx.Response(200, text=SHA)
        assert str(request.url) == f"https://codeload.github.com/owner/repo/zip/{SHA}"
        return httpx.Response(200, content=zip_sources())

    original = httpx.AsyncClient

    def factory(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return original(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    files, source = asyncio.run(repository.fetch_repository("https://github.com/owner/repo"))
    assert source.commit_sha == SHA
    assert "sample-app/compose.yaml" in files
    assert len(seen) == 2


@pytest.mark.parametrize("status", [302, 404, 403, 429, 500])
def test_redirects_and_upstream_failures_are_explicit(monkeypatch, status):
    dns_public(monkeypatch)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(
                status, headers={"Location": "http://169.254.169.254/latest/meta-data"}, text="untrusted upstream body",
            )),
        ) as client:
            return await repository.bounded_response(client, "https://api.github.com/repos/a/b/commits/HEAD", 256)
    with pytest.raises(InputError) as error:
        asyncio.run(run())
    assert "untrusted upstream body" not in str(error.value)


def test_stream_limit_without_content_length(monkeypatch):
    dns_public(monkeypatch)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"x" * 100),
        )) as client:
            return await repository.bounded_response(client, "https://codeload.github.com/a/b/zip/" + SHA, 10)
    with pytest.raises(InputError, match="download limit"):
        asyncio.run(run())


def test_large_irrelevant_assets_are_skipped_and_archive_limit_increased(client):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("compose.yaml", "services: {gateway: {}}")
        archive.writestr("assets/image.bin", b"x" * (6 * 1024 * 1024))
    assert MAX_ARCHIVE == 50 * 1024 * 1024
    assert len(stream.getvalue()) > 5 * 1024 * 1024
    assert list(ingest_zip(stream.getvalue())) == ["compose.yaml"]
    response = client.post("/api/v1/analyses/archive", files={"file": ("large.zip", stream.getvalue(), "application/zip")})
    assert response.status_code == 201


def test_retained_source_budget(monkeypatch):
    monkeypatch.setattr("cascadegraph_runtime.security.MAX_SOURCE", 10)
    with pytest.raises(InputError, match="Retained"):
        validate_sources({"main.py": "x" * 11})


def test_api_limits_and_host_rejection(client):
    status = client.get("/api/v1/status").json()
    assert status["max_archive_mb"] == 50
    assert status["max_expanded_mb"] == 200
    assert status["max_source_mb"] == 20
    assert status["max_file_kb"] == 512
    assert client.post("/api/v1/analyses/repository", json={"repository_url": "http://127.0.0.1/internal"}).status_code == 422
    assert client.post("/api/v1/analyses/repository", content=b"x" * 65537).status_code == 413


def test_repository_api_and_nested_compose_binding(client, monkeypatch):
    async def fetch(url, ref=""):
        return (
            {"sample-app/" + p: t for p, t in sample_files().items()},
            RepositorySource(repository_url="https://github.com/owner/repo", ref=ref or "HEAD", commit_sha=SHA),
        )
    monkeypatch.setattr("cascadegraph_runtime.app.fetch_repository", fetch)
    response = client.post("/api/v1/analyses/repository", json={"repository_url": "https://github.com/owner/repo"})
    assert response.status_code == 201, response.text
    analysis = response.json()
    assert len(analysis["nodes"]) == 3
    assert all(len(edge["policy_ids"]) == 1 for edge in analysis["edges"])
    assert analysis["repository"]["commit_sha"] == SHA
    assert analysis["requested_files"] == []
    projected = client.post("/api/v1/analyses/repository", json={
        "repository_url": "https://github.com/owner/repo", "project_path": "sample-app",
    })
    assert projected.status_code == 201
    assert len(projected.json()["edges"]) == 2
    assert client.get(f"/api/v1/analyses/{analysis['id']}/report").json()["analysis"]["repository"]["commit_sha"] == SHA


def test_direct_sources_and_missing_file_guidance(client):
    partial = client.post("/api/v1/analyses/sources", files=[
        ("files", ("client.py", b"from tenacity import retry, stop_after_attempt\n@retry(stop=stop_after_attempt(2))\ndef call(): pass\n")),
    ])
    assert partial.status_code == 201
    assert partial.json()["status"] == "partial"
    assert any("compose" in item for item in partial.json()["requested_files"])
    source = sample_files()
    response = client.post("/api/v1/analyses/sources",
                           data={"paths": list(source)},
                           files=[("files", (path.split("/")[-1], text.encode())) for path, text in source.items()])
    assert response.status_code == 201, response.text
    assert len(response.json()["edges"]) == 2
    assert response.json()["requested_files"] == []


def test_source_path_and_secret_rejection(client):
    for path in ("../client.py", ".env", "main.bin"):
        response = client.post("/api/v1/analyses/sources", data={"paths": [path]},
                               files=[("files", ("client.py", b"API_KEY='secret'"))])
        assert response.status_code == 422
    mismatch = client.post("/api/v1/analyses/sources", data={"paths": ["a.py", "b.py"]},
                           files=[("files", ("a.py", b"pass"))])
    assert mismatch.status_code == 422


def test_supplements_are_marked_not_falsely_claimed_as_repository_content(client, monkeypatch):
    async def fetch(url, ref=""):
        return sample_files(), RepositorySource(repository_url=url, ref=ref or "HEAD", commit_sha=SHA)
    monkeypatch.setattr("cascadegraph_runtime.app.fetch_repository", fetch)
    response = client.post("/api/v1/analyses/sources",
        data={"repository_url": "https://github.com/owner/repo", "ref": SHA, "paths": ["extra.py"]},
        files=[("files", ("extra.py", b"pass"))])
    assert response.status_code == 201, response.text
    assert response.json()["repository"]["supplemented_paths"] == ["extra.py"]
    assert any("not claimed" in item for item in response.json()["assumptions"])
