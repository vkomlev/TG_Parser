-- WordPress Source: авторы (users)
CREATE TABLE IF NOT EXISTS wp_authors (
    site_id         VARCHAR(64) NOT NULL REFERENCES wp_sites(site_id),
    wp_user_id      BIGINT NOT NULL,
    login           VARCHAR(255),
    name            VARCHAR(255),
    slug            VARCHAR(255),
    raw_json        JSONB,
    synced_at       TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (site_id, wp_user_id)
);

CREATE INDEX IF NOT EXISTS idx_wp_authors_site ON wp_authors(site_id);
