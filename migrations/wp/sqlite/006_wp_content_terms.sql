-- WordPress Source (SQLite): связь контент — термины
CREATE TABLE IF NOT EXISTS wp_content_terms (
    site_id         TEXT NOT NULL,
    content_type    TEXT NOT NULL,
    wp_content_id   INTEGER NOT NULL,
    taxonomy        TEXT NOT NULL,
    wp_term_id      INTEGER NOT NULL,
    synced_at       TEXT NOT NULL,
    PRIMARY KEY (site_id, content_type, wp_content_id, taxonomy, wp_term_id),
    FOREIGN KEY (site_id, content_type, wp_content_id)
        REFERENCES wp_content(site_id, content_type, wp_id) ON DELETE CASCADE,
    FOREIGN KEY (site_id, taxonomy, wp_term_id)
        REFERENCES wp_terms(site_id, taxonomy, wp_term_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_wp_content_terms_term ON wp_content_terms(site_id, taxonomy, wp_term_id);
