# Логирование

В проекте используются два уровня логов: общий лог приложения в корне проекта и логи внутри каталога экспорта. Все логи пишутся в UTF-8, с ротацией по размеру.

## Расположение логов

### 1. Логи приложения (корень проекта)

Каталог: **`logs/`** в корне репозитория (рядом с `telegram_parser_skill.py`).

| Файл | Назначение |
|------|------------|
| `logs/app.log` | Основной лог: команды CLI, подключение Telethon, общий ход работы |
| `logs/errors.log` | Сообщения уровня WARNING и ERROR (в т.ч. трассировки исключений) |

Создаются при первом запуске любой команды CLI. Настраиваются в `logging_setup.py` (вызов `setup_app_logging(Path(__file__).parent / "logs")`).

### 2. Логи экспорта (в каталоге результата парсинга)

Каталог: **`{export_dir}/{channel_slug}__.../logs/`**.

| Файл | Назначение |
|------|------------|
| `run.log` | События парсинга: старт/завершение прогона, flood_wait, retry, file_reference_expired |
| `errors.log` | Ошибки в рамках этого экспорта (повторы, исчерпание попыток, протухший file reference и т.п.) |

Используется класс `JsonLogger` в `telegram_parser.py`; запись — по одной JSON-строке на событие (JSONL).

---

## Формат логов приложения (app.log, errors.log в logs/)

Стандартный формат Python `logging`:

```text
YYYY-MM-DD HH:MM:SS,mmmZ LEVEL name: message
```

- Время в UTC (суффикс `Z`).
- **LEVEL** — DEBUG, INFO, WARNING, ERROR.
- **name** — имя логгера (например `tg_parser.cli`, `tg_parser.core`, `telethon...`).
- **message** — текст сообщения (на русском или английском).

**Пример:**

```text
2026-02-17 14:31:58,813Z INFO tg_parser.cli: Команда parse (channel=https://t.me/AlgorithmPythonStruct/36, mode=safe, dry_run=False, output_dir=D:\Work\TG_Parser\out)
2026-02-17 14:31:58,873Z INFO tg_parser.core: Сессия Telethon: SQLiteSession (telegram_session.session)
```

---

## Формат логов экспорта (run.log, errors.log в каталоге экспорта)

Каждая строка — отдельный JSON-объект (JSONL). Поля:

| Поле | Тип | Описание |
|------|-----|----------|
| `ts` | строка | Время события (ISO UTC, `YYYY-MM-DDTHH:mm:ssZ`) |
| `level` | строка | `INFO` или `ERROR` |
| `event` | строка | Тип события (см. ниже) |
| `data` | объект | Дополнительные данные (зависят от event) |

**Типичные значения event:**

- `run_started` — старт парсинга (channel_identifier, mode, dry_run).
- `run_finished` — завершение (полная сводка, как в summary).
- `flood_wait` — срабатывание FloodWait (seconds, sleep).
- `retry` — повторная попытка (attempt, sleep, error).
- `retry_exhausted` — исчерпаны попытки (error).
- `file_reference_expired` — протух file reference при загрузке медиа (message_id).
- `file_reference_retry_failed` — не удалось загрузить после обновления сообщения (message_id).

**Пример run.log:**

```json
{"ts": "2026-02-17T14:32:02Z", "level": "INFO", "event": "run_started", "data": {"channel_identifier": "https://t.me/AlgorithmPythonStruct/36", "mode": "safe", "dry_run": false}}
{"ts": "2026-02-17T18:57:17Z", "level": "INFO", "event": "run_finished", "data": {"run_at": "2026-02-17T18:57:17Z", "channel_id": 2614091536, ...}}
```

**Пример errors.log:**

```json
{"ts": "2026-02-17T16:32:06Z", "level": "ERROR", "event": "retry", "data": {"attempt": 1, "sleep": 2, "error": "The file reference has expired..."}}
{"ts": "2026-02-17T16:33:10Z", "level": "ERROR", "event": "retry_exhausted", "data": {"error": "The file reference has expired..."}}
```

---

## Ротация

- **Логи приложения** (`logs/app.log`, `logs/errors.log`):  
  максимальный размер файла — 2 МБ, хранится до 10 резервных копий (`.log.1`, `.log.2`, …). Настраивается в `logging_setup.py` (`RotatingFileHandler`).

- **Логи экспорта** (`.../logs/run.log`, `.../logs/errors.log`):  
  те же параметры: 2 МБ, 10 копий. Настраивается в `JsonLogger` в `telegram_parser.py`.

При превышении размера текущий файл переименовывается, создаётся новый.

---

## Безопасность

- Секреты (API keys, пароли, коды) не выводятся в логи.
- В логах могут фигурировать: идентификатор канала, путь к каталогу экспорта, номера сообщений, текст ошибок API (без учётных данных).

---

## См. также

- [Форматы выходных файлов](output-formats.md) — структура каталога экспорта
- [Описание функций](functions.md) — `setup_app_logging`, `JsonLogger`
