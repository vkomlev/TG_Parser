-- WordPress Source (SQLite): посты и страницы
CREATE TABLE IF NOT EXISTS wp_content (
    site_id         TEXT NOT NULL REFERENCES wp_sites(site_id),
    content_type    TEXT NOT NULL,
    wp_id           INTEGER NOT NULL,
    title           TEXT,
    slug            TEXT NOT NULL,
    post_content    TEXT,
    excerpt         TEXT,
    status          TEXT NOT NULL DEFAULT 'publish',
    author_id       INTEGER,
    published_at    TEXT,
    modified_at     TEXT,
    seo_title       TEXT,
    seo_description TEXT,
    seo_json        TEXT,
    raw_json        TEXT,
    synced_at       TEXT NOT NULL,
    PRIMARY KEY (site_id, content_type, wp_id)
);

CREATE INDEX IF NOT EXISTS idx_wp_content_site_type ON wp_content(site_id, content_type);
CREATE INDEX IF NOT EXISTS idx_wp_content_published ON wp_content(site_id, published_at);
CREATE INDEX IF NOT EXISTS idx_wp_content_slug ON wp_content(site_id, content_type, slug);
