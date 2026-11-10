-- Development schema source. Publish applies the dev/prod schema diff.
-- Credential ciphertext is isolated from history and has no history foreign key.
CREATE TABLE IF NOT EXISTS github_credentials (
    handle_hash TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('device','identity')),
    ciphertext TEXT NOT NULL,
    expires_at DOUBLE PRECISION NOT NULL,
    token_tag TEXT NOT NULL DEFAULT '',
    lease_id TEXT NOT NULL DEFAULT '',
    lease_until DOUBLE PRECISION NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS github_credentials_expiry ON github_credentials(expires_at);
CREATE INDEX IF NOT EXISTS github_credentials_token ON github_credentials(token_tag);
-- Never execute this file during production build or application startup.
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    data TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS simulations (
    id TEXT PRIMARY KEY,
    analysis_id TEXT NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS analyses_owner ON analyses(owner);
CREATE INDEX IF NOT EXISTS analyses_expiry ON analyses(expires_at);
