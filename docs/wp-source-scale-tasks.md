# WordPress Source — ТЗ-пакеты этапа Scale (S1–S5)

**Дата:** 2026-02-23  
**Связанные документы:** [wp-source-scale-contract](wp-source-scale-contract.md), [wp-source-implementation-plan](wp-source-implementation-plan.md)

Задачи можно запускать по мере необходимости; порядок S1→S2→… рекомендован, но S3 и S4 при необходимости допускают параллелизацию с S1/S2.

---

## S1. content.raw (Phase 2)

**Цель:** поддержать `context=edit` и сохранение сырого редакторского контента.

### Scope

- **Клиент:** опциональный запрос с параметром `context=edit` при `WP_CONTENT_MODE=raw` или `both` (чтение `content.raw` и при необходимости `excerpt.raw` из ответа API).
- **Mapper:** при `WP_CONTENT_MODE=raw` или `both` брать `content.raw` (и при наличии `excerpt.raw`); при недоступности raw логировать предупреждение и при необходимости выставлять `WP_RAW_CONTENT_FORBIDDEN` в summary при полном отказе по сайту.
- **Storage:** новое поле `wp_content.post_content_raw` (TEXT или выбранный тип); заполнять при наличии raw из маппера.
- **Output:** в едином JSON output добавить поле `post_content_raw` (nullable); при режиме `rendered` поле отсутствует или null.

### DoD

- Unit-тесты: режимы `rendered` / `raw` / `both` (маппинг и наличие/отсутствие полей в выходе).
- Integration: синк с тестовым сайтом, где доступен `context=edit`; в БД и JSON присутствует `post_content_raw`.
- Регрессия MVP: при `WP_CONTENT_MODE=rendered` (или по умолчанию) поведение и объём данных идентичны текущему MVP.

### Зависимости

- Контракт: [wp-source-scale-contract](wp-source-scale-contract.md) (флаг `WP_CONTENT_MODE`, БД `post_content_raw`, JSON v2).
- Миграция: `migrations/wp/` — добавление колонки `post_content_raw` в `wp_content`.

---

## S2. Incremental sync

**Цель:** синхронизировать только изменённые записи по watermark.

### Scope

- **Режим:** при `WP_SYNC_MODE=incremental` использовать таблицу `wp_sync_state` (site_id, last_modified_gmt, last_run_id, updated_at).
- **Стратегия запросов:** по возможности запросы к API с фильтром `modified_after` (или аналог в WP REST API); при недоступности — fallback: обход по страницам с фильтрацией по дате изменения на стороне клиента или выборочная выгрузка по известным id.
- **Watermark:** после успешного incremental run обновлять `wp_sync_state` (last_modified_gmt по последнему изменённому объекту, last_run_id, updated_at).
- **Full sync остаётся доступным:** при `WP_SYNC_MODE=full` поведение как в MVP (полная выгрузка без использования wp_sync_state для отсечения).

### DoD

- Два последовательных прогона incremental без изменений на WP: второй прогон практически пустой по новым данным; дубликатов в БД нет.
- После изменения одного поста на WP в следующем incremental забирается только он (или минимально необходимый набор); в БД обновляется одна запись (и при необходимости связанные terms/authors).
- Идемпотентность: повторный запуск incremental с теми же данными не создаёт дублей.
- В summary присутствуют `sync_mode=incremental` и при необходимости `watermark`.

### Зависимости

- Контракт: таблица `wp_sync_state`, флаг `WP_SYNC_MODE`, коды ошибок `WP_INCREMENTAL_STATE_ERROR`.
- Миграция: создание таблицы `wp_sync_state` в `migrations/wp/`.

---

## S3. Gutenberg raw comments (basic)

**Цель:** извлекать структуру блоков Gutenberg из сырого контента и сохранять в БД/JSON.

### Scope

- **Парсинг:** разбор комментариев вида `<!-- wp:blockname ... -->` и закрывающих `<!-- /wp:blockname -->` в `post_content` или `post_content_raw`; формирование структуры блоков (имя, атрибуты, вложенность при необходимости).
- **Сохранение:** поле `wp_content.gutenberg_blocks_json` (JSONB/TEXT); в JSON output — поле `gutenberg_blocks` (nullable).
- **Флаг:** включение парсинга только при `WP_GUTENBERG_PARSE=basic`.
- **Устойчивость:** при неуспешном парсинге (битый фрагмент, неожиданная структура) — запись warning в лог, в БД/JSON — null или пустой массив; sync не падает.

### DoD

- Unit-тесты на типовые блоки: paragraph, image, embed, core/block (reusable) — корректное извлечение имени и атрибутов.
- Неуспешный парсинг (например обрезанный комментарий) не валит sync: в логе warning, в выходе null/пусто.
- При `WP_GUTENBERG_PARSE=off` парсинг не выполняется, поле в JSON/БД отсутствует или null (совместимость с MVP).

### Зависимости

- Контракт: поле `gutenberg_blocks_json` в `wp_content`, поле `gutenberg_blocks` в JSON v2, флаг `WP_GUTENBERG_PARSE`.
- Миграция: добавление колонки `gutenberg_blocks_json` в `wp_content` (если ещё не добавлена в рамках другой задачи).
- Опционально: S1 (raw) даёт больше сырого контента для парсинга, но парсинг может работать и от `post_content` (rendered), если структура комментариев сохранена.

---

## S4. Performance

**Цель:** ускорение sync без потери стабильности и без изменения контракта данных.

### Scope

- **Батч upsert:** группировка вставок/обновлений в authors, terms, content, content_terms батчами (размер батча конфигурируемый или по умолчанию из контракта); сокращение числа round-trip к БД.
- **Параллельность по сайтам:** при синхронизации нескольких сайтов — ограниченный пул параллельных потоков/задач (например 2–3 сайта одновременно); для каждого сайта по-прежнему не более 3 req/s (rate limit сохраняется).
- **Индексы:** проверка и при необходимости добавление индексов под частые аналитические запросы (например по published_at, site_id+content_type, taxonomy); только additive изменения в `migrations/wp/`.

### DoD

- Замер времени sync до и после изменений на 2+ сайтах (или на одном сайте с достаточным объёмом); фиксация результатов в отчёте или в комментарии к задаче.
- Отсутствие роста ошибок 429 и таймаутов по сравнению с текущим поведением (при тех же лимитах и объёме данных).
- Контракт данных и коды выхода не меняются; существующие тесты проходят.

### Зависимости

- Контракт: совместимость (additive), без изменения формата ответов API и JSON output.
- При необходимости — обновление документации по рекомендуемым индексам в [wp-source-data-model-postgres](wp-source-data-model-postgres.md).

---

## S5. OpenClaw orchestration

**Цель:** формальный контракт запуска для оркестратора (команда, параметры, коды выхода, формат stdout).

### Scope

- **Команда запуска:** зафиксировать точную команду (например `python wp_sync_skill.py sync [--site SITE_ID] [--config PATH]`) и переменные окружения (конфиг, креды, флаги WP_*).
- **Коды выхода:** 0 — успех, 1 — фатальная ошибка, 2 — частичный успех; документировать в одном месте (например в wp-source-setup или в scale-contract).
- **Формат stdout:** описание итогового JSON (single-site vs multi-site), обязательные поля summary для парсинга оркестратором (run_id, status, error_code, totals и т.д.).
- **Рекомендации:** рекомендуемый cron (например daily), retry policy при коде 2 и 1 (сколько повторов, интервал), маршрутизация логов и алертов.

### DoD

- Job в OpenClaw отрабатывает успешный сценарий (exit 0) и сценарий с частичным сбоем (exit 2) с корректной интерпретацией summary в stdout.
- Логи и алерты (при наличии) корректно маршрутизируются по run_id/site_id.
- Документ с контрактом запуска доступен команде и оркестратору (в репозитории или в общей wiki).

### Зависимости

- Текущая реализация CLI и формата stdout (MVP/Hardening); при необходимости расширение summary полями из scale-contract (sync_mode, watermark) без ломающих изменений.

---

## Сводка задач

| Задача | Цель | Зависимости контракта |
|--------|------|------------------------|
| S1 | content.raw | WP_CONTENT_MODE, post_content_raw, WP_RAW_CONTENT_FORBIDDEN |
| S2 | Incremental sync | WP_SYNC_MODE, wp_sync_state, WP_INCREMENTAL_STATE_ERROR |
| S3 | Gutenberg blocks | WP_GUTENBERG_PARSE, gutenberg_blocks_json / gutenberg_blocks |
| S4 | Performance | только additive индексы и батчи |
| S5 | OpenClaw | формальный контракт команд и stdout |

Реализация каждой задачи должна соответствовать [wp-source-scale-contract](wp-source-scale-contract.md) (совместимость, флаги, additive изменения, критерии приёмки).
