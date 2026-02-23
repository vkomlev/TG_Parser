-- WordPress Source (SQLite): авторы
CREATE TABLE IF NOT EXISTS wp_authors (
    site_id         TEXT NOT NULL REFERENCES wp_sites(site_id),
    wp_user_id      INTEGER NOT NULL,
    login           TEXT,
    name            TEXT,
    slug            TEXT,
    raw_json        TEXT,
    synced_at       TEXT NOT NULL,
    PRIMARY KEY (site_id, wp_user_id)
);

CREATE INDEX IF NOT EXISTS idx_wp_authors_site ON wp_authors(site_id);
