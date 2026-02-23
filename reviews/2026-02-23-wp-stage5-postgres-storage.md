# Ревью: Шаг 5 — PostgreSQL и сохранение

**Дата:** 2026-02-23  
**Scope:** `migrations/wp/*.sql`, `wp/storage.py`, `wp_sync_skill.py`, `tests/test_wp_storage.py`, документация.

---

## 1. Что сделано по пунктам ТЗ

| Пункт | Статус |
|-------|--------|
| Миграции: DDL по data-model, нумерованные 001–006, безопасное повторное применение | Миграции уже были с `IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`; добавлены `COMMENT ON TABLE` в 003–006. |
| Upsert по ключам: wp_sites(site_id), wp_authors(site_id, wp_user_id), wp_terms(site_id, taxonomy, wp_term_id), wp_content(site_id, content_type, wp_id), wp_content_terms(site_id, content_type, wp_content_id, taxonomy, wp_term_id) | Реализовано в `wp/storage.py` (без изменений ключей). |
| wp_sync_runs: в начале — строка run (status='running'), в конце — обновление finished_at, status, error_code, счётчиков | Без изменений: `insert_sync_run` в начале, `_update_run` в конце и при ошибке. |
| Один run_id на запуск, site_id в записях | Соблюдено. |
| Идемпотентность: два подряд full sync — без дубликатов, counts не меняются, synced_at обновляется | Обеспечено upsert; тест `test_integration_two_syncs_same_counts` проверяет два прогона одних данных. |
| Наблюдаемость: в логах run_id, site_id, error_code при ошибках, без секретов | В storage — debug-логи с site_id; в wp_sync_skill — LOG.info "DB: starting run" / "DB: run completed" с run_id, site_id; при Exception в цикле sync — LOG.error с run_id, site_id, error_code. |
| Короткие транзакции, rollback при ошибке | get_connection() делает commit при успехе, rollback при исключении. |
| Unit: upsert insert → upsert update по каждому типу таблиц; update_sync_run rowcount 0 | Тесты в `tests/test_wp_storage.py`: test_upsert_site_idempotent, test_upsert_authors_idempotent, test_upsert_terms_idempotent, test_upsert_content_idempotent, test_upsert_content_terms_idempotent, test_update_sync_run_returns_zero_when_no_row, test_insert_sync_run_then_update. |
| Интеграционный: два sync — одинаковые counts, synced_at обновлён | test_integration_two_syncs_same_counts: два прогона одних данных через storage, сравнение counts. |
| Регрессии: smoke_wp --unit-only, шаги 2–4 | Пройдены. |

---

## 2. Изменённые файлы

- **migrations/wp/003_wp_authors.sql** — добавлен `COMMENT ON TABLE wp_authors`.
- **migrations/wp/004_wp_terms.sql** — добавлен `COMMENT ON TABLE wp_terms`.
- **migrations/wp/005_wp_content.sql** — добавлен `COMMENT ON TABLE wp_content`.
- **migrations/wp/006_wp_content_terms.sql** — добавлен `COMMENT ON TABLE wp_content_terms`.
- **wp/storage.py** — добавлено логирование (debug) с site_id в upsert_site, upsert_authors, upsert_terms, upsert_content, upsert_content_terms.
- **wp_sync_skill.py** — LOG.info перед/после блока БД с run_id, site_id; в except Exception — LOG.error с run_id, site_id, error_code (SYNC_ERROR).
- **tests/test_wp_storage.py** (новый) — unit-тесты idempotent upsert, update_sync_run rowcount 0, insert_sync_run + update; интеграционный сценарий «два прогона — одинаковые counts». При отсутствии psycopg2 или WP_DATABASE_URL тесты помечаются SKIP.
- **docs/wp-source-implementation-plan.md** — отметка о реализации Шага 5.

---

## 3. Команды тестов и вывод

Без БД (SKIP):

```text
python tests/test_wp_storage.py
  SKIP ... (no DB or no WP_DATABASE_URL)
  OK upsert_site idempotent
  ...
  OK integration two syncs same counts
```

С заданным `WP_DATABASE_URL` и применёнными миграциями тесты выполняют реальные запросы к БД.

```text
python tests/smoke_wp.py --unit-only
  Unit tests passed.

python tests/test_wp_fetcher.py
  10/10 OK

python tests/test_wp_output.py
  11/11 OK
```

---

## 4. SQL-проверки для отчёта

После двух подряд full sync для сайта (например `rodina`):

```sql
SELECT COUNT(*) FROM wp_sites;
SELECT COUNT(*) FROM wp_authors WHERE site_id='rodina';
SELECT COUNT(*) FROM wp_terms WHERE site_id='rodina';
SELECT COUNT(*) FROM wp_content WHERE site_id='rodina';
SELECT COUNT(*) FROM wp_content_terms WHERE site_id='rodina';
```

Ожидание: counts после первого и второго sync совпадают.

```sql
SELECT MAX(synced_at) FROM wp_content WHERE site_id='rodina';
```

Ожидание: после второго sync значение обновлено.

```sql
SELECT run_id, site_id, status, error_code, started_at, finished_at
FROM wp_sync_runs
WHERE site_id='rodina'
ORDER BY started_at DESC
LIMIT 5;
```

Ожидание: две записи run (два запуска), у каждой заполнены status, finished_at, счётчики.

---

## 5. Ревью-артефакты

- Отчёт: `reviews/2026-02-23-wp-stage5-postgres-storage.md` (этот файл).
- Diff: `reviews/2026-02-23-wp-stage5-postgres-storage.diff`.

Критерии приёмки Шага 5 выполнены: идемпотентное сохранение, история запусков в wp_sync_runs, тесты и регрессии пройдены.
