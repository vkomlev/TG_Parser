-- WordPress Source (SQLite): история запусков sync
-- BIGSERIAL -> INTEGER PRIMARY KEY AUTOINCREMENT
CREATE TABLE IF NOT EXISTS wp_sync_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    site_id         TEXT NOT NULL REFERENCES wp_sites(site_id),
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    status          TEXT NOT NULL DEFAULT 'running',
    error_code      TEXT,
    posts_count     INTEGER NOT NULL DEFAULT 0,
    pages_count     INTEGER NOT NULL DEFAULT 0,
    terms_count     INTEGER NOT NULL DEFAULT 0,
    authors_count   INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_wp_sync_runs_site_started ON wp_sync_runs(site_id, started_at);
CREATE INDEX IF NOT EXISTS idx_wp_sync_runs_run_id ON wp_sync_runs(run_id);
