# WordPress Source — модель данных и PostgreSQL

**Дата:** 2026-02-23  
**Связанные документы:** [wp-source-architecture](wp-source-architecture.md), [wp-source-sync-strategy](wp-source-sync-strategy.md)

---

## 1. Назначение

- Единое хранилище для сырых/нормализованных данных WP (posts, pages, terms, authors) после full sync.
- Идемпотентность: повторный full sync перезаписывает данные по бизнес-ключу без дубликатов.
- Возможность выборки для анализа и трансформаций (в т.ч. маппинг в ContentItem для общего пайплайна).

---

## 2. Бизнес-ключи и scope

- **Сайт** идентифицируется по `site_id` (внутренний id, например UUID или slug из конфига). В таблицах — `site_id` + внешний id сущности на стороне WP (например `wp_post_id`, `wp_user_id`).
- **Уникальность:** (site_id, wp_*_id) для сущностей; для terms дополнительно taxonomy (category, post_tag и т.д.).
- **Допущение:** один инстанс синка не пишет параллельно в один и тот же site_id (оркестратор вызывает sync по одному сайту за раз или последовательно).

---

## 3. DDL PostgreSQL

### 3.1 Таблица сайтов (справочник)

```sql
CREATE TABLE wp_sites (
    site_id     VARCHAR(64) PRIMARY KEY,
    base_url    VARCHAR(512) NOT NULL,
    name        VARCHAR(255),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE wp_sites IS 'Зарегистрированные WordPress-сайты для синхронизации';
```

### 3.2 Синк-раны (обзор запусков)

```sql
CREATE TABLE wp_sync_runs (
    id              BIGSERIAL PRIMARY KEY,
    run_id          VARCHAR(32) NOT NULL,
    site_id         VARCHAR(64) NOT NULL REFERENCES wp_sites(site_id),
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    status          VARCHAR(20) NOT NULL DEFAULT 'running',  -- running | success | partial | failed
    error_code      VARCHAR(64),
    posts_count     INT NOT NULL DEFAULT 0,
    pages_count     INT NOT NULL DEFAULT 0,
    terms_count     INT NOT NULL DEFAULT 0,
    authors_count   INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_wp_sync_runs_site_started ON wp_sync_runs(site_id, started_at DESC);
CREATE INDEX idx_wp_sync_runs_run_id ON wp_sync_runs(run_id);

COMMENT ON TABLE wp_sync_runs IS 'История запусков WP sync для наблюдаемости и отладки';
```

### 3.3 Авторы (users)

```sql
CREATE TABLE wp_authors (
    site_id         VARCHAR(64) NOT NULL REFERENCES wp_sites(site_id),
    wp_user_id      BIGINT NOT NULL,
    login           VARCHAR(255),
    name            VARCHAR(255),
    slug            VARCHAR(255),
    raw_json        JSONB,
    synced_at       TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (site_id, wp_user_id)
);

CREATE INDEX idx_wp_authors_site ON wp_authors(site_id);
```

### 3.4 Термины (categories, tags, custom taxonomies)

```sql
CREATE TABLE wp_terms (
    site_id         VARCHAR(64) NOT NULL REFERENCES wp_sites(site_id),
    taxonomy        VARCHAR(64) NOT NULL,
    wp_term_id      BIGINT NOT NULL,
    name            VARCHAR(255),
    slug            VARCHAR(255) NOT NULL,
    parent_id       BIGINT,
    raw_json        JSONB,
    synced_at       TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (site_id, taxonomy, wp_term_id)
);

CREATE INDEX idx_wp_terms_site_tax ON wp_terms(site_id, taxonomy);
```

### 3.5 Посты и страницы (единая таблица или раздельные)

Рекомендация: **одна таблица** `wp_content` с полем `content_type` ('post' | 'page') для единообразия и повторного использования индексов. При необходимости позже можно разделить представлениями.

```sql
CREATE TABLE wp_content (
    site_id         VARCHAR(64) NOT NULL REFERENCES wp_sites(site_id),
    content_type    VARCHAR(16) NOT NULL,  -- 'post' | 'page'
    wp_id           BIGINT NOT NULL,
    title           TEXT,
    slug            VARCHAR(255) NOT NULL,
    post_content    TEXT,
    excerpt         TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'publish',
    author_id       BIGINT,
    published_at    TIMESTAMPTZ,
    modified_at     TIMESTAMPTZ,
    seo_title       VARCHAR(255),
    seo_description TEXT,
    seo_json        JSONB,
    raw_json        JSONB,
    synced_at       TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (site_id, content_type, wp_id)
);

CREATE INDEX idx_wp_content_site_type ON wp_content(site_id, content_type);
CREATE INDEX idx_wp_content_published ON wp_content(site_id, published_at DESC);
CREATE INDEX idx_wp_content_slug ON wp_content(site_id, content_type, slug);
```

Поля `seo_title`, `seo_description`, `seo_json` — из Yoast/Rank Math (см. [api-mapping](wp-source-api-mapping.md)); при отсутствии в API остаются NULL.

### 3.6 Связь контент–термины (many-to-many)

Для выборки «все посты по категории X» без парсинга raw_json:

```sql
CREATE TABLE wp_content_terms (
    site_id         VARCHAR(64) NOT NULL,
    content_type    VARCHAR(16) NOT NULL,
    wp_content_id   BIGINT NOT NULL,
    taxonomy        VARCHAR(64) NOT NULL,
    wp_term_id      BIGINT NOT NULL,
    synced_at       TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (site_id, content_type, wp_content_id, taxonomy, wp_term_id),
    FOREIGN KEY (site_id, content_type, wp_content_id)
        REFERENCES wp_content(site_id, content_type, wp_id) ON DELETE CASCADE,
    FOREIGN KEY (site_id, taxonomy, wp_term_id)
        REFERENCES wp_terms(site_id, taxonomy, wp_term_id) ON DELETE CASCADE
);

CREATE INDEX idx_wp_content_terms_term ON wp_content_terms(site_id, taxonomy, wp_term_id);
```

---

## 4. Upsert-стратегия и идемпотентность full sync

- **Авторы, термины, контент:** за один run для данного `site_id` выполняем:
  - выборку всех текущих ключей из API (в рамках фильтра status=publish и т.д.);
  - upsert по (site_id, wp_*_id [и taxonomy для terms]) с обновлением полей и `synced_at = now()`.
- **Удаление устаревших записей:** после full sync для данного site_id можно удалить строки, у которых `synced_at` меньше `started_at` текущего run (т.е. их больше нет в ответе API или они не попали в выборку). Альтернатива — не удалять, а помечать `deleted_at` (тогда нужна колонка и мягкое удаление).  
**Рекомендация для MVP:** не удалять автоматически записи, которых не было в ответе (допущение: на стороне WP контент не удаляют часто); при необходимости «очистки» — отдельная команда или флаг `--prune-missing`. Идемпотентность достигается за счёт upsert по первичному ключу.
- **sync_runs:** вставка одной строки в начале run; обновление `finished_at`, `status`, `error_code`, счётчиков — в конце.

---

## 5. Единый JSON output (контракт на экспорт/анализ)

Для интеграции с общим пайплайном и машиночитаемого экспорта предлагается единый формат **одного файла/потока по сайту** (или по run):

**Обязательные поля (уровень документа):**
- `source`: `"wp"`
- `site_id`: строка
- `run_id`: строка (correlation id)
- `synced_at`: ISO UTC
- `content_type`: `"post"` | `"page"` | `"term"` | `"author"`
- `wp_id`: число (id в WP)
- `slug`: строка (обязательна для post/page/term)

**Опциональные (в зависимости от content_type):**
- `title`, `post_content`, `excerpt`, `published_at`, `modified_at`
- `author_id`, `author_slug`, `author_name`
- `seo_title`, `seo_description`, `seo_json`
- `taxonomies`: для post/page — список { taxonomy, terms: [ {wp_term_id, slug, name} ] }
- `raw_json`: полный ответ API при необходимости

**Пример минимального документа поста:**
```json
{
  "source": "wp",
  "site_id": "main-site",
  "run_id": "a1b2c3d4",
  "synced_at": "2026-02-23T12:00:00Z",
  "content_type": "post",
  "wp_id": 42,
  "slug": "hello-world",
  "title": "Hello World",
  "post_content": "<!-- wp:paragraph -->\n<p>Content.</p>\n<!-- /wp:paragraph -->",
  "published_at": "2026-01-01T10:00:00Z",
  "modified_at": "2026-02-20T14:00:00Z",
  "author_id": 1,
  "author_slug": "admin",
  "seo_title": "Hello World | Site Name",
  "seo_description": "Short description.",
  "taxonomies": {
    "category": [{ "wp_term_id": 1, "slug": "news", "name": "News" }],
    "post_tag": []
  }
}
```

**Реализация контракта (MVP, Шаг 4):** модуль `wp/output.py` формирует документ контента с полями `source`, `site_id`, `content_type`, `wp_id`, `slug`, `title`, `post_content`, `excerpt`, `status`, `author_id`, `published_at`, `modified_at`, `taxonomies` (category/post_tag), `seo` (seo_title, seo_description, yoast_head_json). Итог sync в stdout: один JSON-объект (один сайт) или массив объектов (несколько сайтов), каждый с полями summary и массивом `content`.

Маппинг в `ContentItem` (contracts.py) — **вне MVP (Phase 2):** source_id = `wp:{site_id}`, external_id = `{content_type}:{wp_id}`, text = конкатенация title + excerpt + post_content (или только post_content), metadata = { slug, author, seo_*, taxonomies }. Медиа для WP в MVP можно не заполнять или оставить пустой список.

---

## 6. SQLite fallback (dev/тесты)

- Та же схема (без специфичных для PostgreSQL типов: BIGSERIAL → INTEGER AUTOINCREMENT, TIMESTAMPTZ — как текст ISO или INTEGER).
- Путь к SQLite задаётся конфигом/переменной окружения; при отсутствии PostgreSQL использовать SQLite.
- Допущение: в production целевой слой — только PostgreSQL.

---

## 7. Миграции

- **Расположение (зафиксировано):** папка `migrations/wp/` в проекте с нумерованными SQL-файлами (например `001_wp_sites.sql`, `002_wp_sync_runs.sql`, …).
- Применение — вручную или скриптом при деплое; инструмент (Alembic, etc.) — на усмотрение команды.
