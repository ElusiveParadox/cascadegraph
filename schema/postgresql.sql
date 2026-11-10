-- Apply to development explicitly; Replit Publish manages production schema.
CREATE TABLE IF NOT EXISTS cg_sessions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cg_analyses (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL REFERENCES cg_sessions(id) ON DELETE CASCADE,
    data JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    sequence BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE
);
CREATE INDEX IF NOT EXISTS cg_analyses_owner ON cg_analyses(owner, sequence DESC);
CREATE INDEX IF NOT EXISTS cg_analyses_expiry ON cg_analyses(expires_at);
CREATE TABLE IF NOT EXISTS cg_simulations (
    id TEXT PRIMARY KEY,
    analysis_id TEXT NOT NULL REFERENCES cg_analyses(id) ON DELETE CASCADE,
    data JSONB NOT NULL,
    sequence BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE
);
CREATE INDEX IF NOT EXISTS cg_simulations_analysis ON cg_simulations(analysis_id, sequence);
