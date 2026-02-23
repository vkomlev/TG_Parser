-- WordPress Source: таблица сайтов
CREATE TABLE IF NOT EXISTS wp_sites (
    site_id     VARCHAR(64) PRIMARY KEY,
    base_url    VARCHAR(512) NOT NULL,
    name        VARCHAR(255),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE wp_sites IS 'Зарегистрированные WordPress-сайты для синхронизации';
