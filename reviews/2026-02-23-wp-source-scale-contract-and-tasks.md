# Ревью: контракт Scale и ТЗ-пакеты S1–S5

**Дата:** 2026-02-23  
**Контекст:** добавлены контракт этапа Scale (Phase 2) и пакет ТЗ для разработчика; обновлены оглавление docs и раздел Scale в implementation-plan.

## Новые документы

- **docs/wp-source-scale-contract.md** — контракт будущих работ Scale:
  - Совместимость: MVP JSON/БД не ломаем, новые поля только additive.
  - Флаги: `WP_CONTENT_MODE`, `WP_SYNC_MODE`, `WP_GUTENBERG_PARSE`.
  - БД: `post_content_raw`, `gutenberg_blocks_json`, таблица `wp_sync_state`.
  - JSON v2: additive поля в документе и summary (`sync_mode`, `watermark`).
  - Коды ошибок: `WP_INCREMENTAL_STATE_ERROR`, `WP_RAW_CONTENT_FORBIDDEN`.
  - Критерии приёмки: full = MVP по данным, incremental без дублей, откат флагов = MVP.

- **docs/wp-source-scale-tasks.md** — ТЗ-пакеты:
  - **S1** content.raw: context=edit, маппер, post_content_raw, DoD (unit rendered/raw/both, integration, нет регрессии MVP).
  - **S2** Incremental sync: wp_sync_state, modified_after/fallback, DoD (два прогона, один изменённый пост, идемпотентность).
  - **S3** Gutenberg: парсинг raw comments, gutenberg_blocks_json, DoD (unit блоки, неуспешный парсинг не валит sync).
  - **S4** Performance: батч upsert, параллельность по сайтам, индексы, DoD (замеры, нет роста 429/timeout).
  - **S5** OpenClaw: команда, exit codes, stdout summary, cron/retry, DoD (job успешный/partial, логи/алерты).

## Изменённые файлы

- **docs/README.md** — секция «WordPress Source — Scale (Phase 2)» со ссылками на scale-contract и scale-tasks.
- **docs/wp-source-implementation-plan.md** — раздел «4. Этап Scale» переписан со ссылками на контракт и ТЗ, перечислены S1–S5.

Полный diff: [2026-02-23-wp-source-scale-contract-and-tasks.diff](2026-02-23-wp-source-scale-contract-and-tasks.diff).
