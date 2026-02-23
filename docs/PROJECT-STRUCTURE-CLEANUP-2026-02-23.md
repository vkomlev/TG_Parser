# Анализ структуры проекта TG_Parser — упорядочивание

**Дата:** 2026-02-23

## Текущее состояние

### В корне проекта

| Тип | Файлы/папки |
|-----|----------------|
| **Ядро приложения** | `telegram_parser.py`, `telegram_parser_skill.py`, `adapters.py`, `contracts.py`, `errors.py`, `exit_codes.py`, `logging_setup.py`, `session_lock.py` |
| **Смоук-тесты** | `smoke_phase1.py`, `smoke_phase2.py`, `smoke_phase3.py`, `smoke_session_stability.py` |
| **Скрипты PowerShell** | `telegram_parse.ps1`, `telegram_channels.ps1`, `setup_aliases.ps1` |
| **Конфиг/среда** | `.env.example`, `requirements.txt`, `.gitignore` |
| **Документация в корне** | `README.md`, `AUTH_2FA_ENV_SETUP.md`, `SKILL.md` |
| **Временные/артефакты** | `out`, `out_init`, `out_smoke_phase1`, `out_smoke_phase2`, `out_smoke_phase3`, `logs`, `__pycache__`, `videos.db`, `*.session` |

Папки `out*` и `videos.db` в `.gitignore` не были — их стоит добавить, чтобы не коммитить артефакты.

---

## 1. Что разместить в подпапки

### 1.1 Смоук-тесты → `tests/` или `smoke/`

- **Файлы:** `smoke_phase1.py`, `smoke_phase2.py`, `smoke_phase3.py`, `smoke_session_stability.py`
- **Зачем:** отделить тесты от основного кода, в корне остаётся только точка входа и модули.
- **Важно:** в скриптах заданы пути вида `Path(__file__).parent / "out_smoke_phase1"`. При переносе тестов нужно либо:
  - оставить выход тестов в корне (например `Path(__file__).parent.parent / "out_smoke_phase1"`), либо
  - выносить все артефакты в одну папку, например `tests/out/` или общую `out/` с подпапками по фазам.
- **Рекомендация:** завести папку `tests/`, положить туда все `smoke_*.py`, общую выходную папку для смоук-тестов добавить в `.gitignore` (например `tests/out/` или оставить `out_smoke_*` в корне и добавить в `.gitignore`).

### 1.2 PowerShell-скрипты → `scripts/`

- **Файлы:** `telegram_parse.ps1`, `telegram_channels.ps1`, `setup_aliases.ps1`
- **Плюс:** в корне остаются только Python-модули, README и конфиг.
- **Минус:** нужно обновить пути в `docs/setup.md` и в `SKILL.md` (например `.\scripts\setup_aliases.ps1`, `.\scripts\telegram_parse.ps1`). Алиасы в профиле пользователя тоже придётся править при следующей настройке.
- **Рекомендация:** перенос в `scripts/` опционален; если хочется минимальных правок — скрипты можно оставить в корне.

### 1.3 Документация по 2FA → в `docs/`

- **Файл:** `AUTH_2FA_ENV_SETUP.md`
- **Действие:** переместить в `docs/` (например `docs/auth-2fa-env-setup.md`), в `docs/setup.md` заменить ссылку `../AUTH_2FA_ENV_SETUP.md` на `auth-2fa-env-setup.md`.
- **Рекомендация:** сделать — дублирования с `docs/setup.md` нет, это расширенная инструкция, логично держать её в `docs/`.

---

## 2. Что можно смело удалять

### 2.1 Папки артефактов (после добавления в .gitignore)

- `out`, `out_init`, `out_smoke_phase1`, `out_smoke_phase2`, `out_smoke_phase3` — результаты парсинга и смоук-тестов. Пересоздаются при запуске.
- **Действие:** добавить их в `.gitignore`, затем удалить папки с диска. Если они уже были закоммичены — после добавления в `.gitignore` выполнить `git rm -r --cached out out_init out_smoke_phase1 out_smoke_phase2 out_smoke_phase3` (при необходимости).

### 2.2 Файлы кэша и рантайма

- `__pycache__/` — уже в `.gitignore`, при желании можно удалить с диска (`Remove-Item -Recurse -Force __pycache__`).
- `logs/` — уже в `.gitignore`, содержимое можно чистить по мере надобности.
- Файлы `*.session`, `telegram_session*.session` — уже в `.gitignore, не коммитить и не переносить в репозиторий.

### 2.3 База `videos.db`

- Сейчас **отслеживается в git** (попала в репозиторий).
- По коду и тестам не используется — похоже на локальный артефакт или старый тест.
- **Рекомендация:** добавить `videos.db` в `.gitignore`, удалить из индекса: `git rm --cached videos.db`. Саму базу с диска можно удалить, если она не нужна локально.

---

## 3. Что сохранить (на функциональность не влияет, но полезно)

- **`reviews/`** — по правилам проекта сюда сохраняются артефакты ревью (diff и краткие отчёты). Не трогать.
- **`docs/`** — вся текущая документация (setup, CLI, форматы, логирование, аудиты, TZ). Оставить как есть.
- **`SKILL.md`** в корне — описание скилла для Cursor/Codex; на запуск парсера не влияет, но нужно для AI/интеграций. Оставить в корне или при желании перенести в `.cursor/` (тогда нужно обновить ссылки на скилл).
- **`AUTH_2FA_ENV_SETUP.md`** — перед переносом в `docs/` не удалять; после переноса в `docs/` удалить из корня и обновить ссылку в `docs/setup.md`.

---

## 4. Краткий чек-лист действий

| Действие | Риск | Рекомендация |
|----------|------|--------------|
| Добавить в `.gitignore`: `out/`, `out_init/`, `out_smoke_phase1/`, `out_smoke_phase2/`, `out_smoke_phase3/`, `videos.db` | Нет | **Сделать** |
| Удалить с диска папки `out`, `out_init`, `out_smoke_phase*` | Нет (пересоздаются) | По желанию |
| Убрать `videos.db` из git (`git rm --cached`) и с диска | Нет, если база не нужна | **Рекомендуется** |
| Перенести `AUTH_2FA_ENV_SETUP.md` в `docs/` | Нет | **Сделать** |
| Перенести `smoke_*.py` в `tests/` | Нужно править пути в скриптах | По желанию |
| Перенести `.ps1` в `scripts/` | Нужно править docs и алиасы | По желанию |

Ниже в репозитории выполнены: обновление `.gitignore` и перенос `AUTH_2FA_ENV_SETUP.md` в `docs/` с обновлением ссылки в `docs/setup.md`.
