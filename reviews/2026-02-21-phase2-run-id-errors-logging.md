# Review: Phase 2 — run_id, таксономия ошибок, структурированный лог

**Дата:** 2026-02-21  

**Контекст:** Реализация раздела 4.2 аудита (AUDIT-IMPLEMENTATION-2026-02-21): (1) run_id (correlation id) в main → run → parse_channel и во все записи логов; (2) таксономия ошибок в модуле `errors.py` и использование кодов в CLI/ядре (CONFIG_ERROR, AUTH_ERROR, EXTERNAL_API_ERROR, RATE_LIMIT, PARTIAL_FAILURE); (3) app.log с полями run_id и error_code (текстовый лог сохранён, добавлены run_id и error_code).

**Новый файл:**
- `errors.py` — константы: CONFIG_ERROR, AUTH_ERROR, RATE_LIMIT, NETWORK_ERROR, DATA_FORMAT_ERROR, EXTERNAL_API_ERROR, PARTIAL_FAILURE.

**Изменённые файлы:**
- `telegram_parser_skill.py` — генерация run_id в main(), передача в setup_app_logging и run(args, run_id); parse_channel(..., run_id=run_id); log.error(..., extra={"error_code": CONFIG_ERROR}) при отсутствии API/channel; перехват RuntimeError (авторизация) с error_code=AUTH_ERROR.
- `logging_setup.py` — contextvar run_id, RunIdFilter (run_id + error_code в record), setup_app_logging(logs_dir, run_id=...), AppLogFormatter с выводом error_code при отличии от "-".
- `telegram_parser.py` — импорт errors; JsonLogger(logs_dir, run_id=...), _record(..., error_code=...), error(event, payload, error_code=...); parse_channel(..., run_id=None), summary["run_id"]=run_id; во все вызовы logs.error/logger.error добавлен error_code (EXTERNAL_API_ERROR, RATE_LIMIT).
- `docs/output-formats.md` — поле run_id в таблице и примере summary.json.
- `docs/logging.md` — формат app.log с run_id и error_code; описание полей data (run_id, error_code) в логах экспорта.

**Новый файл `errors.py` (полностью):**

```python
"""Таксономия кодов ошибок для логов и контрактов."""
CONFIG_ERROR = "CONFIG_ERROR"
AUTH_ERROR = "AUTH_ERROR"
RATE_LIMIT = "RATE_LIMIT"
NETWORK_ERROR = "NETWORK_ERROR"
DATA_FORMAT_ERROR = "DATA_FORMAT_ERROR"
EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"
PARTIAL_FAILURE = "PARTIAL_FAILURE"
```

**Фрагмент изменений в `logging_setup.py`:** добавлены contextvar `_run_id_ctx`, `RunIdFilter`, `set_run_id`/`get_run_id`, параметр `run_id` в `setup_app_logging`, `AppLogFormatter` с выводом `error_code` при отличии от "-".

**Полный diff** (изменённые файлы на момент сохранения): [2026-02-21-phase2-run-id-errors-logging.diff](2026-02-21-phase2-run-id-errors-logging.diff)  
*(Новый файл `errors.py` в git diff не попадает до `git add`; содержимое см. выше.)*
