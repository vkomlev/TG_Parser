# Первоначальная настройка

## Требования

- Python 3.8+
- Доступ в интернет для Telegram API и загрузки зависимостей

## 1. Клонирование и окружение

```powershell
cd D:\Work\TG_Parser
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

На других ОС:

- Linux/macOS: `source .venv/bin/activate`

## 2. Переменные окружения (.env)

Создайте файл `.env` из шаблона:

```powershell
Copy-Item .env.example .env
```

Обязательные переменные:

| Переменная | Описание |
|------------|----------|
| `TELEGRAM_API_ID` | Числовой API ID приложения (получить на [my.telegram.org/apps](https://my.telegram.org/apps)) |
| `TELEGRAM_API_HASH` | Строка API Hash приложения |

Для первого входа в аккаунт:

| Переменная | Описание |
|------------|----------|
| `TELEGRAM_PHONE` | Номер телефона в международном формате, например `+79001234567` |

Опционально (двухфакторная аутентификация):

| Переменная | Описание |
|------------|----------|
| `TELEGRAM_2FA_PASSWORD` | Пароль 2FA. Если не задан, пароль запрашивается в консоли при входе |

Пример заполненного `.env`:

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_PHONE=+79001234567
TELEGRAM_2FA_PASSWORD=мой_пароль_2fa
```

**Важно:** не добавляйте `.env` в git и не передавайте его третьим лицам.

## 3. Получение API_ID и API_HASH

1. Откройте [https://my.telegram.org/apps](https://my.telegram.org/apps).
2. Войдите по номеру телефона.
3. Создайте приложение (если ещё не создано).
4. Скопируйте **api_id** и **api_hash** в `.env`.

## 4. Первый вход

Запустите любую команду, например список каналов:

```powershell
python .\telegram_parser_skill.py channels
```

При первом запуске:

1. В Telegram на указанный номер придёт код подтверждения.
2. Скрипт запросит ввод кода в консоль.
3. Если включена 2FA и `TELEGRAM_2FA_PASSWORD` не задан — будет запрошен пароль 2FA.

После успешного входа в корне проекта создаётся файл сессии Telethon (например `telegram_session.session`). Повторный ввод кода обычно не требуется, пока сессия действительна.

### Неинтерактивный первый вход (CI/скрипты)

Если переменная `TELEGRAM_CODE` не задана, скрипт отправит код в Telegram и завершится с сообщением о необходимости указать код. Хеш кода сохраняется в `logs/telegram_auth_state.json`. Задайте переменную и запустите снова:

```powershell
$env:TELEGRAM_CODE = "12345"
python .\telegram_parser_skill.py channels
```

## 5. Проверка

Убедитесь, что команда возвращает список каналов (JSON):

```powershell
python .\telegram_parser_skill.py channels
```

Получение информации о канале по ссылке:

```powershell
python .\telegram_parser_skill.py resolve --channel "https://t.me/AlgorithmPythonStruct/36"
```

## 6. Алиасы PowerShell (опционально)

Скрипты парсера лежат в `scripts/`. Для вызова без указания полного пути:

```powershell
.\scripts\setup_aliases.ps1
. $PROFILE
```

После этого доступны команды `telegram_channels`, `telegram_parse`, короткие алиасы `tgch`, `tgparse` (см. [CLI](cli.md)). Алиасы вызывают `scripts/telegram_parse.ps1` и `scripts/telegram_channels.ps1`; корень проекта определяется относительно расположения скриптов, поэтому запуск возможен из любого каталога.

## См. также

- [auth-2fa-env-setup.md](auth-2fa-env-setup.md) — подробнее про 2FA и первый вход
- [CLI и формы запуска](cli.md)
