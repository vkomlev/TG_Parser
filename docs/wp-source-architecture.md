# WordPress Source — архитектура

**Дата:** 2026-02-23  
**Статус:** проектирование  
**Связанные документы:** [data-model-postgres](wp-source-data-model-postgres.md), [api-mapping](wp-source-api-mapping.md), [sync-strategy](wp-source-sync-strategy.md), [implementation-plan](wp-source-implementation-plan.md)

---

## 1. Executive summary

Добавляется **новый источник данных WordPress** в проект TG_Parser без изменения существующего Telegram-функционала. WP Source читает через REST API посты, страницы, таксономии и авторов (только `publish`), сохраняет редакторский контент и метаданные (slug, author, SEO) в PostgreSQL. Синхронизация на первом этапе — full sync по расписанию (daily, конфигурируемо). Оркестрация — внешняя (OpenClaw). Обратной записи в WordPress нет.

**Ключевые решения:**
- Отдельный модуль/пакет `wp_source` (или пространство имён `wp_*`) рядом с текущим ядром.
- Доступ к WP: REST API + Application Password; лимит 3 req/s на сайт, retry 3 с exponential backoff, timeout 30 s.
- Хранилище: PostgreSQL — основное; SQLite — fallback для dev/тестов.
- Единая наблюдаемость: run_id, error_code, summary в том же стиле, что и у TG парсера.

**Зафиксированные решения (до старта разработки):**
- **Конфиг:** YAML-файл `config/wp-sites.yml` (список сайтов, base_url, имена) + переменные окружения для секретов (Application Password и при необходимости логин).
- **run_id:** один на весь запуск sync; в каждой записи БД и в логах дополнительно указывается `site_id`.
- **Интеграция с ContentItem (contracts.py):** в MVP не включать; только экспорт в БД и единый JSON output. Маппинг в ContentItem — при необходимости общего пайплайна (phase 2 и далее).

---

## 2. Цели и ограничения

### 2.1 Цели
- Получать список **posts**, **pages**, **terms** (категории, теги, при необходимости custom taxonomies).
- Получать редакторский контент (`post_content`), без рендера темы.
- Сохранять данные в машиночитаемую структуру для анализа и трансформаций (БД + опционально JSON-экспорт).
- Поддержка нескольких сайтов (multisite как несколько базовых URL).

### 2.2 Зафиксированные продуктовые решения (не переопределять)
- Доступ: REST API + Application Password.
- Multisite: несколько сайтов = несколько конфигурируемых base URL.
- Статусы: только `publish`.
- Метаданные обязательно: slug, author, SEO fields (Yoast/Rank Math — что вернёт API).
- Gutenberg raw comments: не обязательны в MVP, архитектура должна допускать расширение.
- Синхронизация: full sync на первом этапе.
- Обратной записи в WP нет (только чтение/экспорт).
- Основное хранилище: PostgreSQL; SQLite только fallback/dev.
- Оркестрация по расписанию — внешняя (OpenClaw).

### 2.3 Ограничения проектирования
- Не вносить breaking changes в публичный CLI и текущие контракты TG без необходимости.
- Не добавлять в MVP: редактирование WP, async-очереди, сложную event-driven архитектуру.

---

## 3. Встраивание в текущий проект

### 3.1 Принцип
- **TG_Parser** остаётся точкой входа для Telegram-команд (`channels`, `parse`, `resolve`). Публичный CLI и контракты (`export.json`, `summary.json`, коды выхода) не меняются.
- **WordPress Source** вводится как отдельная вертикаль: свой конфиг, свои команды (или подкоманды), свой слой сохранения в БД. Общее — только инфраструктура: логирование (run_id, error_code), exit_codes, структура summary.

### 3.2 Интеграция CLI (зафиксировано)

**Отдельный скрипт точки входа:** файл `wp_sync_skill.py` (или аналог) в корне: команды вида `sync`, `sync-site`, `list-sites`. Нулевое влияние на существующий `telegram_parser_skill.py`. При желании позже можно объединить под единый launcher (отдельная задача).

### 3.3 Общие компоненты
- **errors.py** — добавить коды для WP (например `WP_AUTH_ERROR`, `WP_RATE_LIMIT`, `WP_NETWORK_ERROR`), не удаляя и не переименовывая существующие.
- **exit_codes.py** — не менять; использовать те же EXIT_SUCCESS / EXIT_FAILURE / EXIT_PARTIAL.
- **logging_setup.py** — переиспользовать; run_id передаётся в WP sync так же, как в parse.
- **Контракты:** интеграция с ContentItem (contracts.py) в MVP не входит — только экспорт в БД и единый JSON output. При необходимости общего пайплайна (TG + WP в один destination) маппинг в ContentItem добавить в phase 2.

### 3.4 Структура каталогов (предлагаемая)
```
TG_Parser/
├── config/
│   └── wp-sites.yml            # конфиг сайтов (base_url, name); секреты — в env
├── migrations/
│   └── wp/                     # DDL-миграции для таблиц WP
├── telegram_parser.py          # без изменений по функционалу
├── telegram_parser_skill.py    # без изменений
├── wp_sync_skill.py            # новая точка входа WP (или wp/cli.py)
├── wp/                         # опционально: пакет wp_source
│   ├── __init__.py
│   ├── client.py               # HTTP client, rate limit, retry
│   ├── fetcher.py              # posts, pages, terms, users
│   ├── mapper.py               # WP JSON -> внутренняя модель / ContentItem
│   ├── storage.py              # сохранение в PostgreSQL / SQLite
│   └── config.py               # чтение конфига (sites, timeout, per_page)
├── contracts.py                # при необходимости расширить metadata для source_type=wp
├── errors.py                   # + коды WP_*
├── logging_setup.py            # без изменений
└── docs/
    └── wp-source-*.md
```

Допущение: окончательная структура (пакет `wp/` vs плоские модули `wp_*.py`) — на усмотрение разработчика при реализации.

---

## 4. Поток данных

1. **Оркестратор** (OpenClaw) по расписанию вызывает команду WP sync (один раз за run или по одному вызову на сайт).
2. **CLI** читает конфиг (список сайтов, креды, параметры), генерирует run_id, поднимает логирование.
3. **Client** выполняет запросы к REST API с соблюдением лимита 3 req/s на сайт, timeout 30 s, retries 3 (exponential backoff).
4. **Fetcher** последовательно запрашивает: users (для маппинга author) → terms → posts → pages (или порядок по необходимости; terms могут кэшироваться на run).
5. **Mapper** приводит ответы к единой модели (см. [data-model](wp-source-data-model-postgres.md)) и к контракту выгрузки (JSON/ContentItem).
6. **Storage** пишет в PostgreSQL (upsert по бизнес-ключу), с идемпотентным full sync (см. [sync-strategy](wp-source-sync-strategy.md)).
7. По завершении пишется **summary** (run_at, run_id, site_id, counts, error_code при частичной/полной ошибке) в лог и при необходимости в БД или файл.

---

## 5. Наблюдаемость

- **run_id** — один на запуск sync (все сайты или один сайт — по решению оркестратора); прокидывается во все логи и в summary.
- **error_code** — из `errors.py` (в т.ч. новые WP_*); при ошибках запросов и при частичном успехе (например часть страниц не получена).
- **Логи приложения** — тот же формат, что и для TG (run_id, error_code в extra).
- **Summary** — аналог `summary.json`: run_at, run_id, site/sites, posts_fetched, pages_fetched, terms_fetched, errors_count, partial_failure; при необходимости — путь к экспорту или идентификатор run в БД.
- **Логи экспорта** (если будет каталог по аналогии с TG) — JSONL в том же стиле (ts, level, event, data с run_id/error_code).

---

## 6. Риски и допущения

- **Риски:** см. [wp-source-risks-and-open-questions.md](wp-source-risks-and-open-questions.md).
- **Допущения:** выбор варианта CLI (A/B), точная структура каталогов, состав полей SEO (зависит от плагина на стороне WP) зафиксированы в соответствующих документах и в open questions.

---

## 7. Критерии приёмки архитектуры

- [ ] Существующие smoke-тесты и CLI TG не ломаются.
- [ ] WP sync выполняется отдельной командой/скриптом с теми же exit_codes и run_id/error_code в логах.
- [ ] Данные WP сохраняются в PostgreSQL по описанной схеме и доступны для чтения после full sync.
- [ ] Конфиг WP (URL сайтов, креды, per_page, timeout, retries, rate limit) вынесен в конфиг/переменные окружения, без хардкода в коде.
