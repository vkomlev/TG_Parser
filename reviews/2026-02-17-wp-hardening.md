# Ревью: WP Source Hardening (после MVP)

**Дата:** 2026-02-17

## Цель этапа

Укрепить WP Source для стабильной эксплуатации: мультисайт, fallback на SQLite, расширенная документация и интеграционные проверки.

---

## 1. Мультисайт

- **sync без --site** — проходит по всем сайтам из `config/wp-sites.yml`.
- **Один run_id** на весь запуск.
- **site_id** в каждой записи summary, в лог-событиях WP и в БД (`wp_sync_runs` и остальных таблицах).
- **Агрегированный summary в stdout:** при одном сайте — один объект; при 2+ сайтах — один объект с полями `run_id`, `status` (success/partial/failed), `totals` (sites, success, failed, posts_count, pages_count, terms_count, authors_count), `sites` (массив per-site объектов).
- **Коды выхода:** 0 — все success; 2 — partial; 1 — все failed / config fatal.

**Изменённые файлы:** `wp/output.py` (`build_multisite_aggregated`), `wp_sync_skill.py` (вывод при `len(site_outputs) > 1`).

---

## 2. SQLite fallback

- **Включение:** автоматически при недоступности PostgreSQL; явно — `WP_STORAGE_BACKEND=sqlite` или в конфиге `storage_backend: sqlite`.
- **Абстракция backend в storage:** `wp/storage.py` — выбор backend по env/конфигу (ленивая инициализация), делегирование в Postgres или `wp/storage_sqlite.py`. Единый контракт: `get_connection()`, `upsert_site`, `upsert_authors`, `upsert_terms`, `upsert_content`, `upsert_content_terms`, `insert_sync_run`, `update_sync_run`.
- **DDL для SQLite:** `migrations/wp/sqlite/` (001–006): типы адаптированы (TIMESTAMPTZ→TEXT, JSONB→TEXT), AUTOINCREMENT, индексы и уникальные ключи; применение при первом подключении (строки-комментарии в SQL отбрасываются перед выполнением).
- **Идемпотентность:** повторный sync не создаёт дубликатов (ON CONFLICT DO UPDATE).

**Изменённые/новые файлы:** `wp/storage.py` (фасад, ленивый импорт psycopg2, делегирование по типу conn), `wp/storage_sqlite.py` (новый), `wp/config.py` (опция `storage_backend`), `wp_sync_skill.py` (установка `WP_STORAGE_BACKEND` из конфига перед sync).

---

## 3. Документация

- **README.md** — секция WordPress Source: мультисайт, хранилище Postgres/SQLite, переменные `WP_STORAGE_BACKEND`, `WP_STORAGE_PATH`, команды, коды выхода.
- **docs/wp-source-setup.md** — пошагово Application Password; пример конфига для multisite; переменные окружения (WP_SITE_*_USER, *_APP_PASSWORD, WP_DATABASE_URL, WP_STORAGE_BACKEND, WP_STORAGE_PATH); как работает fallback Postgres→SQLite; команды single/multi-site; разбор 401/429/timeout.
- **docs/wp-source-implementation-plan.md** — блок «Реализовано (Hardening)» в разделе 3.

---

## 4. Тесты

- **test_wp_storage.py** — поддержка SQLite: `_skip_no_db()` не пропускает тесты при `WP_STORAGE_BACKEND=sqlite`; `_count()` и `_fetch_one()` работают с обоими типами conn (placeholder `%s` vs `?`).
- **Интеграция:** два прогона одних данных на SQLite — одинаковые counts (`python tests/test_wp_storage.py --integration` при `WP_STORAGE_BACKEND=sqlite`).
- **smoke_wp в CI** — не добавлен (по ограничению «нет в наличии»); подготовлена инструкция для включения позже: `docs/wp-source-ci-smoke-job.md`.

**Минимальный набор команд для отчёта:**

```powershell
python wp_sync_skill.py list-sites
python wp_sync_skill.py sync
python wp_sync_skill.py sync --site rodina

python tests/test_wp_client.py
python tests/test_wp_fetcher.py
python tests/test_wp_output.py
python tests/test_wp_storage.py
python tests/test_wp_storage.py --integration
python tests/test_wp_cli.py
python tests/smoke_wp.py --unit-only
```

**Режим SQLite:**

```powershell
$env:WP_STORAGE_BACKEND = "sqlite"
$env:WP_DATABASE_URL = ""
python tests/test_wp_storage.py
python tests/test_wp_storage.py --integration
```

---

## Риски и пробелы

- При первом импорте `wp.storage` без `WP_STORAGE_BACKEND` и без `WP_DATABASE_URL` сразу выбирается SQLite; при наличии URL выполняется одна попытка подключения к Postgres — при медленной сети возможна задержка старта.
- ~~Интеграционные сценарии 401/429/timeout~~ — закрыто доработкой ниже.

---

## Доработки по вердикту (P1/P2)

1. **Политика fallback (P1):** добавлена переменная `WP_STORAGE_FALLBACK` (`auto` | `off`). По умолчанию `off` — при недоступности Postgres sync завершается с ошибкой (fail fast). При `WP_STORAGE_FALLBACK=auto` — прежнее поведение (переход на SQLite с предупреждением). Реализация: `wp/storage.py` (`STORAGE_FALLBACK_ENV`, логика в `_resolve_backend()`). Документация: README, docs/wp-source-setup.md.

2. **Приоритет конфига (P2):** при наличии `storage_backend` в YAML он **переопределяет** переменную окружения `WP_STORAGE_BACKEND` на время запуска sync (в `wp_sync_skill.py` используется присваивание `os.environ[STORAGE_BACKEND_ENV] = cfg.storage_backend`, а не `setdefault`). В docs/wp-source-setup.md добавлено явное описание приоритета.

3. **Интеграционные сценарии 401/429/timeout (P1):** добавлен файл `tests/test_wp_integration_http_failures.py` с локальным mock HTTP server (стандартный `http.server.HTTPServer` в потоке). Сценарии: 401 → `WPClientError` с `error_code=WP_AUTH_ERROR`, `status_code=401`; 429 с Retry-After → после retry успешный 200; 429 все попытки → `WP_RATE_LIMIT`; timeout → `WP_NETWORK_ERROR`. Запуск: `python tests/test_wp_integration_http_failures.py`.

---

## Перечень изменённых файлов

| Файл | Изменения |
|------|-----------|
| `wp/output.py` | Уже было: `build_multisite_aggregated` |
| `wp_sync_skill.py` | Вывод агрегата при 2+ сайтах; импорт `STORAGE_BACKEND_ENV`; установка env из конфига перед sync |
| `wp/storage.py` | Backend postgres/sqlite, ленивая инициализация, делегирование по типу conn, ленивый импорт psycopg2 |
| `wp/storage_sqlite.py` | Новый модуль: get_connection, _ensure_schema, upsert_*, insert_sync_run, update_sync_run |
| `wp/config.py` | Поле `storage_backend` в WPSyncConfig, чтение из YAML |
| `migrations/wp/sqlite/*.sql` | Уже было: 001–006 |
| `tests/test_wp_storage.py` | _skip_no_db при sqlite, _count/_fetch_one для SQLite и Postgres |
| `README.md` | Секция WordPress Source: мультисайт, SQLite, команды, коды выхода |
| `docs/wp-source-setup.md` | Multisite пример, переменные, fallback, Application Password пошагово, 401/429/timeout |
| `docs/wp-source-implementation-plan.md` | Блок «Реализовано (Hardening)» |
| `docs/wp-source-ci-smoke-job.md` | Новый: шаблон job/инструкция для smoke_wp в CI |
| `tests/test_wp_integration_http_failures.py` | Новый: интеграционные тесты 401, 429 (retry + exhausted), timeout с mock HTTP server |
| `wp/storage.py` (доработка) | `WP_STORAGE_FALLBACK=auto` или `off`, по умолчанию off — fail fast при недоступности Postgres |
| `wp_sync_skill.py` (доработка) | Приоритет конфига: YAML переопределяет env (`os.environ[KEY]=cfg.storage_backend`) |
