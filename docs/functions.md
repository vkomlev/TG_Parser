# Описание основных функций и классов

Краткое описание публичных функций и классов модулей парсера для разработчиков и интеграции.

---

## Модуль `telegram_parser`

### Вспомогательные функции

**`utc_now_iso() -> str`**  
Возвращает текущее время в UTC в формате ISO 8601: `YYYY-MM-DDTHH:mm:ssZ`.

**`parse_date_utc(date_str: Optional[str]) -> Optional[datetime]`**  
Парсит строку даты `YYYY-MM-DD` и возвращает `datetime` в полночь UTC. Для `None` или пустой строки возвращает `None`.

**`sanitize_name(value: str) -> str`**  
Приводит строку к безопасному имени файла/каталога: удаляет недопустимые символы Windows, заменяет пробелы на подчёркивания, схлопывает повторные подчёркивания.

**`parse_telegram_link(link: str) -> Optional[Tuple[str, Optional[int]]]`**  
Извлекает из ссылки t.me/telegram.me/telegram.dog username канала и опционально номер поста.

- Вход: строка вида `https://t.me/channelname/123` или `t.me/channelname`.
- Выход: `(username, post_id)` или `None`, если строка не является ссылкой. `post_id` — число или `None`.

**`channel_identifier_from_input(identifier: str) -> Tuple[str, Optional[int]]`**  
Нормализует ввод пользователя для резолва канала.

- Если переданная строка — ссылка t.me, возвращает `(@username, post_id)`.
- Иначе возвращает `(identifier.strip(), None)` (например, для @username или числового id).

**`iso_from_telethon_date(dt: Optional[datetime]) -> Optional[str]`**  
Преобразует дату/время Telethon в строку ISO UTC.

---

### Класс `ModeConfig` и пресеты

**`MODE_PRESETS`** — словарь режимов скорости: `"safe"` и `"normal"`. Каждый пресет задаёт задержки между запросами, доп. задержку при FloodWait, число повторов и т.д.

---

### Класс `JsonLogger`

Логгер, пишущий события в виде одной JSON-строки на запись (JSONL) в два файла с ротацией.

- **Конструктор:** `JsonLogger(logs_dir: Path, *, max_bytes=2*1024*1024, backup_count=10)`  
  `logs_dir` — каталог, в котором создаются `run.log` и `errors.log`.

- **Методы:**  
  - `info(event: str, payload: Optional[Dict] = None)` — запись в run.log.  
  - `error(event: str, payload: Optional[Dict] = None)` — запись в errors.log.

Формат записи: `{"ts": "<ISO UTC>", "level": "INFO"|"ERROR", "event": "<event>", "data": {...}}`.

---

### Класс `TelegramParser`

Основной класс для работы с Telegram API и парсингом канала.

**Конструктор:**  
`TelegramParser(api_id, api_hash, session_file="telegram_session", auth_state_dir=None)`  
- `auth_state_dir` — каталог для сохранения состояния авторизации (например `logs/`) при неинтерактивном первом входе.

**Методы:**

- **`async connect() -> None`**  
  Подключение к Telegram, при необходимости — запрос кода и 2FA. Использует `.env` и опционально `auth_state_dir`.

- **`async disconnect() -> None`**  
  Отключение клиента.

- **`async get_available_channels() -> List[Dict]`**  
  Возвращает список каналов, доступных аккаунту. Каждый элемент: `{"id", "username", "title"}`.

- **`async get_channel_info(link_or_identifier: str) -> Dict`**  
  По ссылке, @username или id возвращает информацию о канале: `id`, `username`, `title`; при ссылке на пост — также `post_id`.

- **`async parse_channel(...) -> Dict`**  
  Парсинг канала: загрузка истории и медиа, запись в export/state/media-index/summary и логи.  
  Параметры: `channel_identifier`, `output_dir`, `mode="safe"`, `date_from`, `date_to`, `keyword_filter`, `max_media_size_mb`, `dry_run`, `zip_output`, `cleanup_temp`.  
  Возвращает словарь с путями к файлам и сводкой (аналог `summary`).

Внутри используются: `_resolve_entity` (резолв канала по ссылке/username/id), `_with_retries` (повторы с учётом FloodWait и без ретраев для FileReferenceExpiredError), периодическое сохранение export/state после каждой пачки сообщений и обработка FileReferenceExpiredError (обновление сообщения и повторная попытка загрузки или пропуск с записью в лог и в export).

---

## Модуль `telegram_parser_skill`

CLI-обёртка: парсинг аргументов, загрузка `.env`, настройка логов, вызов методов `TelegramParser`.

- **`build_parser() -> argparse.ArgumentParser`**  
  Создаёт парсер аргументов с командами `channels`, `resolve`, `parse` и всеми опциями (см. [CLI](cli.md)).

- **`main() -> int`**  
  Точка входа: настройка UTF-8 для stdout/stderr, загрузка `.env`, генерация `run_id` (короткий UUID), `setup_app_logging(logs_dir, run_id=run_id)`, разбор аргументов и запуск `asyncio.run(run(args, run_id=run_id))`. Обрабатывает `KeyboardInterrupt` и общие исключения, возвращает код выхода 0/1/2/130.

- **`async run(args, run_id=None) -> int`**  
  Выполняет команду: `channels` → `get_available_channels()`, `resolve` → `get_channel_info()`, `parse` → `parse_channel(..., run_id=run_id)`. Результат выводится в stdout в виде JSON (UTF-8).

---

## Модуль `logging_setup`

**`setup_app_logging(logs_dir: Path, level=logging.INFO, run_id=None) -> None`**  
Настраивает глобальное логирование в каталог `logs_dir`: создаёт `app.log` и `errors.log` с ротацией (2 МБ, 10 файлов), формат с временем в UTC и полями `run_id`, `error_code` (см. [Логирование](logging.md)). При передаче `run_id` он добавляется во все записи лога. Вызов идемпотентен: повторные вызовы не добавляют дублирующих обработчиков.

---

## Зависимости

- **telethon** — клиент Telegram API.
- **python-dotenv** — загрузка `.env`.
- Стандартная библиотека: `asyncio`, `json`, `logging`, `pathlib`, `re`, `hashlib`, `zipfile`, `shutil` и др.

---

## См. также

- [CLI и формы запуска](cli.md)
- [Форматы выходных файлов](output-formats.md)
- [Логирование](logging.md)
