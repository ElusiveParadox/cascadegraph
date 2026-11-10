import io
import stat
import zipfile

import pytest

from cascadegraph_runtime.security import MAX_FILE, InputError, ingest_zip, redact


def zipped(path, data="services: {}", link=False):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        info = zipfile.ZipInfo(path)
        if link:
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
        z.writestr(info, data)
    return stream.getvalue()


@pytest.mark.parametrize("path", ["../compose.yml", "/compose.yml", "a/../../b.py", "C:/b.py", "a\\b.py", "a/\x01.py"])
def test_traversal_rejected(path):
    with pytest.raises(InputError):
        ingest_zip(zipped(path))


def test_links_and_large_file():
    with pytest.raises(InputError):
        ingest_zip(zipped("link.py", link=True))
    with pytest.raises(InputError):
        ingest_zip(zipped("big.py", "a" * (MAX_FILE + 1)))


def test_wrapped_repo_normalized_and_env_ignored():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("repo/compose.yml", "services: {}")
        z.writestr("repo/.env", "API_KEY=secret")
        z.writestr("repo/node_modules/foo.py", "BAD=True")
    assert list(ingest_zip(stream.getvalue())) == ["compose.yml"]


def test_invalid_archive():
    with pytest.raises(InputError):
        ingest_zip(b"not a zip")


def test_secret_redaction():
    assert "supersecret" not in redact("API_KEY='supersecret'")
    assert "[REDACTED]" in redact("token=ghp_01234567890123456789")


def test_decompression_ratio():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("bomb.py", " " * 100000)
    with pytest.raises(InputError):
        ingest_zip(stream.getvalue())
