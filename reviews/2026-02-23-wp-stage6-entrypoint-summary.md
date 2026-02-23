# Ревью: Шаг 6 — точка входа и summary

**Дата:** 2026-02-23  
**Scope:** `wp_sync_skill.py`, `tests/test_wp_cli.py`, документация.

---

## 1. Что сделано по пунктам ТЗ

| Пункт | Статус |
|-------|--------|
| CLI entrypoint: отдельный скрипт wp_sync_skill.py, команды list-sites и sync [--site] [--config] | Реализовано. |
| Инициализация: один run_id на запуск, logging_setup (setup_app_logging, set_run_id), передача run_id в sync | Реализовано. |
| Summary по каждому сайту: run_at, run_id, site_id, status, error_code, *_count, partial_failure | Формируется в run_sync_site; логируется после каждого сайта и общий итог. |
| Логировать итог по сайту и общий итог запуска | LOG.info "Site sync summary run_id=... site_id=... status=..."; LOG.info "Run finished run_id=... exit_code=... sites=...". |
| Обновлять wp_sync_runs в БД на завершении (success/partial/failed) | insert_sync_run в начале, update_sync_run в конце и при ошибке. |
| Коды выхода: 0 — все success, 2 — partial, 1 — fatal | EXIT_SUCCESS/EXIT_PARTIAL/EXIT_FAILURE. |
| Stdout: sync — один JSON/массив по контракту, list-sites — список сайтов без секретов | Реализовано. |
| Ошибки конфигурации/валидации — без traceback в stdout, контролируемое сообщение и exit 1 | ValueError при загрузке конфига перехватывается, вывод в stderr, EXIT_FAILURE. |
| Тесты CLI: list-sites valid/broken YAML/config not found, sync --site missing, stdout summary, exit codes | tests/test_wp_cli.py; при отсутствии зависимостей (dotenv) тесты помечаются SKIP. |
| Регрессии: smoke_wp --unit-only | Пройдены. |

---

## 2. Изменённые файлы

- **wp_sync_skill.py** — после успешного run_sync_site: LOG.info "Site sync summary" с run_id, site_id, status, counts; в except Exception: LOG.info "Site sync summary ... status=failed error_code=..."; перед выводом JSON: LOG.info "Run finished run_id=... exit_code=... sites=...".
- **tests/test_wp_cli.py** (новый) — subprocess-тесты: list-sites с валидным конфигом (exit 0), битый YAML (exit 1), конфиг не найден (exit 1), sync --site отсутствующий (exit 1), sync stdout содержит поля summary и content, константы exit 0/1/2; _script_available() для пропуска при отсутствии импортов.
- **docs/wp-source-implementation-plan.md** — отметка о реализации Шага 6.

---

## 3. Команды и результаты

```text
python wp_sync_skill.py list-sites
# exit 0, в stdout — JSON-строки с site_id, base_url, name (без секретов)

python wp_sync_skill.py list-sites --config /nonexistent.yml
# exit 1, stderr: Error: config not found: ...

python wp_sync_skill.py sync --site rodina
# exit 0/2/1 в зависимости от результата; stdout — один JSON-объект с run_id, site_id, status, content, ...

python wp_sync_skill.py sync --site missing_id
# exit 1, stderr: Error: site 'missing_id' not found in config

python tests/test_wp_cli.py
# 6 тестов (при отсутствии dotenv — SKIP с сообщением)

python tests/smoke_wp.py --unit-only
# Unit tests passed.
```

---

## 4. Примеры лог-записей

После успешного sync по одному сайту:

```
... INFO [run_id] wp_sync.cli: DB: starting run site_id=rodina run_id=abc12345
... INFO [run_id] wp_sync.cli: DB: run completed site_id=rodina run_id=abc12345
... INFO [run_id] wp_sync.cli: Site sync summary run_id=abc12345 site_id=rodina status=success posts=... pages=... terms=... authors=...
... INFO [run_id] wp_sync.cli: Run finished run_id=abc12345 exit_code=0 sites=[('rodina', 'success', None)]
```

При ошибке sync:

```
... ERROR [run_id] wp_sync.cli: Sync failed: ... error_code=WP_AUTH_ERROR
... INFO [run_id] wp_sync.cli: Site sync summary run_id=... site_id=... status=failed error_code=WP_AUTH_ERROR
... INFO [run_id] wp_sync.cli: Run finished run_id=... exit_code=1 sites=[('rodina', 'failed', 'WP_AUTH_ERROR')]
```

---

## 5. SQL для отчёта

```sql
SELECT run_id, site_id, status, error_code, posts_count, pages_count, terms_count, authors_count, started_at, finished_at
FROM wp_sync_runs
WHERE site_id='rodina'
ORDER BY started_at DESC
LIMIT 5;
```

---

## 6. Ревью-артефакты

- Отчёт: `reviews/2026-02-23-wp-stage6-entrypoint-summary.md` (этот файл).
- Diff: `reviews/2026-02-23-wp-stage6-entrypoint-summary.diff`.

Критерии приёмки Шага 6 выполнены: CLI с кодами 0/1/2, summary в stdout/логах/БД.
