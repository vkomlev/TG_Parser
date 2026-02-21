# Форматы выходных файлов

Результат парсинга сохраняется в каталог вида `{output_dir}/{channel_slug}__{YYYY-MM-DD_HH-mm}`. При повторном запуске для того же канала используется **последний** такой каталог (режим обновления).

## Структура каталога экспорта

```text
{output_dir}/
└── {channel_slug}__YYYY-MM-DD_HH-mm\
    ├── export.json          # Сообщения и метаданные канала
    ├── state.json           # Состояние для инкрементального обновления
    ├── media-index.json     # Дедупликация медиа по SHA-256
    ├── summary.json         # Итоги последнего запуска
    ├── logs\
    │   ├── run.log          # JSONL-события парсинга
    │   └── errors.log       # JSONL-ошибки
    └── media\
        ├── photos\
        ├── videos\
        └── documents\
```

- **channel_slug** — `@username` канала (без @) или `channel_{id}` для каналов без username.
- В режиме `--dry-run` создаётся только каталог, `summary.json` и логи; `export.json`, `state.json`, `media-index.json` и файлы в `media/` не создаются.

---

## export.json

Содержит информацию о канале и массив сообщений.

### Корневые поля

| Поле | Тип | Описание |
|------|-----|----------|
| `channel_info` | объект | Id, username и название канала |
| `messages` | массив | Сообщения в порядке возрастания id |
| `export_date` | строка | Дата/время последнего обновления экспорта (ISO UTC) |
| `total_messages` | число | Количество сообщений в массиве |

### channel_info

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | число | Числовой id канала |
| `username` | строка \| null | Username канала (без @) или null |
| `title` | строка \| null | Название канала |

### Элемент messages[]

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | число | Id сообщения в канале |
| `date` | строка | Дата сообщения (ISO UTC, `YYYY-MM-DDTHH:mm:ssZ`) |
| `text` | строка | Текст сообщения |
| `media_files` | массив | Прикреплённые медиа (см. ниже) |
| `forwarded` | объект \| null | Данные о пересланном сообщении |
| `reply_to_msg_id` | число \| null | Id сообщения, на которое отвечает |
| `views` | число \| null | Просмотры |
| `forwards` | число \| null | Пересылки |

### media_files[]

Каждый элемент — объект:

| Поле | Тип | Описание |
|------|-----|----------|
| `type` | строка | `"photo"`, `"video"` или `"document"` |
| `path` | строка \| null | Относительный путь к файлу от корня каталога экспорта (например `media/videos/2_...webm`) или null при ошибке/пропуске |
| `filename` | строка \| null | Имя файла или null |
| `size` | число | Размер в байтах (может отсутствовать при дедупле) |
| `sha256` | строка | SHA-256 файла (для дедупликации; может отсутствовать) |
| `error` | строка | При пропуске загрузки: `"file_reference_expired"`, `"download_timeout"` (исчерпан retry по таймауту), `"retry_exhausted"` (другая ошибка после retry) |

При дедупликации в элементе может быть только `type`, `path`, `filename`, `sha256` (без `size`). Если загрузка не удалась, в элементе указывается `error` и `path: null`; при этом парсинг продолжается и в итоге возвращается код выхода 2 (partial failure).

### forwarded (если есть)

| Поле | Тип | Описание |
|------|-----|----------|
| `from_name` | строка \| null | Имя источника |
| `date` | строка \| null | Дата пересылки (ISO UTC) |
| `channel_post_id` | число \| null | Id поста в канале-источнике |
| `post_author` | строка \| null | Автор поста |

**Пример фрагмента export.json:**

```json
{
  "channel_info": {
    "id": 2614091536,
    "username": "AlgorithmPythonStruct",
    "title": "Алгоритмы, структуры данных и олимпиадное программирование"
  },
  "messages": [
    {
      "id": 2,
      "date": "2025-06-04T13:59:41Z",
      "text": "Текст сообщения...",
      "media_files": [
        {
          "type": "video",
          "path": "media/videos/2_запись.webm",
          "filename": "2_запись.webm",
          "size": 35830456,
          "sha256": "1bc701bf2e..."
        }
      ],
      "forwarded": null,
      "reply_to_msg_id": null,
      "views": 43,
      "forwards": 1
    }
  ],
  "export_date": "2026-02-17T18:57:17Z",
  "total_messages": 35
}
```

---

## state.json

Используется для инкрементального обновления: следующий запуск парсинга того же канала дописывает только сообщения новее `last_message_id`.

| Поле | Тип | Описание |
|------|-----|----------|
| `channel_id` | число | Id канала |
| `channel_username` | строка \| null | Username канала |
| `last_message_id` | число | Максимальный id сообщения в экспорте |
| `last_update_at` | строка \| null | Время последнего обновления (ISO UTC) |
| `messages_total` | число | Количество сообщений в export |
| `media_total` | число | Общее количество записей в media_files по всем сообщениям |

**Пример:**

```json
{
  "channel_id": 2614091536,
  "channel_username": "AlgorithmPythonStruct",
  "last_message_id": 36,
  "last_update_at": "2026-02-17T18:57:17Z",
  "messages_total": 70,
  "media_total": 62
}
```

---

## media-index.json

Дедупликация медиа по SHA-256: один и тот же файл (по хешу) хранится один раз, в остальных сообщениях указывается путь к уже сохранённому файлу.

| Поле | Тип | Описание |
|------|-----|----------|
| `sha256_to_path` | объект | Соответствие SHA-256 (строка) → относительный путь к файлу |

Формат ключа: строка SHA-256 в hex. Значение: строка пути относительно корня каталога экспорта, например `media/videos/2_file.webm`.

---

## summary.json

Итоги **последнего** запуска парсинга (в т.ч. dry-run). Перезаписывается при каждом запуске.

| Поле | Тип | Описание |
|------|-----|----------|
| `run_at` | строка | Время запуска (ISO UTC) |
| `channel_id` | число | Id канала |
| `channel_username` | строка \| null | Username канала |
| `mode` | строка | Режим: `safe` или `normal` |
| `dry_run` | логический | Был ли запуск в режиме dry-run |
| `date_from` | строка \| null | Опция `--date-from` |
| `date_to` | строка \| null | Опция `--date-to` |
| `scanned_messages` | число | Всего просмотрено сообщений в этом запуске |
| `new_messages` | число | Добавлено новых сообщений в экспорт |
| `media_saved` | число | Скачано файлов медиа |
| `media_skipped_by_size` | число | Пропущено из-за `--max-media-size` |
| `media_dedup_hits` | число | Использовано уже сохранённых по SHA-256 |
| `media_errors_count` | число | Количество медиа, не загруженных из-за ошибки (например file_reference_expired) |
| `partial_failure` | логический | true, если был хотя бы один сбой загрузки медиа при успешном завершении прогона (CLI при этом возвращает код 2) |
| `known_size_mb` | число | Суммарный известный размер медиа (МБ) |
| `unknown_size_count` | число | Количество медиа с неизвестным размером |
| `flood_wait_events` | число | Срабатываний FloodWait |
| `export_dir` | строка | Абсолютный путь к каталогу экспорта |

**Пример:**

```json
{
  "run_at": "2026-02-17T18:57:17Z",
  "channel_id": 2614091536,
  "channel_username": "AlgorithmPythonStruct",
  "mode": "safe",
  "dry_run": false,
  "date_from": null,
  "date_to": null,
  "scanned_messages": 35,
  "new_messages": 35,
  "media_saved": 31,
  "media_skipped_by_size": 0,
  "media_dedup_hits": 0,
  "known_size_mb": 639.162,
  "unknown_size_count": 1,
  "flood_wait_events": 0,
  "export_dir": "D:\\Work\\TG_Parser\\out\\AlgorithmPythonStruct__2026-02-17_19-32"
}
```

---

## Кодировка и время

- Все JSON-файлы: UTF-8.
- Все даты и время: UTC в формате ISO 8601 `YYYY-MM-DDTHH:mm:ssZ`.
