-- WordPress Source: связь контент — термины (many-to-many)
CREATE TABLE IF NOT EXISTS wp_content_terms (
    site_id         VARCHAR(64) NOT NULL,
    content_type    VARCHAR(16) NOT NULL,
    wp_content_id   BIGINT NOT NULL,
    taxonomy        VARCHAR(64) NOT NULL,
    wp_term_id      BIGINT NOT NULL,
    synced_at       TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (site_id, content_type, wp_content_id, taxonomy, wp_term_id),
    FOREIGN KEY (site_id, content_type, wp_content_id)
        REFERENCES wp_content(site_id, content_type, wp_id) ON DELETE CASCADE,
    FOREIGN KEY (site_id, taxonomy, wp_term_id)
        REFERENCES wp_terms(site_id, taxonomy, wp_term_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_wp_content_terms_term ON wp_content_terms(site_id, taxonomy, wp_term_id);
