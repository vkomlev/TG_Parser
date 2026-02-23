-- WordPress Source (SQLite): таблица сайтов
-- TIMESTAMPTZ -> TEXT (ISO 8601), остальное как в Postgres
CREATE TABLE IF NOT EXISTS wp_sites (
    site_id     TEXT PRIMARY KEY,
    base_url    TEXT NOT NULL,
    name        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
