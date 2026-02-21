# Review: Phase 2 — стабилизация smoke_phase2 и KeyError run_id в логах

**Дата:** 2026-02-21  

**Контекст:** Стабилизация `smoke_phase2.py` (тесты 3 и 7 проходят), устранение `KeyError: run_id` в логировании за счёт переноса `RunIdFilter` с root на хендлеры.

**Изменённые файлы:**

- **`smoke_phase2.py`**
  - **Тест 3:** проверка CONFIG_ERROR через `resolve` без `--channel` (детерминированно, без зависимости от .env override). Проверяется только **новый хвост** логов после запуска (размер файлов до/после, чтение только добавленного).
  - **Тест 7:** мок FloodWait срабатывает на **первом встреченном** `GetHistoryRequest`, а не на первом вызове клиента; мок `__call__` оставлен на уровне **класса** клиента (`client_cls`), в патче передаётся `this` (инстанс) в `original_call(this, request, ...)`.

- **`logging_setup.py`**
  - Фильтр `RunIdFilter` перенесён с `root.addFilter(RunIdFilter())` на **каждый хендлер**: `app_handler.addFilter(run_filter)` и `err_handler.addFilter(run_filter)`. Это устраняет `KeyError: run_id` в случаях, когда запись обрабатывается хендлерами, не прошедшими через фильтр root.

**Проверка:** `python smoke_phase2.py --unit-only` проходит полностью (PASS 3, 5, 6, 7).

**Полный diff** (smoke_phase2.py + logging_setup.py): [2026-02-21-phase2-smoke-stabilise-and-runid-filter.diff](2026-02-21-phase2-smoke-stabilise-and-runid-filter.diff)  
*(smoke_phase2.py мог быть не в индексе git — в .diff только изменённые отслеживаемые файлы.)*
