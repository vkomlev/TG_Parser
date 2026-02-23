# Ревью: Шаг 4 — модель и единый JSON output (MVP)

**Дата:** 2026-02-23  
**Scope:** `wp/output.py`, `wp_sync_skill.py`, `tests/test_wp_output.py`, документация.

---

## 1. Что сделано по пунктам ТЗ

| Пункт | Статус |
|-------|--------|
| Единый JSON-контракт: sync --site → один объект, sync по нескольким сайтам → массив | Реализовано в `wp_sync_skill.py`: вывод через `build_single_site_output` / `build_multi_site_output`. |
| На уровне записи контента: source, site_id, content_type, wp_id, slug, title, post_content, excerpt, status, author_id, published_at, modified_at, taxonomies, seo | Реализовано в `wp/output.py`: `content_row_to_export_dict` и `build_content_export_list`. |
| Run summary: run_id, status, counts, error_code — стабильный контракт | `summary_to_export_dict` выводит только эти поля, без credential. |
| post_content только из content.rendered | Используется существующий маппинг в mapper (post_content из content.rendered); в JSON нет content.raw. |
| SEO из yoast_head_json: title → seo_title, og_description \|\| description → seo_description, yoast_head_json целиком | Уже в mapper; в export — объект seo: { seo_title, seo_description, yoast_head_json }. |
| Даты в ISO, отсутствующие поля = null | `_datetime_iso`, все ключи контракта присутствуют, None → null в JSON. |
| Без content.raw, без ContentItem, без изменения логики записи в БД | Соблюдено. |
| Unit-тесты маппинга и JSON-контракта | 11 тестов в `tests/test_wp_output.py`. |
| Регрессии smoke_wp --unit-only | Проходят. |

---

## 2. Изменённые/добавленные файлы

- **wp/output.py** (новый) — контракт документа контента и summary; `content_row_to_export_dict`, `build_content_export_list`, `summary_to_export_dict`, `build_single_site_output`, `build_multi_site_output`; обогащение taxonomies из TermRow/ContentTermRow.
- **wp_sync_skill.py** — `run_sync_site` возвращает `{ summary, contents, content_terms, terms }`; при исключении — объект с пустыми списками; в `run_sync` формирование итогового JSON по контракту и вывод в stdout (один объект или массив); импорт `wp.output`.
- **tests/test_wp_output.py** (новый) — тесты полного export, без/с SEO, без excerpt/content, пустые taxonomies, single/multi output, обязательные ключи, post_content только rendered, маппинг из фиксированного API с yoast, отсутствие секретов в summary.
- **docs/wp-source-implementation-plan.md** — отметка о реализации Шага 4.
- **docs/wp-source-data-model-postgres.md** — абзац о реализации контракта в `wp/output.py`.

---

## 3. Команды тестов и вывод

```text
d:\Work\TG_Parser> python tests/test_wp_output.py
WP output (stage 4) unit tests
  OK content export full
  OK content export without SEO
  OK content export with SEO
  ...
  OK summary no credentials
```

```text
d:\Work\TG_Parser> python tests/smoke_wp.py --unit-only
WP smoke/unit tests
  OK mapper user_to_author
  ...
Unit tests passed.
```

```text
d:\Work\TG_Parser> python tests/test_wp_fetcher.py
WP fetcher (stage 3) unit tests
  OK _total_pages from header
  ...
```

---

## 4. Пример итогового JSON

**Single-site (sync --site main):**

```json
{
  "run_id": "a1b2c3d4",
  "site_id": "main",
  "status": "success",
  "run_at": "2026-02-23T12:00:00+00:00",
  "error_code": null,
  "posts_count": 2,
  "pages_count": 1,
  "terms_count": 5,
  "authors_count": 1,
  "content": [
    {
      "source": "wp",
      "site_id": "main",
      "content_type": "post",
      "wp_id": 42,
      "slug": "hello-world",
      "title": "Hello World",
      "post_content": "<p>Rendered content.</p>",
      "excerpt": null,
      "status": "publish",
      "author_id": 1,
      "published_at": "2026-01-01T10:00:00+00:00",
      "modified_at": "2026-02-20T14:00:00+00:00",
      "taxonomies": {
        "category": [{ "wp_term_id": 1, "slug": "news", "name": "News" }],
        "post_tag": []
      },
      "seo": {
        "seo_title": null,
        "seo_description": null,
        "yoast_head_json": null
      }
    }
  ]
}
```

**Multi-site (sync без --site):** массив таких объектов, по одному на каждый сайт из конфига.

---

## 5. Ревью-артефакты

- Отчёт: `reviews/2026-02-23-wp-stage4-model-json.md` (этот файл).
- Diff: `reviews/2026-02-23-wp-stage4-model-json.diff`.

Критерии приёмки Шага 4 выполнены: единый JSON-контракт, преобразование WP API → model → JSON покрыто тестами, интеграции с ContentItem нет.
