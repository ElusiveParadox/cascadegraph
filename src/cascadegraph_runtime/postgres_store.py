"""Parameterized PostgreSQL snapshot operations; no runtime schema changes."""

import secrets

from psycopg.types.json import Jsonb


async def initialize(db):
    # Fail explicitly on missing schema. Development setup / Publish owns DDL.
    await probe(db)


async def probe(db):
    await db.execute("SELECT id FROM cg_sessions LIMIT 0")
    await db.execute("SELECT id, owner, data, expires_at, sequence FROM cg_analyses LIMIT 0")
    await db.execute("SELECT id, analysis_id, data, sequence FROM cg_simulations LIMIT 0")


async def prune(db):
    await db.execute("DELETE FROM cg_analyses WHERE expires_at <= CURRENT_TIMESTAMP")
    await db.execute("DELETE FROM cg_sessions WHERE created_at <= CURRENT_TIMESTAMP - INTERVAL '25 hours'")


async def resolve_session(db, token):
    if token and await session_exists(db, token):
        return token, False
    # Serialize only new-session capacity checks, not ordinary reads.
    await db.execute("SELECT pg_advisory_xact_lock(7070001)")
    await prune(db)
    row = await (await db.execute("SELECT count(*) FROM cg_sessions")).fetchone()
    if row[0] >= 5000:
        raise ValueError("Session capacity reached; retry after retention cleanup")
    token = secrets.token_urlsafe(32)
    await db.execute("INSERT INTO cg_sessions (id) VALUES (%s)", (token,))
    return token, True


async def create_session(db):
    token, _ = await resolve_session(db, "")
    return token


async def session_exists(db, token):
    return bool(await (await db.execute(
        "SELECT 1 FROM cg_sessions WHERE id=%s AND created_at > CURRENT_TIMESTAMP - INTERVAL '25 hours'",
        (token,),
    )).fetchone())


async def save_analysis(db, owner, data):
    # A session row lock serializes its quota checks and saves without a global
    # write lock. Ownership is checked again in the upsert's conflict clause.
    session = await (await db.execute("SELECT id FROM cg_sessions WHERE id=%s FOR UPDATE", (owner,))).fetchone()
    if not session:
        raise PermissionError("Session unavailable")
    await db.execute("DELETE FROM cg_analyses WHERE owner=%s AND expires_at <= CURRENT_TIMESTAMP", (owner,))
    existing = await (await db.execute("SELECT owner FROM cg_analyses WHERE id=%s", (data["id"],))).fetchone()
    if existing and existing[0] != owner:
        raise PermissionError("Analysis owner mismatch")
    count = await (await db.execute("SELECT count(*) FROM cg_analyses WHERE owner=%s", (owner,))).fetchone()
    if not existing and count[0] >= 20:
        raise ValueError("Delete an analysis before exceeding 20 analyses per session")
    cursor = await db.execute(
        """INSERT INTO cg_analyses (id,owner,data,expires_at) VALUES (%s,%s,%s,%s)
        ON CONFLICT(id) DO UPDATE SET data=excluded.data WHERE cg_analyses.owner=excluded.owner""",
        (data["id"], owner, Jsonb(data), data["expires_at"]),
    )
    if not cursor.rowcount:
        raise PermissionError("Analysis owner mismatch")


async def get_analysis(db, owner, aid):
    row = await (await db.execute(
        "SELECT data FROM cg_analyses WHERE id=%s AND owner=%s AND expires_at > CURRENT_TIMESTAMP",
        (aid, owner),
    )).fetchone()
    return row[0] if row else None


async def list_analyses(db, owner):
    rows = await (await db.execute(
        """SELECT data FROM cg_analyses WHERE owner=%s AND expires_at > CURRENT_TIMESTAMP
        ORDER BY sequence DESC""", (owner,),
    )).fetchall()
    return [row[0] for row in rows]


async def delete_analysis(db, owner, aid):
    return (await db.execute("DELETE FROM cg_analyses WHERE owner=%s AND id=%s", (owner, aid))).rowcount


async def save_simulation(db, owner, data):
    row = await (await db.execute(
        """SELECT id FROM cg_analyses WHERE id=%s AND owner=%s AND expires_at > CURRENT_TIMESTAMP
        FOR UPDATE""", (data["analysis_id"], owner),
    )).fetchone()
    if not row:
        raise PermissionError("Analysis unavailable")
    count = await (await db.execute(
        "SELECT count(*) FROM cg_simulations WHERE analysis_id=%s", (data["analysis_id"],),
    )).fetchone()
    if count[0] >= 20:
        raise ValueError("Simulation limit of 20 per analysis reached")
    await db.execute(
        "INSERT INTO cg_simulations (id,analysis_id,data) VALUES (%s,%s,%s)",
        (data["id"], data["analysis_id"], Jsonb(data)),
    )


async def simulations(db, owner, aid):
    rows = await (await db.execute(
        """SELECT s.data FROM cg_simulations s JOIN cg_analyses a ON a.id=s.analysis_id
        WHERE a.id=%s AND a.owner=%s AND a.expires_at > CURRENT_TIMESTAMP ORDER BY s.sequence""",
        (aid, owner),
    )).fetchall()
    return [row[0] for row in rows]


async def get_simulation(db, owner, sid):
    row = await (await db.execute(
        """SELECT s.data FROM cg_simulations s JOIN cg_analyses a ON a.id=s.analysis_id
        WHERE s.id=%s AND a.owner=%s AND a.expires_at > CURRENT_TIMESTAMP""", (sid, owner),
    )).fetchone()
    return row[0] if row else None
