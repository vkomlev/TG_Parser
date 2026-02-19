---
name: telegram-channel-parser
description: Парсинг Telegram-каналов в JSON с загрузкой медиа, инкрементальным обновлением и поддержкой запуска по ссылке на пост/канал (t.me/.../123), @username или id. Используй, когда нужно: (1) получить список доступных каналов, (2) определить канал по ссылке, (3) выгрузить сообщения и медиа в структурированный экспорт, (4) выполнить dry-run оценку объёма.
---

# Telegram Channel Parser Skill

## Быстрые команды

Точка входа: `telegram_parser_skill.py`

```powershell
python .\telegram_parser_skill.py channels
python .\telegram_parser_skill.py resolve --channel "https://t.me/AlgorithmPythonStruct/36"
python .\telegram_parser_skill.py parse --channel "https://t.me/AlgorithmPythonStruct/36"
```

## Что поддерживается

- Форматы `--channel`:
  - ссылка на пост/канал: `https://t.me/channel/123`, `t.me/channel`
  - username: `@channelname`, `channelname`
  - id: `2614091536`, `-100...`
- Инкрементальный режим (дозагрузка новых сообщений в последний каталог канала)
- Дедупликация медиа по SHA-256 (`media-index.json`)
- Логи приложения и логи конкретного прогона (JSONL)
- Обработка FloodWait и retry
- Dry-run, фильтр по датам, фильтр по ключевым словам, лимит размера медиа, ZIP

## Основные опции parse

- `--channel` (обязательно)
- `--mode safe|normal` (по умолчанию `safe`)
- `--date-from YYYY-MM-DD`
- `--date-to YYYY-MM-DD`
- `--keyword-filter ...`
- `--max-media-size <MB>`
- `--dry-run`
- `--zip`
- `--output-dir <path>`
- `--session-file <name>`
- `--no-cleanup-temp`

## Результат выгрузки

Каталог экспорта:

```text
{output_dir}/{channel_slug}__YYYY-MM-DD_HH-mm/
```

Ключевые файлы:

- `export.json` — канал + массив сообщений
- `state.json` — состояние инкрементального обновления
- `media-index.json` — индекс дедупликации SHA-256
- `summary.json` — итог последнего запуска
- `logs/run.log`, `logs/errors.log` — JSONL-логи прогона
- `media/photos|videos|documents` — скачанные файлы

## Интеграция с OpenClaw

Маппинг команд:

- `/telegram_channels` → `python D:\work\TG_Parser\telegram_parser_skill.py channels`
- `/telegram_parse ...` → `python D:\work\TG_Parser\telegram_parser_skill.py parse ...`

Если нужен явный резолв ссылки в чате, добавь алиас `/telegram_resolve ...` на команду:

```powershell
python D:\work\TG_Parser\telegram_parser_skill.py resolve --channel ...
```

## Где смотреть детали

- `docs/setup.md` — первичная настройка и 2FA
- `docs/cli.md` — команды и опции
- `docs/output-formats.md` — схема выходных файлов
- `docs/logging.md` — логирование и ротация
- `docs/functions.md` — функции/классы для разработки
