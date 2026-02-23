-- WordPress Source: история запусков sync
CREATE TABLE IF NOT EXISTS wp_sync_runs (
    id              BIGSERIAL PRIMARY KEY,
    run_id          VARCHAR(32) NOT NULL,
    site_id         VARCHAR(64) NOT NULL REFERENCES wp_sites(site_id),
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    status          VARCHAR(20) NOT NULL DEFAULT 'running',
    error_code      VARCHAR(64),
    posts_count     INT NOT NULL DEFAULT 0,
    pages_count     INT NOT NULL DEFAULT 0,
    terms_count     INT NOT NULL DEFAULT 0,
    authors_count   INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wp_sync_runs_site_started ON wp_sync_runs(site_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_wp_sync_runs_run_id ON wp_sync_runs(run_id);

COMMENT ON TABLE wp_sync_runs IS 'История запусков WP sync для наблюдаемости и отладки';
