# Ревью: Этап 3 — Fetcher (users, terms, posts, pages)

**Дата:** 2026-02-23  
**Scope:** `wp/fetcher.py`, `wp/mapper.py` (без изменений), `tests/test_wp_fetcher.py`, документация.

---

## 1. Что сделано по пунктам ТЗ

| Пункт | Статус |
|-------|--------|
| Эндпоинты и порядок: GET /users, /categories, /tags, /posts, /pages | Реализовано в `fetch_users`, `fetch_categories`, `fetch_tags`, `fetch_posts`, `fetch_pages`. |
| Пагинация: per_page=100, page=1..N по X-WP-TotalPages | Реализовано; fallback при пустой странице или len(data) < per_page. |
| Защита от невалидных заголовков | `_total_pages()` возвращает >= 1 при None/пустом/нечисловом/0/отрицательном значении. |
| Фильтры: status=publish, _embed для posts/pages | В параметрах запросов к /posts и /pages передаются `status=publish` и `_embed`. |
| Маппинг по docs/wp-source-api-mapping.md | Используются `user_to_author`, `category_to_term`, `tag_to_term`, `post_to_content`, `page_to_content`, `content_embedded_terms` из `wp/mapper.py`. |
| post_content только content.rendered | В маппере используется только `content.rendered`; content.raw не запрашивается (phase 2). |
| Парсинг даты: date_gmt приоритетно, затем date | В mapper: `_parse_iso(raw.get("date_gmt") or raw.get("date"))`. |
| Возвращаемые типы: AuthorRow, TermRow, (ContentRow, ContentTermRow) | Соответствует сигнатурам в fetcher. |
| Устойчивость: ответ не list — не падать | При не-list пишется лог и выполняется break, возвращаются уже собранные данные. |
| Unit-тесты | 10 тестов в `tests/test_wp_fetcher.py`: пагинация, fallback, params, маппинг, non-list. |
| Регрессия smoke | `tests/smoke_wp.py --unit-only` проходит. |

---

## 2. Изменённые/добавленные файлы

- **wp/fetcher.py** — доработки Этапа 3: докстринг, `_total_pages(headers)` с защитой, во всех fetch-функциях проверка `isinstance(data, list)` и лог при не-list.
- **tests/test_wp_fetcher.py** — новый файл: unit-тесты пагинации, X-WP-TotalPages, fallback, параметры status/_embed, маппинг content.rendered и _embedded terms, безопасное завершение при не-list.
- **docs/wp-source-implementation-plan.md** — добавлена отметка о реализации Шага 3 и ссылка на ревью.

---

## 3. Команды тестов и вывод

```text
d:\Work\TG_Parser> python tests/test_wp_fetcher.py
WP API /users вернул не список (type=dict), завершаем пагинацию
WP fetcher (stage 3) unit tests
  OK _total_pages from header
  OK _total_pages fallback invalid
  OK fetch_users pagination 2 pages
  OK fetch_users stop on empty page
  OK fetch_posts params status _embed
  OK fetch_pages params status _embed
  OK mapping post_content rendered
  OK mapping embedded terms
  OK fetch non-list safe finish
  OK fetch_categories pagination
```

```text
d:\Work\TG_Parser> python tests/smoke_wp.py --unit-only
WP smoke/unit tests
  OK mapper user_to_author
  OK mapper category_to_term
  ...
Unit tests passed.
```

---

## 4. Пример результата маппинга (1–2 записи)

**AuthorRow** (после `user_to_author`):

```python
AuthorRow(site_id='main', wp_user_id=1, login='admin', name='Admin', slug='admin', raw_json={...})
```

**ContentRow + ContentTermRow** (пост с _embed):

```python
# Один пост
ContentRow(
  site_id='main', content_type='post', wp_id=42,
  title='Hello World', slug='hello-world',
  post_content='<p>Rendered content here.</p>',  # только content.rendered
  excerpt=None, status='publish', author_id=1,
  published_at=datetime(2026, 1, 15, 10, 0, 0), modified_at=...
)
# Связи с терминами из _embedded['wp:term']
ContentTermRow(site_id='main', content_type='post', wp_content_id=42, taxonomy='category', wp_term_id=1)
ContentTermRow(site_id='main', content_type='post', wp_content_id=42, taxonomy='post_tag', wp_term_id=5)
```

---

## 5. Ревью-артефакты

- Отчёт: `reviews/2026-02-23-wp-fetcher-stage3.md` (этот файл).
- Diff: `reviews/2026-02-23-wp-fetcher-stage3.diff` (сводка изменений; репозиторий не git — diff сформирован вручную).

Критерии приёмки Этапа 3 выполнены: пагинация по X-WP-TotalPages с fallback, маппинг полей корректен, unit-тесты проходят, регрессий в smoke нет.
