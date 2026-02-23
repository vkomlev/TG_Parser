-- WordPress Source: термины (categories, tags)
CREATE TABLE IF NOT EXISTS wp_terms (
    site_id         VARCHAR(64) NOT NULL REFERENCES wp_sites(site_id),
    taxonomy        VARCHAR(64) NOT NULL,
    wp_term_id      BIGINT NOT NULL,
    name            VARCHAR(255),
    slug            VARCHAR(255) NOT NULL,
    parent_id       BIGINT,
    raw_json        JSONB,
    synced_at       TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (site_id, taxonomy, wp_term_id)
);

CREATE INDEX IF NOT EXISTS idx_wp_terms_site_tax ON wp_terms(site_id, taxonomy);
