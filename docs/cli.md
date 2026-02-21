# CLI и формы запуска

Точка входа: `telegram_parser_skill.py`. Все команды возвращают JSON в stdout (кодировка UTF-8).

## Общий вид

```text
python telegram_parser_skill.py <команда> [опции]
```

## Команды

### channels — список доступных каналов

Выводит JSON со списком каналов, к которым у аккаунта есть доступ.

```powershell
python .\telegram_parser_skill.py channels
```

Опции (общие): `--session-file` (по умолчанию `telegram_session`).

**Пример вывода:**

```json
[
  { "id": -1001234567890, "username": "channel_name", "title": "Название канала" },
  ...
]
```

---

### resolve — получение id канала по ссылке или username

По ссылке на пост/канал, `@username` или числовому id возвращает информацию о канале: `id`, `username`, `title`; при ссылке на пост добавляется `post_id`.

```powershell
python .\telegram_parser_skill.py resolve --channel "https://t.me/AlgorithmPythonStruct/36"
python .\telegram_parser_skill.py resolve --channel @AlgorithmPythonStruct
python .\telegram_parser_skill.py resolve --channel 2614091536
```

**Пример вывода:**

```json
{
  "id": 2614091536,
  "username": "AlgorithmPythonStruct",
  "title": "Алгоритмы, структуры данных и олимпиадное программирование",
  "post_id": 36
}
```

---

### parse — парсинг канала

Скачивает историю сообщений и медиа, сохраняет в каталог экспорта. Поддерживает инкрементальный режим: повторный запуск дописывает только новые сообщения в тот же каталог.

**Обязательная опция:** `--channel` — канал в одном из форматов:

- Ссылка: `https://t.me/channelname/123` или `t.me/channelname`
- Username: `@channelname` или `channelname`
- Числовой id: `2614091536` или `-1001234567890`

**Примеры запуска:**

```powershell
# По ссылке на пост
python .\telegram_parser_skill.py parse --channel "https://t.me/AlgorithmPythonStruct/36"

# По username
python .\telegram_parser_skill.py parse --channel @AlgorithmPythonStruct

# С указанием каталога вывода
python .\telegram_parser_skill.py parse --channel @my_channel --output-dir D:\export\tg

# Только оценка объёма (без записи и загрузки медиа)
python .\telegram_parser_skill.py parse --channel @my_channel --dry-run

# Фильтр по датам
python .\telegram_parser_skill.py parse --channel @my_channel --date-from 2025-01-01 --date-to 2025-12-31

# Ограничение размера медиа и упаковка в ZIP
python .\telegram_parser_skill.py parse --channel @my_channel --max-media-size 50 --zip
```

## Опции команды parse

| Опция | Тип | По умолчанию | Описание |
|-------|-----|--------------|----------|
| `--channel` | строка | — | Канал: ссылка, @username или id (обязательно для `parse` и `resolve`) |
| `--mode` | `safe` \| `normal` | `safe` | Режим скорости и задержек; `safe` — осторожнее по лимитам API |
| `--date-from` | YYYY-MM-DD | — | Включить только сообщения не старше этой даты (UTC) |
| `--date-to` | YYYY-MM-DD | — | Включить только сообщения не новее этой даты (UTC) |
| `--keyword-filter` | слова… | — | Включить только сообщения, содержащие хотя бы одно из слов |
| `--max-media-size` | число (MB) | — | Не скачивать медиа крупнее указанного размера (МБ) |
| `--dry-run` | флаг | false | Только оценка: подсчёт сообщений/медиа, без записи и загрузки |
| `--zip` | флаг | false | После парсинга упаковать каталог экспорта в ZIP (без шифрования) |
| `--output-dir` | путь | см. ниже | Корневой каталог для экспорта |
| `--session-file` | строка | `telegram_session` | Имя файла сессии Telethon (без расширения) |
| `--no-cleanup-temp` | флаг | false | Не удалять временные файлы после загрузки медиа |

**Значение по умолчанию для `--output-dir`:** `D:\clawbot\ClawBot\outbox\telegram-parser\` (можно изменить в коде или всегда задавать явно).

## Формы запуска

1. **Интерактивно** — из корня проекта с активированным venv:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   python .\telegram_parser_skill.py parse --channel "https://t.me/..."
   ```

2. **С явным путём к Python venv** (без активации):
   ```powershell
   .\.venv\Scripts\python .\telegram_parser_skill.py parse --channel @channel
   ```

3. **С алиасами** (после `.\setup_aliases.ps1` и перезагрузки профиля):
   ```powershell
   telegram_parse --channel @channel --mode safe
   tgparse --channel "https://t.me/channel/1"
   ```

4. **Пакетный/фоновый запуск** — через планировщик задач или скрипт с нужными `--output-dir` и `--channel`.

## Коды выхода

Единая матрица для скриптов и оркестрации (константы в `exit_codes.py`):

| Код | Константа | Описание |
|-----|-----------|----------|
| 0 | EXIT_SUCCESS | Успешное выполнение команды |
| 1 | EXIT_FAILURE | Фатальная ошибка: конфиг, авторизация, неверные аргументы, необработанное исключение |
| 2 | EXIT_PARTIAL | Частичный успех: команда `parse` завершилась, но часть медиа не загружена (например file_reference_expired) |
| 130 | EXIT_INTERRUPTED | Прерывание пользователем (Ctrl+C) |

При использовании в скриптах проверяйте код выхода; при `EXIT_PARTIAL` данные и summary сохранены, но в `summary.media_errors_count` указано количество пропущенных медиа.

## Интеграция с OpenClaw

Маппинг чат-команд на скрипт:

- `/telegram_channels` → `python telegram_parser_skill.py channels`
- `/telegram_resolve ...` → `python telegram_parser_skill.py resolve --channel ...`
- `/telegram_parse ...` → `python telegram_parser_skill.py parse --channel ...`

Привязку к конфигу агента/скиллов настраивают отдельно.

## См. также

- [Форматы выходных файлов](output-formats.md) — структура каталога и JSON
- [Первоначальная настройка](setup.md)
