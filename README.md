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

## Документация

| Раздел | Описание |
|--------|----------|
| [**Первоначальная настройка**](docs/setup.md) | Окружение, `.env`, первый вход, 2FA |
| [**CLI и формы запуска**](docs/cli.md) | Команды `channels`, `resolve`, `parse`, все опции и примеры |
| [**Форматы выходных файлов**](docs/output-formats.md) | `export.json`, `state.json`, `media-index.json`, `summary.json`, структура каталога |
| [**Логирование**](docs/logging.md) | Формат логов, ротация, расположение файлов |
| [**Описание функций**](docs/functions.md) | Основные функции и классы модулей парсера |

## Безопасность

- Учётные данные хранятся только в `.env` (файл в `.gitignore`)
- Секреты не выводятся в логи
- Время в JSON и логах — UTC в формате ISO (`YYYY-MM-DDTHH:mm:ssZ`)

## Интеграция

- **OpenClaw / скиллы**: команды можно сопоставить с `telegram_parser_skill.py` (см. [CLI](docs/cli.md))
- **PowerShell-алиасы**: `.\setup_aliases.ps1` и перезагрузка профиля — см. [Настройка](docs/setup.md)
