"""Authenticated encrypted authorization records, never analysis/history data.

Only opaque random handles leave the server. PostgreSQL transports records and
poll leases across replicas. The key stays in Replit Secrets, not this database.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from contextlib import contextmanager

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import HTTPException

from .storage_connection import Postgres, connection

CAPACITY = 1000
LEASE_SECONDS = 45


def keys():
    secret = os.getenv("SESSION_SECRET", "")
    if len(secret) < 32:
        raise HTTPException(503, "GitHub credential vault requires a stable, strong server secret.")
    material = HKDF(algorithm=hashes.SHA256(), length=64, salt=b"CascadeGraph-vault-v1",
                    info=b"server-only-credential-encryption-and-index").derive(secret.encode())
    return material[:32], material[32:]


def digest(value):
    return hmac.new(keys()[1], value.encode(), hashlib.sha256).hexdigest()


def valid(handle):
    return isinstance(handle, str) and bool(re.fullmatch(r"[A-Za-z0-9_-]{43}", handle))


@contextmanager
def database():
    try:
        with connection() as db:
            if isinstance(db, Postgres):
                db.execute("SELECT pg_advisory_xact_lock(74209532)")
            yield db
    except HTTPException:
        raise
    except Exception:
        # Never surface SQL parameters, ciphertext, provider material or DB URLs.
        raise HTTPException(503, "GitHub credential vault unavailable. Retry or upload source files.") from None


def seal(kind, hid, payload):
    nonce = secrets.token_bytes(12)
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(nonce + AESGCM(keys()[0]).encrypt(
        nonce, raw, f"cg-vault-v1:{kind}:{hid}".encode(),
    )).decode()


def unseal(kind, hid, value):
    try:
        raw = base64.urlsafe_b64decode(value)
        data = AESGCM(keys()[0]).decrypt(raw[:12], raw[12:], f"cg-vault-v1:{kind}:{hid}".encode())
        return json.loads(data)
    except (InvalidTag, ValueError, TypeError):
        raise HTTPException(503, "GitHub credential vault could not authenticate this connection. Reconnect.") from None


def prune():
    with database() as db:
        db.execute("DELETE FROM github_credentials WHERE expires_at <= ?", (time.time(),))


def fetch(kind, handle):
    if not valid(handle):
        return None
    hid = digest(handle)
    with database() as db:
        row = db.execute("SELECT ciphertext FROM github_credentials WHERE kind=? AND handle_hash=? AND expires_at>?",
                         (kind, hid, time.time())).fetchone()
        payload = unseal(kind, hid, row["ciphertext"]) if row else None
        return payload if payload and payload["expires"] > time.time() else None


def insert(db, kind, handle, payload):
    if not valid(handle) or payload["expires"] <= time.time():
        raise HTTPException(401, "GitHub connection expired. Reconnect.")
    db.execute("DELETE FROM github_credentials WHERE expires_at <= ?", (time.time(),))
    if db.execute("SELECT count(*) AS total FROM github_credentials WHERE kind=?", (kind,)).fetchone()["total"] >= CAPACITY:
        raise HTTPException(429, "GitHub connection capacity reached. Try later.")
    hid = digest(handle)
    tag = digest(payload["token"]) if kind == "identity" else ""
    db.execute("""INSERT INTO github_credentials
        (handle_hash,kind,ciphertext,expires_at,token_tag,lease_id,lease_until) VALUES (?,?,?,?,?,'',0)""",
               (hid, kind, seal(kind, hid, payload), payload["expires"], tag))


def put(kind, handle, payload):
    with database() as db:
        hid = digest(handle)
        existing = db.execute("SELECT 1 FROM github_credentials WHERE kind=? AND handle_hash=?", (kind, hid)).fetchone()
        if existing:
            tag = digest(payload["token"]) if kind == "identity" else ""
            db.execute("UPDATE github_credentials SET ciphertext=?,expires_at=?,token_tag=? WHERE kind=? AND handle_hash=?",
                       (seal(kind, hid, payload), payload["expires"], tag, kind, hid))
        else:
            insert(db, kind, handle, payload)


def remove(kind, handle):
    if valid(handle):
        with database() as db:
            db.execute("DELETE FROM github_credentials WHERE kind=? AND handle_hash=?", (kind, digest(handle)))


def revoke(token):
    if token:
        with database() as db:
            db.execute("DELETE FROM github_credentials WHERE kind='identity' AND token_tag=?", (digest(token),))


def count(kind):
    with database() as db:
        return db.execute("SELECT count(*) AS total FROM github_credentials WHERE kind=? AND expires_at>?",
                          (kind, time.time())).fetchone()["total"]


@contextmanager
def claim(handle):
    """Short DB transaction; no database lock is held over a provider call."""
    lease = secrets.token_hex(16)
    payload = None
    hid = digest(handle) if valid(handle) else ""
    with database() as db:
        row = db.execute("""SELECT ciphertext FROM github_credentials
            WHERE kind='device' AND handle_hash=? AND expires_at>? AND lease_until<=?""",
                         (hid, time.time(), time.time())).fetchone()
        if row:
            payload = unseal("device", hid, row["ciphertext"])
            if payload["expires"] <= time.time():
                payload = None
            else:
                db.execute("UPDATE github_credentials SET lease_id=?,lease_until=? WHERE handle_hash=?",
                           (lease, time.time() + LEASE_SECONDS, hid))
    try:
        yield payload, lease
    finally:
        if payload:
            with database() as db:
                db.execute("""UPDATE github_credentials SET lease_id='',lease_until=0
                    WHERE handle_hash=? AND lease_id=?""", (hid, lease))


def update_claim(handle, lease, payload):
    hid = digest(handle)
    with database() as db:
        return db.execute("""UPDATE github_credentials SET ciphertext=?
            WHERE kind='device' AND handle_hash=? AND lease_id=? AND lease_until>? AND expires_at>?""",
                          (seal("device", hid, payload), hid, lease, time.time(), time.time())).rowcount == 1


def cancel_claim(handle, lease):
    with database() as db:
        db.execute("DELETE FROM github_credentials WHERE kind='device' AND handle_hash=? AND lease_id=?",
                   (digest(handle), lease))


def complete(handle, lease, auth_handle, payload):
    """Atomically consume a device and publish one authenticated connection."""
    with database() as db:
        removed = db.execute("""DELETE FROM github_credentials
            WHERE kind='device' AND handle_hash=? AND lease_id=? AND lease_until>? AND expires_at>?""",
                             (digest(handle), lease, time.time(), time.time())).rowcount
        if removed:
            insert(db, "identity", auth_handle, payload)
        return bool(removed)
