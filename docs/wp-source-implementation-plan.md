# WordPress Source — план внедрения

**Дата:** 2026-02-23  
**Связанные документы:** [wp-source-architecture](wp-source-architecture.md), [wp-source-test-plan](wp-source-test-plan.md), [wp-source-risks-and-open-questions](wp-source-risks-and-open-questions.md)

---

## 1. Обзор этапов

| Этап | Цель | Трудоёмкость (оценка) |
|------|------|------------------------|
| **MVP** | Рабочий full sync в PostgreSQL, один сайт, конфиг, логирование, базовые тесты | 5–8 дн. |
| **Hardening** | Мультисайт, SQLite fallback, улучшение тестов и документации | 2–3 дн. |
| **Scale** | Оптимизация, инкремент (опционально), расширение SEO/Gutenberg | по необходимости |

---

## 2. Этап MVP (пошагово)

### Шаг 1. Инфраструктура и конфиг (0.5–1 дн.)
- Добавить в `errors.py` коды WP_AUTH_ERROR, WP_RATE_LIMIT, WP_NETWORK_ERROR, WP_DATA_FORMAT_ERROR (или зафиксировать использование общих кодов).
- **Конфиг (зафиксировано):** YAML `config/wp-sites.yml` — список сайтов (site_id, base_url, name); секреты (логин, Application Password) — только из переменных окружения (например по site_id: `WP_SITE_<ID>_USER`, `WP_SITE_<ID>_APP_PASSWORD` или единый набор для одного сайта в MVP).
- Создать модуль чтения конфига (например `wp/config.py`) без логики запросов.

**Критерий:** конфиг читается; при отсутствии обязательных полей — понятная ошибка и EXIT_FAILURE.

### Шаг 2. HTTP-клиент и rate limit (1–1.5 дн.)
- Реализовать клиент с таймаутом 30 с, паузой 1/3 с между запросами к одному site_id, Basic Auth.
- Обёртка запроса с retry 3 и exponential backoff; обработка 429 (Retry-After или backoff).
- Логирование каждого запроса/ошибки с run_id и error_code.

**Критерий:** unit-тесты на backoff и на решение retry/not retry; ручная проверка с реальным или мок-сервером.

**Этап 2 (HTTP-клиент production-ready):** Уточнённая реализация в `wp/client.py`: rate limit перед каждым запросом (включая retry), backoff `2^(attempt+1)` с cap 60 и учётом `Retry-After` при 429, без retry для 401/403/400/404, структурированное логирование с run_id/site_id/error_code и задержкой до повтора. Тесты: `tests/test_wp_client.py`, критерии приёмки Этапа 2 см. в ТЗ разработчику.

### Шаг 3. Fetcher: users, terms, posts, pages (1.5–2 дн.)
- Последовательные запросы к эндпоинтам с пагинацией (per_page=100, page); фильтр status=publish для posts/pages.
- По возможности использовать _embed для постов/страниц, чтобы уменьшить число запросов.
- **post_content в MVP:** сохранять только `content.rendered`; опция `context=edit` и `content.raw` — phase 2.
- Маппинг ответов в внутренние структуры (dataclass или dict) согласно [api-mapping](wp-source-api-mapping.md).

**Реализовано (2026-02-23):** `wp/fetcher.py` — пагинация по `X-WP-TotalPages` с fallback при пустой странице или невалидных заголовках; обработка ответа не-list (лог + безопасное завершение без исключения); `wp/mapper.py` без изменений. Тесты: `tests/test_wp_fetcher.py`; ревью: `reviews/2026-02-23-wp-fetcher-stage3.md`.

**Критерий:** для заданного тестового сайта получаем полный список постов и страниц; маппинг полей (slug, author, date, content) корректен.

### Шаг 4. Модель и единый JSON output (0.5 дн.)
- Финализировать структуру данных (в т.ч. SEO: yoast_head_json) и контракт единого JSON output по [data-model](wp-source-data-model-postgres.md).
- Функции преобразования: WP API response → внутренняя модель → JSON output. **Интеграция с ContentItem (contracts.py) в MVP не входит** — только экспорт в БД и JSON.

**Реализовано (2026-02-23):** Модуль `wp/output.py`: контракт документа контента (source, site_id, content_type, wp_id, slug, title, post_content, excerpt, status, author_id, published_at, modified_at, taxonomies, seo); контракт summary (run_id, site_id, status, run_at, error_code, *_count); `content_row_to_export_dict`, `build_content_export_list`, `summary_to_export_dict`, `build_single_site_output`, `build_multi_site_output`. Интеграция в `wp_sync_skill.py`: sync возвращает данные для JSON, stdout — один объект (один сайт) или массив объектов (несколько сайтов). Тесты: `tests/test_wp_output.py`. Ревью: `reviews/2026-02-23-wp-stage4-model-json.md`.

**Критерий:** unit-тесты на маппинг из фиксированных примеров API.

### Шаг 5. PostgreSQL и сохранение (1.5–2 дн.)
- Применить DDL из [data-model-postgres](wp-source-data-model-postgres.md). **Миграции:** папка `migrations/wp/` с нумерованными SQL-файлами.
- Реализовать слой сохранения: upsert в wp_sites, wp_authors, wp_terms, wp_content, wp_content_terms; запись в wp_sync_runs в начале и в конце run. В каждой записи и в логах — `site_id`; один `run_id` на весь запуск.
- Идемпотентность: повторный sync не создаёт дубликатов.

**Реализовано (2026-02-23):** Миграции `migrations/wp/001_..sql`–`006_..sql` с `IF NOT EXISTS`/`CREATE INDEX IF NOT EXISTS` и `COMMENT ON TABLE`. Слой `wp/storage.py`: upsert по заявленным ключам, `insert_sync_run`/`update_sync_run` с rowcount; логирование операций (debug) с `site_id`; короткие транзакции. В `wp_sync_skill.py`: лог "DB: starting run" / "DB: run completed" с run_id, site_id; при исключении в цикле sync — LOG.error с run_id, site_id, error_code. Тесты: `tests/test_wp_storage.py` (unit: idempotent upsert по таблицам, update_sync_run rowcount 0; интеграция: два прогона одних данных — одинаковые counts). Ревью: `reviews/2026-02-23-wp-stage5-postgres-storage.md`.

**Критерий:** интеграционный тест: два подряд full sync → одинаковое количество строк и обновлённый synced_at.

### Шаг 6. Точка входа и summary (1 дн.)
- Точка входа: отдельный скрипт `wp_sync_skill.py` (или аналог) с командой sync (и при необходимости list-sites). Генерация run_id, вызов logging_setup, передача run_id в sync.
- По завершении — формирование summary (run_at, run_id, site_id, счётчики, partial_failure, error_code) и запись в лог; обновление wp_sync_runs.
- Коды выхода: 0 / 1 / 2 по правилам проекта.

**Реализовано (2026-02-23):** CLI `wp_sync_skill.py`: команды `list-sites`, `sync [--site SITE_ID] [--config PATH]`; один run_id на запуск, логирование через logging_setup, run_id во все операции sync. Summary по каждому сайту и общий итог в логах (LOG.info "Site sync summary", "Run finished"); wp_sync_runs обновляется в начале и в конце run. Коды выхода: 0 — все success, 2 — partial, 1 — fatal (все failed или ошибка конфигурации). Stdout: sync — JSON по контракту (один объект/массив), list-sites — список сайтов без секретов. Тесты: `tests/test_wp_cli.py` (list-sites valid/broken YAML/config not found, sync --site missing, stdout summary fields, exit codes). Ревью: `reviews/2026-02-23-wp-stage6-entrypoint-summary.md`.

**Критерий:** запуск из CLI с конфигом; в логах и в БД (wp_sync_runs) виден результат.

### Шаг 7. Тесты и регрессия (1 дн.)
- Unit-тесты: маппинг, retry/backoff, валидация конфига.
- Один интеграционный тест с тестовым WP или мок-сервером.
- Запуск существующих smoke-тестов TG — убедиться в отсутствии регрессии.

**Реализовано (2026-02-23):** Тестовый контур: test_wp_client (backoff, Retry-After, cap 60, should_retry 429/5xx/401/403/400/404, rate limit), test_wp_fetcher (пагинация, маппинг, non-list), test_wp_output (контракт JSON, single/multi), test_wp_storage (idempotent upsert, update_sync_run rowcount, уникальный run_id, интеграция два прогона — одинаковые counts при --integration), test_wp_cli (list-sites/sync exit codes, stdout summary), smoke_wp --unit-only (маппинг, конфиг, backoff/retry). Интеграция: test_wp_storage.py --integration при WP_DATABASE_URL; ручной sync --site <id> для real WP. TG smoke (phase1/phase3/session_stability) требуют полного окружения (dotenv, telethon); WP-код не меняет TG entrypoints — регрессий по коду нет. Сверка с docs/wp-source-test-plan.md: отчёт reviews/2026-02-23-wp-stage7-tests-regression.md.

**Критерий:** чек-лист из [test-plan](wp-source-test-plan.md) выполнен; TG smoke проходят в полном окружении.

---

## 3. Этап Hardening (после MVP)

- **Мультисайт:** итерация по списку сайтов из конфига; один run_id на весь запуск, site_id в каждой записи/логе (зафиксировано); агрегированный summary.
- **SQLite fallback:** переключение на SQLite при недоступности PostgreSQL (или по флагу конфига); адаптация DDL (типы, автоинкремент).
- **Документация:** обновить README/docs — как создать Application Password, пример конфига, переменные окружения.
- **Тесты:** расширить интеграционные сценарии (401, 429, таймаут); добавить smoke_wp в CI при наличии.

---

## 4. Этап Scale (по необходимости)

- **content.raw (phase 2):** опция запроса с `context=edit` для получения сырого редакторского контента; сохранять в отдельное поле или заменить post_content по конфигу.
- **Инкрементальная синхронизация:** фильтр по modified_after (если API поддерживает) или кэш последнего run и запрос только изменённых id — отдельное ТЗ.
- **Gutenberg raw comments:** парсинг блоков из post_content или отдельное поле; расширение маппинга и БД.
- **Производительность:** батчинг вставок, параллельные запросы к разным сайтам (с сохранением лимита на сайт), индексы по запросам аналитики.
- **Оркестрация:** интеграция с OpenClaw (команды/триггеры) — конфиг на стороне оркестратора.

---

## 5. Риски и зависимости

- **Риски:** см. [wp-source-risks-and-open-questions](wp-source-risks-and-open-questions.md).
- **Зависимости:** доступ к тестовому WordPress с включённым REST API и Application Passwords; PostgreSQL для разработки и CI (или SQLite для unit/integration при fallback).

---

## 6. Порядок выполнения (сводка)

1. Конфиг и коды ошибок  
2. HTTP-клиент + retry + rate limit  
3. Fetcher и маппинг API → модель  
4. Контракт JSON output  
5. DDL и слой сохранения в PostgreSQL  
6. CLI и summary  
7. Unit/integration/smoke и регрессия TG  

После шага 7 — приёмка MVP по чек-листу из [test-plan](wp-source-test-plan.md).
