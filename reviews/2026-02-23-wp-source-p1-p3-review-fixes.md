# Ревью: исправления P1–P3 по WP Source (Stage 1)

**Дата:** 2026-02-23  
**Контекст:** Вердикт ревью — No-Go из-за двух P1; после правок — Go на боевой прогон.

## Внесённые изменения

### [P1] Потеря записи в wp_sync_runs при ошибках синка

- **wp_sync_skill.py:** `run_sync_site` перестроен:
  - Отдельная короткая транзакция в начале: `upsert_site` + `insert_sync_run`, commit сразу (запись о run всегда фиксируется).
  - Все сетевые вызовы (`fetch_users`, `fetch_*`) выполняются **вне** транзакции БД.
  - Короткие транзакции на запись: по одной на `upsert_authors`, `upsert_terms`, блок posts+content_terms, блок pages+content_terms.
  - Финальное обновление run через `_update_run(status, error_code)` в отдельном соединении; при `WPClientError` вызывается `_update_run("failed"|"partial", error_code)` — строка run уже есть в БД.
- **wp/storage.py:** `update_sync_run` возвращает `cur.rowcount`; в CLI при `rowcount == 0` пишется предупреждение в лог.

### [P1] Необработанный YAML parse error

- **wp/config.py:** В `load_sites_yaml` обёрнут `yaml.safe_load` в `try/except yaml.YAMLError` → проброс `ValueError` с текстом «Ошибка разбора YAML в …». Повторное чтение YAML в `load_config` (глобальные параметры) тоже в `try/except yaml.YAMLError` → `ValueError`.
- **wp_sync_skill.py:** В `run_list_sites` и `run_sync` перехват `ValueError` при загрузке конфига: лог с `error_code=CONFIG_ERROR`, вывод в stderr, выход с `EXIT_FAILURE` без traceback.

### [P2] Длинная транзакция БД на время сетевых вызовов

- Уже закрыто правками P1: fetch выполняется вне `get_connection()`, транзакции только на upsert и на insert/update sync run.

### [P3] Документация по версии WordPress

- **docs/wp-source-setup.md:** «5.6+» заменено на «6.0+» (в соответствии с api-mapping и risks).

### [P3] Smoke-тест зависит от локального конфига

- **tests/smoke_wp.py:** Тест `test_load_sites_list_no_creds` заменён на `test_load_sites_list_valid_yaml`: используется временный YAML-fixture (tempfile), а не `config/wp-sites.yml`. Добавлен тест `test_load_sites_yaml_invalid_raises_value_error`: битый YAML приводит к `ValueError` с сообщением про YAML/разбор.

## Проверки

- `tests/smoke_wp.py --unit-only` — 11 тестов, все проходят.
- `tests/smoke_phase1.py --unit-only`, `tests/smoke_phase3.py` — без регрессии.

Полный diff: [2026-02-23-wp-source-p1-p3-review-fixes.diff](2026-02-23-wp-source-p1-p3-review-fixes.diff).
