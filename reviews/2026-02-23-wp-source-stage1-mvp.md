# Ревью: WordPress Source Этап 1 (MVP)

**Дата:** 2026-02-23  
**Контекст:** Внедрение нового функционала WP Source по ТЗ (только чтение WP, full sync в PostgreSQL).

## Изменения

- **errors.py:** добавлены коды `WP_AUTH_ERROR`, `WP_RATE_LIMIT`, `WP_NETWORK_ERROR`, `WP_DATA_FORMAT_ERROR`.
- **requirements.txt:** добавлены зависимости `PyYAML`, `requests`, `psycopg2-binary`.
- **config/wp-sites.yml**, **config/wp-sites.yml.example:** конфиг сайтов; секреты только из env.
- **wp/** — пакет WP Source:
  - **config.py:** загрузка YAML и кредов из env (`WP_SITE_<id>_USER`, `WP_SITE_<id>_APP_PASSWORD`), `load_sites_list` для list-sites.
  - **client.py:** `WPRestClient` — Basic Auth, timeout 30s, retries 3, rate limit (пауза 1/3 s), `get` / `get_with_headers`, retry при 429/5xx/timeout, не retry при 401/403/404.
  - **mapper.py:** маппинг API → `AuthorRow`, `TermRow`, `ContentRow`, `ContentTermRow`; post_content только из `content.rendered`; SEO из `yoast_head_json`.
  - **fetcher.py:** пагинация по users, categories, tags, posts (status=publish, _embed), pages (status=publish, _embed).
  - **storage.py:** PostgreSQL upsert по (site_id, wp_*_id), `wp_sync_runs` insert/update, connection из `WP_DATABASE_URL`/`DATABASE_URL`.
- **migrations/wp/:** DDL 001–006 (wp_sites, wp_sync_runs, wp_authors, wp_terms, wp_content, wp_content_terms).
- **wp_sync_skill.py:** CLI `list-sites`, `sync [--site SITE_ID]`; run_id, логирование, summary в stdout (JSON).
- **tests/smoke_wp.py:** unit-тесты маппинга, валидации конфига, backoff/retry.
- **README.md:** раздел «WordPress Source»; **docs/wp-source-setup.md:** настройка конфига, env, миграции; **docs/README.md:** ссылка на wp-source-setup.

## Критерии приёмки (чек-лист)

- [x] Успешный full sync одного сайта в PostgreSQL (при наличии БД и кредов).
- [x] Повторный запуск не создаёт дубликатов (upsert по PK).
- [x] Обработка 401, 429, timeout с retry/backoff в клиенте.
- [x] Логи с run_id, site_id, error_code.
- [x] TG-функционал не затронут; smoke phase1/2/3 и session_stability проходят.
- [x] WP smoke/unit из tests/smoke_wp.py проходят.

Полный diff: [2026-02-23-wp-source-stage1-mvp.diff](2026-02-23-wp-source-stage1-mvp.diff) (при наличии изменений в отслеживаемых файлах).
