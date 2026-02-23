# TG_Parser

Парсер Telegram-каналов: экспорт сообщений в JSON и загрузка медиа (фото, видео, документы) с поддержкой инкрементального обновления и работы по ссылкам на посты.

## Возможности

- Экспорт текста и медиа в структурированный JSON
- Хранение медиа по типам: `media/photos`, `media/videos`, `media/documents`
- Режим обновления: добавление новых сообщений в существующий каталог по `message_id`
- Поддержка ссылок: парсинг по `https://t.me/channel/123` или получение id канала командой `resolve`
- Дедупликация медиа по SHA-256 (`media-index.json`), состояние в `state.json`
- Режимы скорости: `safe` (по умолчанию) и `normal`, обработка FloodWait и повторные попытки
- Dry-run (оценка объёма без записи), опция упаковки в ZIP
- Логирование с ротацией: `logs/app.log`, `logs/errors.log`, JSONL в каталоге экспорта

## Быстрый старт

```powershell
cd D:\Work\TG_Parser
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# заполните .env (см. docs/setup.md)
python .\telegram_parser_skill.py channels
python .\telegram_parser_skill.py parse --channel "https://t.me/AlgorithmPythonStruct/36"
```

См. также запуск через [скрипты в `scripts/`](docs/setup.md#6-алиасы-powershell-опционально) и [смоук-тесты](docs/tests.md).

## Документация

| Раздел | Описание |
|--------|----------|
| [**Первоначальная настройка**](docs/setup.md) | Окружение, `.env`, первый вход, 2FA |
| [**CLI и формы запуска**](docs/cli.md) | Команды `channels`, `resolve`, `parse`, все опции и примеры |
| [**Форматы выходных файлов**](docs/output-formats.md) | `export.json`, `state.json`, `media-index.json`, `summary.json`, структура каталога |
| [**Логирование**](docs/logging.md) | Формат логов, ротация, расположение файлов |
| [**Описание функций**](docs/functions.md) | Основные функции и классы модулей парсера |

## Коды выхода

- `0` — успех; `1` — фатальная ошибка; `2` — частичный успех (parse завершён, часть медиа не загружена); `130` — прерывание (Ctrl+C). Подробно — в [CLI](docs/cli.md#коды-выхода).

## Безопасность

- Учётные данные хранятся только в `.env` (файл в `.gitignore`)
- Секреты не выводятся в логи
- Время в JSON и логах — UTC в формате ISO (`YYYY-MM-DDTHH:mm:ssZ`)

## WordPress Source (sync в PostgreSQL или SQLite)

Отдельная точка входа для синхронизации WordPress-сайтов (только чтение, full sync).

- **Конфиг:** `config/wp-sites.yml`; секреты — переменные окружения `WP_SITE_<site_id>_USER`, `WP_SITE_<site_id>_APP_PASSWORD`. Опционально `storage_backend: sqlite` в YAML.
- **Хранилище:** по умолчанию PostgreSQL (`WP_DATABASE_URL` или `DATABASE_URL`). При недоступности Postgres или при явном указании используется **SQLite** (файл `data/wp_sync.db` или путь из `WP_STORAGE_PATH`). Явное включение: `WP_STORAGE_BACKEND=sqlite` или в конфиге `storage_backend: sqlite`. **Fallback:** по умолчанию при ошибке Postgres sync завершается с ошибкой; для авто-перехода на SQLite задайте `WP_STORAGE_FALLBACK=auto`.
- **Миграции:** PostgreSQL — DDL в `migrations/wp/` (001–006); SQLite — скрипты в `migrations/wp/sqlite/`, применяются автоматически при первом подключении.
- **Команды:**  
  `python wp_sync_skill.py list-sites`  
  `python wp_sync_skill.py sync` — мультисайт (все сайты из конфига, один run_id, агрегированный summary в stdout)  
  `python wp_sync_skill.py sync --site SITE_ID` — один сайт  
- **Коды выхода:** 0 — все сайты success; 2 — partial (часть успешна); 1 — все failed или фатальная ошибка конфига.
- Подробнее: [docs/wp-source-setup.md](docs/wp-source-setup.md), [docs/wp-source-architecture.md](docs/wp-source-architecture.md), [docs/wp-source-implementation-plan.md](docs/wp-source-implementation-plan.md).

## Интеграция

- **OpenClaw / скиллы**: команды можно сопоставить с `telegram_parser_skill.py` (см. [CLI](docs/cli.md))
- **PowerShell-скрипты и алиасы**: `scripts/telegram_parse.ps1`, `scripts/telegram_channels.ps1`, `scripts/setup_aliases.ps1` — см. [Настройка](docs/setup.md)
