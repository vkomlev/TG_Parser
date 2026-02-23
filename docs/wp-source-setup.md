# WordPress Source — настройка (Этап 1 MVP)

**Дата:** 2026-02-23

## 1. Конфиг сайтов

Файл `config/wp-sites.yml` (можно скопировать из `config/wp-sites.yml.example`):

```yaml
sites:
  - site_id: main
    base_url: https://your-site.com
    name: Main Site
```

- `site_id` — уникальный идентификатор сайта (латиница, цифры, дефис).
- `base_url` — базовый URL без слэша в конце.
- Секреты **не** хранятся в YAML: только в переменных окружения.

## 2. Переменные окружения

Для каждого сайта задайте (подставьте свой `site_id`, например `main`):

- `WP_SITE_<SITE_ID>_USER` — логин пользователя WordPress (с правами на чтение REST API).
- `WP_SITE_<SITE_ID>_APP_PASSWORD` — Application Password (создаётся в профиле пользователя WP: Users → Profile → Application Passwords).

Пример для `site_id: main`:

```bash
WP_SITE_MAIN_USER=admin
WP_SITE_MAIN_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

Строка подключения к PostgreSQL:

```bash
WP_DATABASE_URL=postgresql://user:password@host:5432/dbname
```

Либо `DATABASE_URL` (если уже используется в проекте).

## 3. Application Password в WordPress

1. Вход в админку WP → Users → Profile.
2. Раздел **Application Passwords**: ввести имя (например `tg-parser-sync`), нажать **Add New Application Password**.
3. Скопировать сгенерированный пароль один раз (отображается единственный раз) и задать в `WP_SITE_<ID>_APP_PASSWORD`.

Требуется WordPress 6.0+ и включённый REST API.

## 4. Миграции PostgreSQL (Alembic)

Схема WP (таблицы `wp_sites`, `wp_sync_runs`, …) применяется через **Alembic**. URL подключения берётся из `WP_DATABASE_URL` или `DATABASE_URL` (из `.env`).

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

## 5. Запуск

- Список сайтов из конфига (без кредов):  
  `python wp_sync_skill.py list-sites`

- Синхронизация всех сайтов из конфига:  
  `python wp_sync_skill.py sync`

- Синхронизация одного сайта:  
  `python wp_sync_skill.py sync --site main`

Итоговый summary выводится в stdout в формате JSON. Логи — в `logs/app.log`, `logs/errors.log` (run_id и site_id в записях).

## 6. MCP PostgreSQL (доступ к БД из Cursor)

Для запросов к БД Pipeline прямо из Cursor (схема, выборки, отладка):

1. Скопируйте конфиг:  
   `Copy-Item .cursor\mcp.json.example .cursor\mcp.json`
2. Откройте `.cursor/mcp.json` и в строке подключения замените `USER`, `PASSWORD`, при необходимости `localhost:5432` на свои значения (та же БД, что и для `WP_DATABASE_URL`).
3. Перезапустите Cursor, чтобы поднялся MCP-сервер PostgreSQL.
4. В чате/агентах можно обращаться к БД через MCP (read-only). БД по умолчанию в примере: **Pipeline**.
