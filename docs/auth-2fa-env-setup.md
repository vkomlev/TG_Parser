# Настройка авторизации и .env (включая 2FA)

## 1) Подготовка
1. Перейдите в каталог проекта:
   - `cd D:\work\TG_Parser`
2. Создайте `.env` из шаблона:
   - `Copy-Item .env.example .env`

## 2) Получение API_ID/API_HASH
1. Откройте: https://my.telegram.org/apps
2. Создайте приложение (если не создано)
3. Скопируйте:
   - `api_id`
   - `api_hash`

## 3) Заполнение .env
Откройте `.env` и заполните:

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_PHONE=+7XXXXXXXXXX
TELEGRAM_2FA_PASSWORD=ВАШ_ПАРОЛЬ_2FA
```

Примечания:
- `TELEGRAM_PHONE` обязателен для первого входа.
- `TELEGRAM_2FA_PASSWORD`:
  - если заполнен — скрипт возьмёт пароль из `.env`;
  - если пусто — скрипт запросит пароль интерактивно.
- Не отправляйте `.env` в git/мессенджеры.

## 4) Первый вход (код + пароль)
Запустите любую команду, например:

```powershell
python .\telegram_parser_skill.py channels
```

Что произойдет:
1. Telegram отправит код на номер `TELEGRAM_PHONE`.
2. Скрипт попросит ввести код в консоль.
3. Если включена 2FA:
   - возьмёт пароль из `TELEGRAM_2FA_PASSWORD`, либо
   - попросит ввести пароль вручную.

После успешного входа создастся session-файл (`telegram_session*`).

## 5) Повторные запуски
- Обычно код/пароль больше не нужны, пока сессия валидна.
- Если сессию удалить/протухнет — повторите шаг 4.

## 6) Быстрые команды
- Список каналов:
  - `python .\telegram_parser_skill.py channels`
- Парсинг:
  - `python .\telegram_parser_skill.py parse --channel @my_channel`

## 7) Алиасы (PowerShell)
1. Выполните:
   - `.\setup_aliases.ps1`
2. Перезагрузите профиль:
   - `. $PROFILE`
3. Используйте:
   - `telegram_channels`
   - `telegram_parse --channel @my_channel --mode safe`
