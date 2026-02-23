# WordPress Source — контракт этапа Scale (Phase 2)

**Дата:** 2026-02-23  
**Статус:** контракт (реализация — отдельными задачами S1–S5)  
**Связанные документы:** [wp-source-implementation-plan](wp-source-implementation-plan.md), [wp-source-data-model-postgres](wp-source-data-model-postgres.md), [wp-source-scale-tasks](wp-source-scale-tasks.md)

---

## 1. Совместимость

- **Текущий JSON/БД контракт MVP не ломаем.** Существующие поля документов экспорта и таблиц БД остаются без изменений типа и семантики.
- **Новые поля только additive.** Новые колонки в БД и новые ключи в JSON добавляются как опциональные (nullable / отсутствующие при отключённых фичах). Старый код и потребители JSON, игнорирующие новые поля, продолжают работать.

---

## 2. Флаги поведения

Управление режимами — через переменные окружения (и при необходимости дублирование в конфиге YAML). Значения по умолчанию обеспечивают поведение, эквивалентное MVP.

| Переменная | Значения | По умолчанию | Описание |
|------------|----------|--------------|----------|
| `WP_CONTENT_MODE` | `rendered` \| `raw` \| `both` | `rendered` | Какой контент постов/страниц забирать и сохранять: только rendered (MVP), только raw, или оба. |
| `WP_SYNC_MODE` | `full` \| `incremental` | `full` | Режим синхронизации: полная выгрузка (MVP) или только изменённые записи. |
| `WP_GUTENBERG_PARSE` | `off` \| `basic` | `off` | Парсить ли Gutenberg raw comments в структуру блоков и сохранять в БД/JSON. |

При откате всех флагов на значения по умолчанию поведение должно быть идентично MVP (full sync, только rendered, без парсинга блоков).

---

## 3. Расширения БД (additive)

Новые объекты и колонки только добавляются; существующие таблицы не переименовываются и не меняют типы существующих колонок.

### 3.1 Таблица `wp_content`

| Колонка | Тип | Описание |
|---------|-----|----------|
| `post_content_raw` | TEXT (или JSON по решению реализации) | Сырой редакторский контент (`content.raw` из API). Заполняется при `WP_CONTENT_MODE=raw` или `both`. NULL при `rendered`. |
| `gutenberg_blocks_json` | JSONB / TEXT | Структурированное представление блоков Gutenberg (из парсинга raw comments). Заполняется при `WP_GUTENBERG_PARSE=basic`. NULL при `off`. |

Миграции: отдельные файлы в `migrations/wp/` с `ALTER TABLE wp_content ADD COLUMN ...` (и при необходимости индексы только по новым колонкам).

### 3.2 Таблица `wp_sync_state` (новая)

Для режима `WP_SYNC_MODE=incremental`: хранение watermark по сайту.

| Колонка | Тип | Описание |
|---------|-----|----------|
| `site_id` | VARCHAR(64) | PK, ссылка на wp_sites(site_id). |
| `last_modified_gmt` | TIMESTAMPTZ | Последняя известная дата изменения контента на стороне WP (для запроса modified_after и т.п.). |
| `last_run_id` | VARCHAR(32) | run_id последнего успешного incremental run. |
| `updated_at` | TIMESTAMPTZ | Время обновления записи. |

Один ряд на сайт. Создаётся/обновляется только при включённом incremental sync.

---

## 4. JSON output v2 (additive)

Существующие поля документов контента и summary не удаляются и не переименовываются. Добавляются опциональные поля.

### 4.1 Документ контента (пост/страница)

| Поле | Тип | Описание |
|------|-----|----------|
| `post_content_raw` | string \| null | Сырой контент; присутствует при `WP_CONTENT_MODE=raw` или `both`, иначе отсутствует или null. |
| `gutenberg_blocks` | array/object \| null | Распарсенные блоки Gutenberg; присутствует при `WP_GUTENBERG_PARSE=basic`, иначе отсутствует или null. |

### 4.2 Summary (итог run)

| Поле | Тип | Описание |
|------|-----|----------|
| `sync_mode` | string | `full` или `incremental`. |
| `watermark` | string/object \| null | Для incremental — значение watermark после run (например last_modified_gmt или описание состояния). Для full — отсутствует или null. |

Остальные поля summary (run_id, site_id, status, run_at, error_code, *_count и т.д.) без изменений.

---

## 5. Коды ошибок (additive)

Добавить в `errors.py` (или аналог) без удаления существующих кодов:

| Код | Описание |
|-----|----------|
| `WP_INCREMENTAL_STATE_ERROR` | Ошибка чтения/записи состояния incremental sync (wp_sync_state): повреждённые данные, конфликт, недоступность БД. |
| `WP_RAW_CONTENT_FORBIDDEN` | Запрошен raw-контент (`WP_CONTENT_MODE=raw` или `both`), но API не вернул его (например нет прав на `context=edit`, или ответ без `content.raw`). |

Использование: логирование и при необходимости передача в summary.error_code при частичном/фатальном сбое в соответствующих сценариях.

---

## 6. Критерии приёмки этапа Scale (сводные)

- **Full sync эквивалентен MVP по данным:** при `WP_SYNC_MODE=full`, `WP_CONTENT_MODE=rendered`, `WP_GUTENBERG_PARSE=off` набор данных и форма JSON/БД совместим с текущим MVP (новые колонки/поля могут быть NULL или отсутствовать).
- **Incremental не создаёт дублей:** два последовательных прогона incremental без изменений на WP не дублируют записи в БД; обновляются только изменённые сущности.
- **Откат флагов:** при возврате всех флагов к значениям по умолчанию поведение идентично MVP (те же запросы, те же поля, те же коды выхода и формат summary).

Реализация каждой фичи (content.raw, incremental, Gutenberg, performance, orchestration) оформляется отдельными задачами S1–S5 с собственными DoD; см. [wp-source-scale-tasks](wp-source-scale-tasks.md).
