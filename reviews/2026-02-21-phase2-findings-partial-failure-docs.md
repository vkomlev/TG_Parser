# Review: Phase 2 — findings (PARTIAL_FAILURE + синхронизация доков)

**Дата:** 2026-02-21  

**Контекст:** Учёт findings по Phase 2: (1) явное использование `PARTIAL_FAILURE` в логах при частичном успехе — в ядре при `run_finished` передаётся `error_code=PARTIAL_FAILURE`, если `partial_failure`; (2) синхронизация документации с реализацией: `docs/functions.md` и `docs/logging.md` приведены к актуальной сигнатуре и примерам (`run_id`, `setup_app_logging(..., run_id=...)`, `run(args, run_id=...)`, описание `run_finished` с `error_code: PARTIAL_FAILURE`).

**Изменённые файлы в этом раунде:**
- `telegram_parser.py` — у `JsonLogger.info()` добавлен параметр `error_code`; вызов `logs.info("run_finished", summary, error_code=PARTIAL_FAILURE if partial_failure else None)`.
- `docs/functions.md` — в описании `main()` и `run()` добавлены `run_id`, актуальная сигнатура `setup_app_logging(logs_dir, level=..., run_id=None)` и вызов с `run_id`.
- `docs/logging.md` — пример вызова `setup_app_logging(..., run_id=run_id)`; у события `run_finished` указано наличие `error_code: "PARTIAL_FAILURE"` при частичном успехе.

**Фрагмент изменений (telegram_parser.py):**

```diff
     def info(self, event: str, payload: Optional[Dict[str, Any]] = None) -> None:
-        self._run_logger.info(self._record("INFO", event, payload))
+    def info(
+        self,
+        event: str,
+        payload: Optional[Dict[str, Any]] = None,
+        error_code: Optional[str] = None,
+    ) -> None:
+        self._run_logger.info(self._record("INFO", event, payload, error_code))
...
-        logs.info("run_finished", summary)
+        logs.info(
+            "run_finished",
+            summary,
+            error_code=PARTIAL_FAILURE if partial_failure else None,
+        )
```

**Полный diff** (все незакоммиченные изменения на момент сохранения): [2026-02-21-phase2-findings-partial-failure-docs.diff](2026-02-21-phase2-findings-partial-failure-docs.diff)
