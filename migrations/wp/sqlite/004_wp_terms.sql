-- WordPress Source (SQLite): термины
CREATE TABLE IF NOT EXISTS wp_terms (
    site_id         TEXT NOT NULL REFERENCES wp_sites(site_id),
    taxonomy        TEXT NOT NULL,
    wp_term_id      INTEGER NOT NULL,
    name            TEXT,
    slug            TEXT NOT NULL,
    parent_id       INTEGER,
    raw_json        TEXT,
    synced_at       TEXT NOT NULL,
    PRIMARY KEY (site_id, taxonomy, wp_term_id)
);

CREATE INDEX IF NOT EXISTS idx_wp_terms_site_tax ON wp_terms(site_id, taxonomy);
