# WordPress Source — настройка (MVP + Hardening)

**Дата:** 2026-02-23

## 1. Конфиг сайтов

Файл `config/wp-sites.yml` (можно скопировать из `config/wp-sites.yml.example`):

**Один сайт:**

```yaml
sites:
  - site_id: main
    base_url: https://your-site.com
    name: Main Site
```

**Мультисайт (несколько сайтов в одном конфиге):**

```yaml
sites:
  - site_id: main
    base_url: https://your-site.com
    name: Main Site
  - site_id: rodina
    base_url: https://rodina.example.com
    name: Rodina

# Опционально: глобальные параметры и явный backend
per_page: 100
timeout_sec: 30
retries: 3
requests_per_second: 3.0
# storage_backend: sqlite   # раскомментировать для принудительного SQLite
```

**Приоритет конфигурации backend:** если в YAML задан `storage_backend`, он переопределяет переменную окружения `WP_STORAGE_BACKEND` на время запуска sync (конфиг имеет приоритет над env).

- `site_id` — уникальный идентификатор сайта (латиница, цифры, дефис).
- `base_url` — базовый URL без слэша в конце.
- Секреты **не** хранятся в YAML: только в переменных окружения.
- Команда `python wp_sync_skill.py sync` без `--site` синхронизирует **все** сайты из списка; один общий `run_id`, в stdout — агрегированный JSON с полями `run_id`, `status`, `totals`, `sites`.

## 2. Переменные окружения

Для каждого сайта задайте (подставьте свой `site_id` в верхнем регистре, дефис → подчёркивание, например `main`, `rodina` → `RODINA`):

- `WP_SITE_<SITE_ID>_USER` — логин пользователя WordPress (с правами на чтение REST API).
- `WP_SITE_<SITE_ID>_APP_PASSWORD` — Application Password (см. раздел 3).

Пример для двух сайтов `main` и `rodina`:

```bash
WP_SITE_MAIN_USER=admin
WP_SITE_MAIN_APP_PASSWORD=xxxx xxxx xxxx xxxx
WP_SITE_RODINA_USER=editor
WP_SITE_RODINA_APP_PASSWORD=yyyy yyyy yyyy yyyy
```

**Хранилище:**

- **PostgreSQL (по умолчанию):**  
  `WP_DATABASE_URL=postgresql://user:password@host:5432/dbname`  
  Либо `DATABASE_URL`, если уже используется в проекте.

- **SQLite (fallback или явно):**  
  - `WP_STORAGE_BACKEND=sqlite` — принудительно использовать SQLite.  
  - `WP_STORAGE_PATH` — путь к файлу БД (по умолчанию `data/wp_sync.db` в корне проекта).  
  - **Политика fallback:** при недоступности PostgreSQL по умолчанию sync **завершается с ошибкой** (fail fast). Чтобы автоматически переключаться на SQLite, задайте `WP_STORAGE_FALLBACK=auto`. Рекомендуется в prod оставлять `off` (или не задавать), чтобы не писать в локальную БД по ошибке.

**Поведение fallback:** если `WP_STORAGE_BACKEND` не задан, **обязателен** `WP_DATABASE_URL` — иначе sync завершится с ошибкой (fail fast). При заданном URL делается попытка подключиться к PostgreSQL. При ошибке: если `WP_STORAGE_FALLBACK=auto` — переход на SQLite с предупреждением в логах; иначе — исключение и выход с ошибкой. Чтобы использовать только SQLite без Postgres, явно задайте `WP_STORAGE_BACKEND=sqlite` (тогда `WP_DATABASE_URL` не нужен).

## 3. Application Password в WordPress (пошагово)

1. Войдите в админку WordPress → **Users** → **Profile** (профиль пользователя с правами на чтение).
2. Пролистайте до раздела **Application Passwords**.
3. В поле **New Application Password Name** введите имя (например `tg-parser-sync`), нажмите **Add New Application Password**.
4. Скопируйте сгенерированный пароль **один раз** (отображается единственный раз) и задайте его в переменной окружения `WP_SITE_<ID>_APP_PASSWORD` (пробелы в пароле допустимы).

Требуется WordPress 6.0+ и включённый REST API.

## 4. Миграции PostgreSQL и SQLite

**PostgreSQL:** схема WP (таблицы `wp_sites`, `wp_sync_runs`, …) применяется через **Alembic**. URL подключения берётся из `WP_DATABASE_URL` или `DATABASE_URL` (из `.env`).

**SQLite:** DDL лежит в `migrations/wp/sqlite/` (001–006). При первом вызове `get_connection()` с backend=sqlite схема создаётся автоматически; отдельно применять ничего не нужно. Файл БД по умолчанию: `data/wp_sync.db` (или путь из `WP_STORAGE_PATH`).

Схема WP (таблицы `wp_sites`, `wp_sync_runs`, …) для Postgres применяется через **Alembic**. URL подключения берётся из `WP_DATABASE_URL` или `DATABASE_URL` (из `.env`).

**Важно:** база данных **Pipeline** должна существовать до запуска миграций. Если её ещё нет:

```sql
-- Подключитесь к любой существующей БД (например postgres) и выполните:
CREATE DATABASE "Pipeline";
```

Через psql (подставьте своего пользователя и хост):

```bash
psql -U postgres -h localhost -d postgres -c "CREATE DATABASE \"Pipeline\";"
```

**Первое применение (создать все таблицы):**

```powershell
# из корня проекта, .venv активирован
alembic upgrade head
```

**Проверить текущую ревизию:**

```powershell
alembic current
```

**Откатить последнюю миграцию:**

```powershell
alembic downgrade -1
```

**Создать новую миграцию (после изменения схемы):**

```powershell
alembic revision -m "описание_изменения"
# отредактировать alembic/versions/xxxx_описание.py: upgrade() и downgrade()
alembic upgrade head
```

Файлы в `migrations/wp/*.sql` остаются справочными (исходный DDL); для применения используется только Alembic.

## 5. Запуск и диагностика

**Команды:**

- Список сайтов из конфига (без кредов):  
  `python wp_sync_skill.py list-sites`

- Синхронизация **всех** сайтов (мультисайт, один run_id, агрегированный summary в stdout):  
  `python wp_sync_skill.py sync`

- Синхронизация **одного** сайта:  
  `python wp_sync_skill.py sync --site main`

Итоговый summary выводится в stdout в формате JSON. Логи — в `logs/app.log`, `logs/errors.log` (в каждой записи WP — `run_id` и `site_id`).

**Коды выхода:** 0 — все сайты success; 2 — partial (хотя бы один success и хотя бы один failed); 1 — все failed или фатальная ошибка конфига.

**Типичные ошибки:**

- **401 Unauthorized** — неверный логин или Application Password. Проверьте `WP_SITE_<ID>_USER` и `WP_SITE_<ID>_APP_PASSWORD`, пересоздайте Application Password в профиле WP при необходимости.
- **429 Too Many Requests** — лимит запросов к REST API. Уменьшите `requests_per_second` в конфиге или подождите; скрипт делает retry с backoff.
- **Timeout** — сайт не отвечает за `timeout_sec` секунд. Увеличьте `timeout_sec` в конфиге или проверьте доступность `base_url`.

## 6. MCP PostgreSQL (доступ к БД из Cursor)

Для запросов к БД Pipeline прямо из Cursor (схема, выборки, отладка):

1. Скопируйте конфиг:  
   `Copy-Item .cursor\mcp.json.example .cursor\mcp.json`
2. Откройте `.cursor/mcp.json` и в строке подключения замените `USER`, `PASSWORD`, при необходимости `localhost:5432` на свои значения (та же БД, что и для `WP_DATABASE_URL`).
3. Перезапустите Cursor, чтобы поднялся MCP-сервер PostgreSQL.
4. В чате/агентах можно обращаться к БД через MCP (read-only). БД по умолчанию в примере: **Pipeline**.
