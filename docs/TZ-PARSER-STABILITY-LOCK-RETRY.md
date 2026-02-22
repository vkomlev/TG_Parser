# ТЗ: стабилизация парсера — lock, retry, диагностика

**Задача:** стабилизировать парсер, убрать падения `database is locked`, улучшить диагностику зависаний/долгих загрузок.

**Статус:** реализовано; ожидание ревью по приоритетам P0–P3.

---

## Реализация (для PR/ревью)

### Изменённые/новые файлы

- `session_lock.py` — новый: межпроцессный lock по session_file (PID в lock-файле, проверка живого процесса, контекстный менеджер).
- `errors.py` — добавлен `SESSION_LOCKED`.
- `telegram_parser_skill.py` — в `main()` перед запуском команды: `session_lock(args.session_file)`; при неудаче — лог + `SESSION_LOCKED`, exit 1.
- `telegram_parser.py` — retry при `database is locked` в `connect()` (до 5 попыток, backoff 2^attempt); логирование `media_download_start` / `media_download_finished` (run_id, message_id, media_type, known_size, duration_sec, outcome); адаптивный timeout медиа по известному размеру (потолок 3600 с).
- `smoke_session_stability.py` — новый: unit-тесты lock (acquire/release, stale PID, busy same PID), unit connect retry, опциональный интеграционный тест (два процесса, один session_file). Запуск: `python smoke_session_stability.py` или `python smoke_session_stability.py --no-integration`.

### Решения и компромиссы

- Lock по файлу с PID: без fcntl/msvcrt, кроссплатформенно; при падении процесса lock-файл может остаться — следующий запуск считает PID мёртвым и перезанимает.
- Connect retry: до 5 попыток, backoff 2^n сек; после исчерпания — `RuntimeError` с `error_code=SESSION_LOCKED` для единообразного логирования в CLI.
- Медиа: логи в export `logs/run.log` (события `media_download_start`, `media_download_finished` с outcome success|timeout|error); чувствительные данные не пишутся.
- Адаптивный timeout: `base + known_size_mb * 60` сек, cap 3600; при неизвестном размере — без изменений (базовый timeout).

### Команды тестов и результат

```text
python smoke_phase1.py
python smoke_phase3.py
python smoke_session_stability.py --no-integration
```

Все перечисленные прогоны должны завершаться успешно. Интеграционный тест без `--no-integration` запускает два процесса (один держит lock, второй — parse с тем же session_file) и проверяет выход второго с кодом 1.

### Примеры новых логов

**1) Занятая сессия (второй процесс):**

```json
{"ts":"...","level":"ERROR","event":"...","data":{"error_code":"SESSION_LOCKED"}}
```

В stderr: `Error: session is locked by another process (use another --session-file or wait)`.

**2) Connect retry (database is locked):**

```
connect database is locked, retry 1/5 in 2 s: database is locked
connect database is locked, retry 2/5 in 4 s: database is locked
connect succeeded after 3 attempt(s)
```

**3) Медиа — старт и финиш (export logs/run.log):**

```json
{"ts":"...","level":"INFO","event":"media_download_start","data":{"run_id":"...","message_id":123,"media_type":"video","known_size":1048576}}
{"ts":"...","level":"INFO","event":"media_download_finished","data":{"run_id":"...","message_id":123,"media_type":"video","duration_sec":12.34,"outcome":"success"}}
```

---

## Контекст (подтверждено логами)

- За последние сутки были падения `sqlite3.OperationalError: database is locked` в момент `connect()` Telethon (SQLiteSession).
- `download_timeout` в боевых логах не подтверждён; массово встречается в smoke-тестах (искусственно смоделировано).
- В `safe` режиме timeout уже 1800 сек, поэтому первичный фокус: **конкурирующие запуски с одним `session_file`**.

---

## 1) Что нужно внедрить

### 1.1 Межпроцессный lock на запуск `parse` для одного `session_file`

- Один процесс с конкретным session-файлом может работать одновременно.
- Второй процесс должен завершаться **контролируемо** (понятный лог + exit code failure), без зависания и без повреждения сессии.
- Lock-файл должен очищаться корректно при нормальном завершении и при исключениях.

### 1.2 Retry на `database is locked` при `connect()`

- Если при `await client.connect()` получен `sqlite3.OperationalError` с текстом `database is locked`, выполнить **ограниченный retry с backoff**.
- После исчерпания retry — корректная ошибка в лог с `error_code` (новый или существующий, но консистентный).

### 1.3 Наблюдаемость долгих загрузок

- Логировать **старт/финиш загрузки медиа** с: `run_id`, `message_id`, `media_type`, `known_size` (если есть), `duration_sec`, итог (`success|timeout|error`).
- Логи не должны содержать чувствительные данные.

### 1.4 Опционально (если быстро/без риска): адаптивный timeout

- Если известен размер файла, увеличивать timeout по формуле (с верхним потолком), чтобы крупные файлы не отстреливались фиксированным порогом.
- Поведение по умолчанию не ломать.

---

## 2) Ограничения

- Не менять внешний CLI/API контракт.
- Не ломать текущий формат `export.json`, `state.json`, `summary.json`.
- Изменения минимальные и безопасные, без крупных рефакторингов.

---

## 3) Критерии приёмки

| № | Критерий |
|---|----------|
| 1 | **Конкурентный запуск:** при одновременном старте двух `parse` с одним `--session-file` только один запускается; второй завершается предсказуемо, без `database is locked`. |
| 2 | **Устойчивость connect:** кратковременный lock SQLite не валит процесс сразу, а проходит через retry; при исчерпании retry — читаемая ошибка и корректный код выхода. |
| 3 | **Логирование:** в `app.log`/`errors.log` есть чёткая трасса по попыткам connect/retry; для медиа — start/end события с длительностью и итогом. |
| 4 | **Регрессий нет:** текущие smoke-тесты проходят; добавлены новые тесты на lock/retry (минимум unit + один интеграционный сценарий на конкурентный запуск). |

---

## 4) Что разработчик должен приложить в PR

- Список изменённых файлов.
- Краткое описание решений и компромиссов.
- Вывод тестов (команды + результат).
- Примеры новых логов (2–3 фрагмента: lock, connect retry, media duration).

После отправки PR/диффа выполняется детальное ревью по приоритетам **P0–P3**.
