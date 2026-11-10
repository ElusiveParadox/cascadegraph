"""Bounded data-only ingestion; never extract archives to the filesystem."""

import hashlib
import io
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

import yaml
from yaml.tokens import AliasToken

MAX_ARCHIVE = 5 * 1024 * 1024
MAX_EXPANDED = 12 * 1024 * 1024
MAX_FILE = 128 * 1024
MAX_FILES = 500
ROOT = Path(__file__).resolve().parents[2]
IGNORED = {".git", ".env", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".github"}
SOURCE_SUFFIXES = {".py", ".yaml", ".yml", ".toml", ".txt"}


class InputError(ValueError):
    pass


def redact(text: str) -> str:
    text = re.sub(
        r"(?i)((?:api[_-]?key|secret|password|token)\s*[:=]\s*)[\"']?[^\"'\s,\n]+",
        r"\1[REDACTED]", text,
    )
    text = re.sub(r"(?:gh[pousr]_[A-Za-z0-9_]{15,}|sk-[A-Za-z0-9_-]{15,})", "[REDACTED]", text)
    text = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----", "[REDACTED PRIVATE KEY]", text)
    return text


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate keys instead of silently overwriting source evidence."""

    def construct_mapping(self, node, deep=False):
        keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
        if len(keys) != len(set(keys)):
            raise InputError("Duplicate YAML keys are unsupported")
        return super().construct_mapping(node, deep=deep)


def safe_yaml(text: str):
    try:
        if len(text.encode()) > MAX_FILE:
            raise InputError("YAML exceeds the per-file limit")
        if any(isinstance(token, AliasToken) for token in yaml.scan(text, Loader=yaml.SafeLoader)):
            raise InputError("YAML aliases are unsupported to bound expansion")
        loader = UniqueLoader(text)  # Subclass of SafeLoader; never Loader/UnsafeLoader.
        try:
            result = loader.get_single_data()
        finally:
            loader.dispose()
        def check(value, depth=0):
            if depth > 30:
                raise InputError("YAML nesting exceeds 30 levels")
            if isinstance(value, dict):
                for k, v in value.items():
                    if not isinstance(k, str):
                        raise InputError("YAML mapping keys must be strings")
                    check(v, depth + 1)
            elif isinstance(value, list):
                for v in value:
                    check(v, depth + 1)
        check(result)
        return result
    except (yaml.YAMLError, RecursionError, TypeError) as exc:
        raise InputError("Invalid or unsupported YAML") from exc


def ingest_zip(data: bytes) -> dict[str, str]:
    if len(data) > MAX_ARCHIVE:
        raise InputError("Archive exceeds 5 MiB")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_FILES:
                raise InputError("Archive exceeds 500 entries")
            total = 0
            files = {}
            for info in infos:
                path = PurePosixPath(info.filename)
                if (
                    path.is_absolute() or ".." in path.parts or "\\" in info.filename
                    or ":" in info.filename or len(path.parts) > 12
                    or any(ord(c) < 32 for c in info.filename)
                    or stat.S_ISLNK(info.external_attr >> 16)
                    or info.flag_bits & 1
                ):
                    raise InputError("Archive contains unsafe paths, links or encrypted entries")
                total += info.file_size
                if total > MAX_EXPANDED:
                    raise InputError("Expanded archive exceeds 12 MiB")
                if info.file_size > MAX_FILE:
                    raise InputError("Archive entry exceeds 128 KiB")
                if info.file_size > max(1, info.compress_size) * 100:
                    raise InputError("Archive compression ratio exceeds the safety limit")
                if info.is_dir() or any(p in IGNORED or p.startswith(".env") for p in path.parts):
                    continue
                if path.suffix.lower() not in SOURCE_SUFFIXES:
                    continue
                if str(path) in files:
                    raise InputError("Duplicate archive path")
                try:
                    raw = archive.read(info)
                    if b"\0" in raw:
                        continue
                    files[str(path)] = raw.decode("utf-8")
                except UnicodeDecodeError:
                    continue
            if not files:
                raise InputError("No supported UTF-8 source files found")
            # GitHub downloads commonly wrap the repository in one directory.
            roots = {p.split("/")[0] for p in files}
            if len(roots) == 1 and all("/" in p for p in files):
                files = {p.split("/", 1)[1]: s for p, s in files.items()}
            return files
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise InputError("Invalid ZIP archive") from exc


def sample_files() -> dict[str, str]:
    root = ROOT / "sample-app"
    return {
        p.relative_to(root).as_posix(): p.read_text()
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.suffix in SOURCE_SUFFIXES and "__pycache__" not in p.parts
    }
