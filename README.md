# TG_Parser

Парсер Telegram-каналов в JSON + медиа (фото/видео/документы) с безопасным режимом и апдейтом.

## Что реализовано
- Экспорт текста + медиа
- Структура хранения: `канал -> media/photos|videos|documents`
- Режим апдейта: добавление новых сообщений по `message_id` в **тот же последний каталог**
- `state.json` + `media-index.json` (SHA-256 дедупликация)
- `logs/run.log` и `logs/errors.log`
- `summary.json`
- `dry-run` (оценка объёма: `known_size_mb`, `unknown_size_count`)
- Режимы скорости: `safe` (default) и `normal`
- Обработка `FloodWait` + retry/backoff
- Опция `--zip` (без шифрования)

## Установка
```powershell
cd D:\work\TG_Parser
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# заполните .env
```

## CLI

### Список каналов
```powershell
python .\telegram_parser_skill.py channels
```

### Парсинг (базовый)
```powershell
python .\telegram_parser_skill.py parse --channel @my_channel
```

## Алиасы (интеграция)
В проект добавлены алиасы-обёртки:
- `telegram_channels.ps1`
- `telegram_parse.ps1`

Быстрая установка в PowerShell-профиль:
```powershell
.\setup_aliases.ps1
. $PROFILE
```

После этого доступны команды:
- `telegram_channels`
- `telegram_parse --channel @my_channel --mode safe`
- короткие: `tgch`, `tgparse`

### Парсинг с датами
```powershell
python .\telegram_parser_skill.py parse --channel @my_channel --date-from 2025-01-01 --date-to 2025-12-31
```

### Dry-run
```powershell
python .\telegram_parser_skill.py parse --channel @my_channel --dry-run
```

### Ограничение размера медиа + zip
```powershell
python .\telegram_parser_skill.py parse --channel @my_channel --max-media-size 50 --zip
```

## Опции
- `--mode safe|normal` (default: `safe`)
- `--date-from YYYY-MM-DD`
- `--date-to YYYY-MM-DD`
- `--keyword-filter word1 word2 ...`
- `--max-media-size <MB>`
- `--dry-run`
- `--zip`
- `--output-dir` (default: `D:\clawbot\ClawBot\outbox\telegram-parser\`)
- `--no-cleanup-temp`

## Структура результата
```text
D:\clawbot\ClawBot\outbox\telegram-parser\
└── channel_username__YYYY-MM-DD_HH-mm\
    ├── export.json
    ├── state.json
    ├── media-index.json
    ├── summary.json
    ├── logs\
    │   ├── run.log
    │   └── errors.log
    └── media\
        ├── photos\
        ├── videos\
        └── documents\
```

## Важно по безопасности
- Критичные данные хранятся только в `.env`
- Секреты не пишутся в логи
- Время в JSON/логах: ISO UTC (`YYYY-MM-DDTHH:mm:ssZ`)

## Чат-команды OpenClaw
Маппинг можно сделать так:
- `/telegram_channels` -> `python telegram_parser_skill.py channels`
- `/telegram_parse ...` -> `python telegram_parser_skill.py parse ...`

(привязку чат-команд к локальному скрипту можно добавить отдельным шагом в конфиге агента/skills)
