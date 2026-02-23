-- WordPress Source: посты и страницы
CREATE TABLE IF NOT EXISTS wp_content (
    site_id         VARCHAR(64) NOT NULL REFERENCES wp_sites(site_id),
    content_type    VARCHAR(16) NOT NULL,
    wp_id           BIGINT NOT NULL,
    title           TEXT,
    slug            VARCHAR(255) NOT NULL,
    post_content    TEXT,
    excerpt         TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'publish',
    author_id       BIGINT,
    published_at    TIMESTAMPTZ,
    modified_at     TIMESTAMPTZ,
    seo_title       VARCHAR(255),
    seo_description TEXT,
    seo_json        JSONB,
    raw_json        JSONB,
    synced_at       TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (site_id, content_type, wp_id)
);

CREATE INDEX IF NOT EXISTS idx_wp_content_site_type ON wp_content(site_id, content_type);
CREATE INDEX IF NOT EXISTS idx_wp_content_published ON wp_content(site_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_wp_content_slug ON wp_content(site_id, content_type, slug);
