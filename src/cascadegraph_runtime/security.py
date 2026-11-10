"""Bounded data-only ingestion; never extract archives to the filesystem."""

import hashlib
import io
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

import yaml
from yaml.tokens import AliasToken

MAX_ARCHIVE = 50 * 1024 * 1024
MAX_EXPANDED = 200 * 1024 * 1024
MAX_SOURCE = 20 * 1024 * 1024
MAX_FILE = 512 * 1024
MAX_FILES = 2000
MAX_BODY = MAX_ARCHIVE + 2 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[2]
IGNORED = {".git", ".env", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".github"}
SOURCE_SUFFIXES = {".py", ".yaml", ".yml", ".toml", ".txt"}


class InputError(ValueError):
    pass


def validate_source_path(name: str) -> str:
    path = PurePosixPath(name)
    if (
        not name or len(name) > 300 or path.is_absolute() or ".." in path.parts
        or "\\" in name or ":" in name or len(path.parts) > 16
        or any(ord(c) < 32 for c in name) or str(path) in {".", ""}
    ):
        raise InputError("Source paths must be bounded repository-relative paths")
    return str(path)


def supported_source(path: str) -> bool:
    value = PurePosixPath(path)
    return (
        not any(p in IGNORED or p.startswith(".env") for p in value.parts)
        and value.suffix.lower() in SOURCE_SUFFIXES
    )


def validate_sources(files: dict[str, str]) -> dict[str, str]:
    if not files or len(files) > MAX_FILES:
        raise InputError(f"Provide 1–{MAX_FILES} supported source files")
    total = 0
    for path, text in files.items():
        validate_source_path(path)
        if not supported_source(path):
            raise InputError("Only supported source/configuration files are accepted; secret/dependency paths are excluded")
        size = len(text.encode("utf-8"))
        if size > MAX_FILE:
            raise InputError("A supported source file exceeds 512 KiB")
        if "\0" in text:
            raise InputError("Binary source files are unsupported")
        total += size
        if total > MAX_SOURCE:
            raise InputError("Retained supported source exceeds 20 MiB")
    return files


def select_project(files: dict[str, str], project_path: str = ".") -> dict[str, str]:
    if project_path.strip() in {"", "."}:
        return files
    prefix = validate_source_path(project_path.strip().rstrip("/")) + "/"
    selected = {path[len(prefix):]: text for path, text in files.items() if path.startswith(prefix)}
    if not selected:
        raise InputError("Project folder contains no supported source files; check its repository-relative path")
    return selected


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
        raise InputError("Archive exceeds 50 MiB")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_FILES:
                raise InputError(f"Archive exceeds {MAX_FILES} entries")
            total = 0
            source_bytes = 0
            files = {}
            seen = set()
            for info in infos:
                path = PurePosixPath(info.filename)
                if (
                    path.is_absolute() or ".." in path.parts or "\\" in info.filename
                    or ":" in info.filename or len(path.parts) > 16 or len(info.filename) > 300
                    or any(ord(c) < 32 for c in info.filename)
                    or stat.S_ISLNK(info.external_attr >> 16)
                    or info.flag_bits & 1
                ):
                    raise InputError("Archive contains unsafe paths, links or encrypted entries")
                if str(path) in seen:
                    raise InputError("Duplicate archive path")
                seen.add(str(path))
                total += info.file_size
                if total > MAX_EXPANDED:
                    raise InputError("Expanded archive exceeds 200 MiB")
                if info.is_dir() or any(p in IGNORED or p.startswith(".env") for p in path.parts):
                    continue
                if path.suffix.lower() not in SOURCE_SUFFIXES:
                    continue
                if info.file_size > MAX_FILE:
                    raise InputError("A supported source file exceeds 512 KiB")
                if info.file_size > max(1, info.compress_size) * 100:
                    raise InputError("Archive compression ratio exceeds the safety limit")
                try:
                    raw = archive.read(info)
                    if b"\0" in raw:
                        continue
                    text = raw.decode("utf-8")
                    source_bytes += len(raw)
                    if source_bytes > MAX_SOURCE:
                        raise InputError("Retained supported source exceeds 20 MiB")
                    files[str(path)] = text
                except UnicodeDecodeError:
                    continue
            if not files:
                raise InputError("No supported UTF-8 source files found")
            # GitHub downloads commonly wrap the repository in one directory.
            roots = {p.split("/")[0] for p in files}
            if len(roots) == 1 and all("/" in p for p in files):
                files = {p.split("/", 1)[1]: s for p, s in files.items()}
            return validate_sources(files)
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise InputError("Invalid ZIP archive") from exc


def sample_files() -> dict[str, str]:
    root = ROOT / "sample-app"
    return {
        p.relative_to(root).as_posix(): p.read_text()
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.suffix in SOURCE_SUFFIXES and "__pycache__" not in p.parts
    }
