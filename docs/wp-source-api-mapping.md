# WordPress Source — маппинг REST API

**Дата:** 2026-02-23  
**Связанные документы:** [wp-source-architecture](wp-source-architecture.md), [wp-source-data-model-postgres](wp-source-data-model-postgres.md)

---

## 1. Базовые параметры

- **Минимальная версия WordPress:** 6.0+ (зафиксировано до старта разработки).
- **Base URL сайта:** `https://example.com` — запросы к `https://example.com/wp-json/wp/v2/...`.
- **Аутентификация:** HTTP Basic Auth: username = логин WP-пользователя, password = Application Password (создаётся в профиле пользователя, показывается один раз).
- **Заголовки:** `Content-Type: application/json`, `Accept: application/json`.
- **Параметры по умолчанию:**  
  - `per_page=100` (максимум для ядра WP — 100),  
  - `page` — для пагинации (1-based).  
  Ответы содержат заголовки `X-WP-Total`, `X-WP-TotalPages` для определения числа страниц.

---

## 2. Эндпоинты и маппинг полей

### 2.1 Пользователи (авторы)

| Эндпоинт | Метод | Назначение |
|----------|--------|------------|
| `/wp/v2/users` | GET | Список пользователей сайта (для multisite — пользователи текущего сайта). |

**Параметры:** `per_page`, `page`; опционально `context=edit` (требует прав) для дополнительных полей — в MVP не обязательно.

**Маппинг в `wp_authors`:**
| Поле БД | Поле API | Примечание |
|---------|----------|------------|
| wp_user_id | id | |
| login | slug или username (если есть в ответе) | В ядре WP REST часто возвращается `slug` как идентификатор логина |
| name | name | |
| slug | slug | |
| raw_json | весь объект ответа | |

**Допущение:** поле `username` в ядре REST API может отсутствовать в публичном контексте; при наличии — использовать для `login`, иначе `slug`.

---

### 2.2 Таксономии и термины

**Список таксономий:**  
`GET /wp/v2/taxonomies` — возвращает объект с ключами `category`, `post_tag` и т.д. Для MVP достаточно захардкодить запрос терминов для `category` и `post_tag`; при необходимости — читать список таксономий и итерировать.

**Термины конкретной таксономии:**

| Эндпоинт | Метод | Назначение |
|----------|--------|------------|
| `/wp/v2/categories` | GET | Категории |
| `/wp/v2/tags` | GET | Метки (post_tag) |
| `/wp/v2/{taxonomy}` | GET | Для custom taxonomy (подставить slug таксономии) |

**Параметры:** `per_page`, `page`; для категорий — `parent` при необходимости иерархии.

**Маппинг в `wp_terms`:**
| Поле БД | Поле API | Примечание |
|---------|----------|------------|
| taxonomy | — | `category` | `post_tag` или slug таксономии |
| wp_term_id | id | |
| name | name | |
| slug | slug | |
| parent_id | parent | 0 если нет родителя |
| raw_json | весь объект | |

---

### 2.3 Посты

| Эндпоинт | Метод | Назначение |
|----------|--------|------------|
| `/wp/v2/posts` | GET | Список постов |

**Параметры (обязательные/рекомендуемые):**
- `status=publish` — только опубликованные.
- `per_page=100`, `page`.
- `_embed` (опционально) — включить в ответ вложенные объекты `author`, `wp:term` (категории и теги), чтобы не делать лишних запросов. Рекомендуется для уменьшения числа запросов при соблюдении rate limit.

**Маппинг в `wp_content` (content_type='post'):**
| Поле БД | Поле API | Примечание |
|---------|----------|------------|
| wp_id | id | |
| title | title.rendered | строка (HTML может быть экранирован) |
| slug | slug | |
| post_content | content.rendered | **MVP:** в MVP всегда использовать `content.rendered` (HTML после фильтров темы). **Phase 2:** опция `context=edit` и `content.raw` для сырого редакторского контента — по необходимости. |
| excerpt | excerpt.rendered | по аналогии (в MVP — только rendered). |
| status | status | только publish в выборке |
| author_id | author | id пользователя |
| published_at | date_gmt / date | ISO в UTC |
| modified_at | modified_gmt / modified | ISO в UTC |
| seo_title | yoast_head_json.title / meta из плагина | см. раздел SEO |
| seo_description | yoast_head_json.description | см. раздел SEO |
| seo_json | yoast_head_json или аналог | см. раздел SEO |
| raw_json | весь объект (опционально) | для отладки и расширения |

**Связь с терминами:** из ответа поста при `_embed` брать `_embedded['wp:term']` — массив массивов по таксономиям (категории, теги). Заполнять таблицу `wp_content_terms`.

---

### 2.4 Страницы

| Эндпоинт | Метод | Назначение |
|----------|--------|------------|
| `/wp/v2/pages` | GET | Список страниц |

Параметры и маппинг — аналогично постам; `content_type='page'`. Для страниц в ядре нет категорий/тегов по умолчанию; при наличии custom taxonomies для page — обрабатывать по той же схеме, что и для постов.

---

## 3. SEO-поля

- **Yoast SEO:** при активном плагине в ответах постов/страниц добавляются поля:
  - `yoast_head` — HTML-блок мета-тегов (для экспорта можно не сохранять).
  - `yoast_head_json` — объект с ключами `title`, `description`, `og_*`, `twitter_*` и т.д. (доступно с версии Yoast 16.7+).
- **Rank Math / другие:** могут добавлять свои поля в REST (например через `meta` или отдельный ключ). В MVP достаточно обрабатывать `yoast_head_json`; при наличии других плагинов — расширить маппинг в `seo_json` (сырой объект).
- Маппинг в БД: `seo_title` ← yoast_head_json.title, `seo_description` ← yoast_head_json.description, `seo_json` ← весь объект yoast_head_json (или аналог).

**Допущение:** состав SEO-полей зависит от установленных плагинов на каждом сайте; при их отсутствии поля остаются NULL.

---

## 4. Порядок запросов и rate limit

- **Лимит:** не более 3 запросов в секунду на один сайт (базовый URL).
- **Рекомендуемый порядок за один run:**
  1. GET users (с пагинацией) — для маппинга author в постах/страницах.
  2. GET categories, GET tags (и при необходимости другие таксономии) — с пагинацией.
  3. GET posts?status=publish&per_page=100&page=N&_embed — до исчерпания страниц.
  4. GET pages?status=publish&per_page=100&page=N&_embed — до исчерпания страниц.
- Между запросами выдерживать паузу не менее 1/3 сек (или токен-бакет на 3 req/s). При получении HTTP 429 (Too Many Requests) — обрабатывать как rate limit: повтор с exponential backoff (см. [sync-strategy](wp-source-sync-strategy.md)).

---

## 5. Ошибки и коды

- **401 Unauthorized** — неверный Application Password или логин → AUTH_ERROR / WP_AUTH_ERROR.
- **403 Forbidden** — нет прав на чтение (редко для публичных постов) → EXTERNAL_API_ERROR / WP_AUTH_ERROR.
- **404** — сайт не найден или отключён REST API → EXTERNAL_API_ERROR.
- **429** — rate limit → RATE_LIMIT / WP_RATE_LIMIT, retry после паузы.
- **5xx / таймаут** → NETWORK_ERROR / WP_NETWORK_ERROR, retry по стратегии.
- Невалидный JSON или неожиданная структура ответа → DATA_FORMAT_ERROR.

Все коды дублируются в логах с run_id и при необходимости в summary.error_code.
