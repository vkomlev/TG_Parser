# Аудит архитектуры: TG_Parser + VK_Importer

Дата: 2026-02-21  
Фокус: расширяемость, DRY, обработка ошибок, коды выхода, логирование, стратегия масштабирования

---

## 1) Executive summary (коротко)

**Текущее состояние:**
- Связка уже рабочая для сценария **Telegram -> VK Video**.
- Базовая расширяемость присутствует (особенно в `VK_Importer`: парсеры как интерфейс + отдельный publisher слой).
- Но архитектура пока **продуктовая/скриптовая**, не платформенная: добавлять новые источники/получатели можно, но стоимость изменений будет быстро расти.

**Главный вывод:**
- **Не дробить сейчас на микросервисы.**
- Оставить модульный monolith, но сделать 1 рефакторинг-итерацию в сторону "plugin-like" контрактов:
  1. унифицировать доменную модель контента,
  2. выделить pipeline contracts (Source -> Normalize -> Store -> Publish),
  3. централизовать error taxonomy + exit codes,
  4. унифицировать structured logging/summary.

Это даст масштабирование на Rutube/YouTube/Дзен/WordPress/Telegram без операционной сложности микросервисов.

---

## 2) Что уже хорошо

## TG_Parser
- Чистый CLI слой (`telegram_parser_skill.py`) отдельно от ядра (`telegram_parser.py`).
- Хорошая устойчивость по Telegram API:
  - retry/backoff,
  - FloodWait handling,
  - timeout на media download,
  - special-case `FileReferenceExpiredError`.
- Прозрачный output contract (`export.json`, `state.json`, `media-index.json`, `summary.json`).
- Инкрементальность через `state.last_message_id`.

## VK_Importer
- Разделение по слоям: `parsers/`, `storage/`, `publisher/`, `title_generators/`.
- Есть `BaseParser` + несколько реализаций (HTML/JSON/custom export).
- `VideoStorage` уже служит как единая точка state management.
- У `VKPublisher` есть retry logic + token refresh callback hook.
- CLI покрывает production-операции (scan/upload/skip/unskip/update titles/folders).

---

## 3) Ключевые архитектурные риски для масштабирования

## 3.1 Сильная привязка доменной модели к "видео в VK"
`VideoData/VideoRecord` и flow ориентированы на один тип ассета и одного destination.

**Риск:** при добавлении, например, WordPress/Telegram-репостов/YouTube Shorts появятся ветки if/else по всей кодовой базе.

**Что нужно:** перейти к общей сущности публикации (например `ContentItem`) с поддержкой разных media types + destination-specific payload adapters.

## 3.2 Оркестрация пока сценарная, не контрактная
Сейчас pipeline хорошо работает, но логика связана с конкретными командами и конкретным маршрутом.

**Риск:** при 3-5 новых направлений вырастет дублирование шагов (scan/filter/skip/retry/report).

**Что нужно:** формализовать pipeline contracts:
- `SourceAdapter.fetch()`
- `Normalizer.transform()`
- `Repository.upsert()`
- `Publisher.publish()`
- `Reporter.emit()`

## 3.3 DRY-нарушения (особенно в CLI VK_Importer)
В `main.py` повторяется подготовка env/publisher/checks в нескольких командах upload/delete/update.

**Риск:** изменение политики токена/ретраев/валидации нужно делать в нескольких местах.

**Что нужно:** сервисный фасад (`PublishingService` / `AppContext`) для общих зависимостей.

## 3.4 Неполная дисциплина exit codes
Часть ошибок только печатается (`return`), без `sys.exit(1)`.

**Риск:** orchestrator может считать шаг успешным при фактическом сбое.

**Что нужно:** единая матрица кодов выхода + обязательное применение во всех командах.

## 3.5 Логирование: смешанный формат
Есть обычные текстовые логи и JSONL в TG_Parser, но нет единого pipeline-friendly формата на весь E2E.

**Риск:** сложно автоматизировать алерты, метрики, postmortem across projects.

**Что нужно:** унифицированный structured log schema + run correlation id.

---

## 4) Микросервисы vs модульный монолит

**Рекомендация: оставить модульный монолит на текущем этапе.**

Почему:
- Команда/контур небольшой.
- У вас уже есть OpenClaw orchestration + cron (операционный слой и так есть).
- Микросервисы добавят: деплой, сетевые контракты, observability stack, retry/idempotency на границах сервисов.

**Когда реально переходить к сервисам:**
- >3 независимых источника и >3 destination,
- параллельные команды разработки,
- отдельные SLA на ingestion/publishing,
- потребность в горизонтальном scale по очередям.

До этого — дешевле и безопаснее сделать «псевдо-сервисную» модульность внутри текущих реп.

---

## 5) Рекомендованный целевой blueprint (эволюционно)

## 5.1 Unified domain contract
Ввести общий контракт (пример):
- `ContentItem { source, external_id, published_at, text, media[], metadata }`
- `PublicationAttempt { destination, status, error_code, retry_count, remote_url }`

`VideoRecord` оставить как storage-реализацию, но логически перейти к более общей модели.

## 5.2 Adapter interfaces
- `SourceAdapter` (Telegram API, сайты RSS/scrape, VK source, etc.)
- `DestinationAdapter` (VK/Rutube/YouTube/Дзен/WP/TG)
- `PolicyEngine` (skip tags, dedup, windows, channel rules)

## 5.3 Pipeline runner contract
Каждый шаг возвращает:
- `StepResult { ok, stats, warnings, errors, artifacts, exit_code }`

А финальный раннер собирает единый `PipelineSummary`.

## 5.4 Error taxonomy
Единые коды/классы:
- `CONFIG_ERROR`
- `AUTH_ERROR`
- `RATE_LIMIT`
- `NETWORK_ERROR`
- `DATA_FORMAT_ERROR`
- `EXTERNAL_API_ERROR`
- `PARTIAL_FAILURE`

Сопоставление с process exit codes обязательно.

---

## 6) DRY-конкретика (что рефакторить первым)

1. **VK_Importer/main.py**
   - Вынести повторяющуюся инициализацию (`VK_ACCESS_TOKEN`, `VK_GROUP_ID`, publisher init, retry/delay defaults) в 1 helper/service.
2. **Date parsing/validation**
   - Единая функция в utils для `--since/--until` и любых date windows.
3. **Scan source registry**
   - Убрать hardcoded `tg_parser` folders из `get_export_paths`; заменить на конфиг/DB mapping.
4. **Course/channel mappings**
   - Централизовать mapping (сейчас он дублируется между scanner и CLI).
5. **Output summaries**
   - Унифицировать summary JSON для всех CLI-команд (не только scan).

---

## 7) Ошибки, коды выхода, логирование — целевое состояние

## 7.1 Exit codes (минимум)
- `0` — success
- `1` — fatal error (config/auth/runtime)
- `2` — partial failure (например часть upload не прошла)
- `130` — interrupted

## 7.2 Logging standard
Обязательные поля в structured logs:
- `ts`, `level`, `service`, `run_id`, `step`, `event`, `item_id`, `error_code`, `message`, `payload`

## 7.3 Correlation
`run_id` генерировать в orchestrator и пробрасывать во все шаги/процессы.

---

## 8) Пошаговый план внедрения (без ломки продакшена)

**Phase 1 (быстро, 1-2 дня):**
- Единая матрица exit codes.
- Привести все фатальные ошибки CLI к non-zero exit.
- Добавить единый summary JSON на команду.

**Phase 2 (2-4 дня):**
- Вынести `PublishingService/AppContext` в VK_Importer.
- Убрать дубли по env/publisher init.
- Централизовать mappings + source registry.

**Phase 3 (4-7 дней):**
- Ввести `ContentItem` и adapters interface.
- Переиспользовать текущие TG parser + VK publisher как первые адаптеры.
- Подготовить skeleton для 1 нового destination (например YouTube stub).

**Phase 4 (опционально):**
- Нормализованная очередь задач (SQLite job table/Redis later).
- Только после роста нагрузки — обсуждать физическое разделение сервисов.

---

## 9) Ответ на ключевой вопрос пользователя

**Текущую структуру оставлять или дробить?**
- **Сейчас: оставлять**, но сделать контрактный рефакторинг модульного монолита.
- **Дробить на сервисы — позже**, когда появятся объективные признаки масштаба (мульти-команда/мульти-SLA/нагрузка).

Так вы получите масштабируемость и DRY уже сейчас, без дорогой операционной сложности.

---

## 10) Примечание по памяти/контексту

Проверка `memory_search` в этой сессии выполнена, но инструмент недоступен из-за отсутствия API ключей; выводы основаны на текущем коде и документации репозиториев.

---

## 11) Документ по аудиту реализации и внедрению

Пошаговый аудит текущего кода TG_Parser, разрывы с целевой архитектурой и конкретный план внедрения (Phase 1–4) с чек-листом: **[AUDIT-IMPLEMENTATION-2026-02-21.md](AUDIT-IMPLEMENTATION-2026-02-21.md)**.
