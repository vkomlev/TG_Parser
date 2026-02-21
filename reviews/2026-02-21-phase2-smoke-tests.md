# Review: Phase 2 — минимальный smoke-набор

**Дата:** 2026-02-21  

**Контекст:** Добавлен минимальный smoke-набор для Phase 2 (run_id, error_code): разделение на unit-only (моки, CI) и интеграционные (с Telegram).

**Новый файл:** `smoke_phase2.py`

**Сценарии:**
- **Unit-only** (`--unit-only`): 3 CONFIG_ERROR в app/errors.log, 5 EXTERNAL_API_ERROR в export logs, 6 PARTIAL_FAILURE в run_finished, 7 RATE_LIMIT при моке FloodWaitError.
- **Интеграционные**: 1 run_id в app.log, 2 run_id в export/summary, 4 AUTH_ERROR в errors.log.

**Реализация:**
- Тест 3: subprocess с `TELEGRAM_API_ID=""`, `TELEGRAM_API_HASH=""`, проверка exit 1 и наличия CONFIG_ERROR в logs (app.log или errors.log).
- Тесты 5, 6: парсер + connect + мок `download_media` (timeout / FileReferenceExpiredError), проверка export logs на EXTERNAL_API_ERROR и run_finished с PARTIAL_FAILURE.
- Тест 7: мок `client.__call__` — первый GetHistoryRequest поднимает FloodWaitWithSeconds (подкласс FloodWaitError с seconds=1), проверка export errors.log на flood_wait и RATE_LIMIT.
- Тесты 1, 2: subprocess `parse --dry-run`, проверка app.log на единый run_id и совпадение run_id в summary и export run.log.
- Тест 4: subprocess с `--session-file telegram_session_nonexistent_auth_test`, проверка exit 1 и AUTH_ERROR в errors.log.

**Примечания:** Тест 3 может падать, если в окружении .env перезаписывает пустые переменные. Тест 7 при изменении кода парсера может потребовать правки (мок GetHistory).

**Полный diff:** [2026-02-21-phase2-smoke-tests.diff](2026-02-21-phase2-smoke-tests.diff)
