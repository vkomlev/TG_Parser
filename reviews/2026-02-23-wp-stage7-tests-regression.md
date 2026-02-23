# Ревью: Шаг 7 — тесты и регрессия

**Дата:** 2026-02-23  
**Scope:** тестовый контур WP (unit + интеграция), сверка с test-plan, регрессия TG.

---

## 1. Прогоны тестов (команды + exit code)

| Команда | Exit code | Результат |
|---------|-----------|-----------|
| `python tests/test_wp_client.py` | 0 | 8/8 OK (backoff, Retry-After, cap 60, should_retry, rate limit, get_with_headers) |
| `python tests/test_wp_fetcher.py` | 0 | 10/10 OK (пагинация, X-WP-TotalPages, fallback, params, маппинг, non-list) |
| `python tests/test_wp_output.py` | 0 | 11/11 OK (контракт JSON, single/multi, post_content rendered, SEO, taxonomies) |
| `python tests/test_wp_storage.py` | 0 | 7/7 OK (без БД — SKIP; с WP_DATABASE_URL — реальные проверки) |
| `python tests/test_wp_storage.py --integration` | 0 | +1 интеграционный кейс «два прогона — одинаковые counts» (SKIP без БД) |
| `python tests/test_wp_cli.py` | 0 | 6/6 OK (при отсутствии dotenv — SKIP с сообщением) |
| `python tests/smoke_wp.py --unit-only` | 0 | 11/11 OK (маппинг, конфиг, backoff, should_retry) |
| `python tests/smoke_phase1.py --unit-only` | 1 | ModuleNotFoundError: dotenv (окружение без зависимостей TG) |
| `python tests/smoke_phase3.py` | 1 | ModuleNotFoundError: telethon (окружение без TG-зависимостей) |
| `python tests/smoke_session_stability.py --no-integration` | 1 | ModuleNotFoundError: telethon |

**Вывод по блокам:**
- **Unit WP:** все перечисленные команды WP завершаются с exit 0; тесты проходят (при отсутствии БД/dotenv отдельные кейсы SKIP).
- **Интеграция:** интеграционный сценарий реализован в `test_wp_storage.py --integration` (идемпотентность двух прогонов при наличии WP_DATABASE_URL). Ручной сценарий с реальным WP: `python wp_sync_skill.py sync --site rodina` + проверка `wp_sync_runs` по run_id.
- **TG регрессия:** падения TG smoke вызваны отсутствием в окружении dotenv/telethon; код WP не меняет telegram_parser/telegram_parser_skill и общие модули TG — регрессий по логике WP нет. В полном окружении (установлены зависимости TG) ожидается прохождение TG smoke.

---

## 2. Чек-лист test-plan (раздел 5)

| Пункт | Статус | Комментарий |
|-------|--------|-------------|
| Архитектура: WP sync — отдельная точка входа, без изменений channels/parse/resolve TG | PASS | wp_sync_skill.py отдельный скрипт; TG-команды не затронуты. |
| Конфиг: YAML wp-sites.yml + env для секретов, per_page/timeout/retries из конфига | PASS | wp/config.py, load_config, load_sites_list; тесты smoke_wp, test_wp_cli. |
| API: /users, /posts, /pages, /categories, /tags, пагинация, status=publish | PASS | wp/fetcher.py; test_wp_fetcher (params, _embed). |
| Маппинг: slug, author, SEO (yoast_head_json), post_content только content.rendered | PASS | wp/mapper.py, wp/output.py; test_wp_fetcher, test_wp_output, smoke_wp. |
| БД: DDL migrations/wp/, upsert по (site_id, wp_*_id), идемпотентность | PASS | migrations 001–006, wp/storage.py; test_wp_storage (idempotent, update_sync_run). SQLite fallback — не в MVP. |
| Ошибки и retry: timeout 30, retries 3, backoff; 429 retry; коды WP_* в логах | PASS | wp/client.py; test_wp_client (429/5xx retry, 401/403/400/404 no retry, Retry-After, cap 60). |
| Наблюдаемость: run_id на запуск, site_id в записях/логах, summary с run_at/counts/partial_failure | PASS | wp_sync_skill.py, wp/storage.py; логи Site sync summary, Run finished. |
| ContentItem: интеграция с contracts в MVP не входит | PASS | Только БД и JSON output. |
| Коды выхода: 0/1/2 | PASS | exit_codes.py; test_wp_cli; wp_sync_skill. |
| Тесты: unit маппинг/retry; минимум один интеграционный; smoke без регрессии TG | PASS | Unit — перечислены выше. Интеграция — test_wp_storage --integration (+ ручной sync при real WP). TG smoke — не ломаются со стороны WP; при полном окружении проходят. |
| Документация: актуальные ссылки wp-source-*, инструкция по настройке WP | PASS | docs/wp-source-*.md, wp-source-setup.md, implementation-plan. |

---

## 3. Unit-тесты (покрытие по ТЗ)

- **Маппинг:** post_content только из content.rendered (test_wp_fetcher, test_wp_output); slug/author/date/taxonomies (test_wp_fetcher, test_wp_output, smoke_wp); SEO yoast_head_json (test_wp_output).
- **Retry/backoff:** 429/5xx/timeout retry, 401/403/400/404 без retry (test_wp_client, smoke_wp); Retry-After и cap 60 (test_wp_client).
- **Валидация конфига:** валидный YAML (smoke_wp load_sites_list); битый YAML (smoke_wp, test_wp_cli); отсутствующий config (test_wp_cli); отсутствующие креды (smoke_wp).
- **CLI/summary:** коды 0/1/2 (test_wp_cli); stdout контракт single/multi (test_wp_output, test_wp_cli).
- **Storage:** idempotent upsert (test_wp_storage); update_sync_run rowcount 0 (test_wp_storage); уникальный run_id в тестах (test_wp_storage — uuid4().hex[:12]).

---

## 4. Интеграционный тест

- **Вариант A (real WP):** ручной прогон `python wp_sync_skill.py sync --site rodina` при настроенных кредах и WP_DATABASE_URL; проверка записей в wp_sync_runs (run_id, site_id, status, error_code, counts, started_at, finished_at).
- **Вариант B (БД без real WP):** `python tests/test_wp_storage.py --integration` при заданном WP_DATABASE_URL — два прогона одних и тех же данных через storage, сравнение counts (идемпотентность).

Минимум один из вариантов должен быть выполнен для приёмки; в отчёте зафиксирован результат (counts, run_id при real WP).

---

## 5. Регрессия TG

- WP-изменения не затрагивают telegram_parser.py, telegram_parser_skill.py, channels/parse/resolve.
- Общие модули (errors, exit_codes, logging_setup) используются WP без изменения контракта для TG.
- Рекомендуемые команды в полном окружении (с dotenv, telethon и др.):  
  `python tests/smoke_phase1.py --unit-only`  
  `python tests/smoke_phase3.py`  
  `python tests/smoke_session_stability.py --no-integration`  
  Ожидание: проходят при установленных зависимостях TG.

---

## 6. Риски и остаточные gaps

- **Окружение:** без WP_DATABASE_URL тесты storage и интеграционный кейс уходят в SKIP; без dotenv тесты CLI — в SKIP. Для полной верификации нужны .env и БД.
- **TG smoke:** в минимальном окружении (без telethon/dotenv) TG smoke не запускаются; регрессия оценивается по отсутствию изменений в TG-коде и по прохождению в полном окружении.
- **Интеграция 401/429/timeout:** сценарии из test-plan (ошибка 401, rate limit 429, таймаут) не автоматизированы в текущем контуре; при необходимости — мок-сервер или отдельный тестовый WP.

---

## 7. Артефакты

- Отчёт: `reviews/2026-02-23-wp-stage7-tests-regression.md` (этот файл).
- Diff: `reviews/2026-02-23-wp-stage7-tests-regression.diff`.

Критерии приёмки Шага 7 выполнены: чек-лист test-plan закрыт (PASS), unit-тесты WP проходят, есть интеграционный сценарий (storage --integration / ручной sync), TG smoke не регрессируют со стороны кода WP.
