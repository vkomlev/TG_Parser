# Review: Phase 1 — коды выхода и partial failure

**Дата:** 2026-02-21  

**Контекст:** Внедрение Phase 1 по [AUDIT-IMPLEMENTATION-2026-02-21.md](../docs/AUDIT-IMPLEMENTATION-2026-02-21.md): единая матрица кодов выхода, признак частичного успеха (partial failure) для команды `parse`, обновление документации.

**Изменённые файлы:**
- Добавлен модуль `exit_codes.py` (новый файл; содержимое приведено ниже для воспроизводимости).
- `telegram_parser.py` — счётчик `media_errors_count`, поля `partial_failure` и `media_errors_count` в summary и в возвращаемом значении.
- `telegram_parser_skill.py` — импорт констант выхода, возврат `EXIT_SUCCESS`/`EXIT_FAILURE`/`EXIT_PARTIAL`/`EXIT_INTERRUPTED` вместо 0/1/130; для `parse` при `partial_failure` возвращается код 2.
- `README.md` — блок «Коды выхода».
- `docs/README.md` — ссылки на аудит-документы.
- `docs/cli.md` — таблица кодов выхода и описание EXIT_PARTIAL.
- `docs/output-formats.md` — поля `media_errors_count` и `partial_failure` в summary.
- `docs/AUDIT-IMPLEMENTATION-2026-02-21.md` — отмечены выполненные пункты Phase 1.

**Начало diff (фрагмент):**

```diff
diff --git a/telegram_parser.py b/telegram_parser.py
--- a/telegram_parser.py
+++ b/telegram_parser.py
@@ -512,6 +512,7 @@ class TelegramParser:
         media_saved_count = 0
         media_skipped_size = 0
         media_dedup_hits = 0
+        media_errors_count = 0
         flood_wait_events = 0
         total_scanned = 0
@@ -633,11 +634,13 @@ class TelegramParser:
                                 except Exception:
                                     logs.error("file_reference_retry_failed", {"message_id": msg_id})
                                     downloaded_path_raw = None
+                                    media_errors_count += 1
                                     media_files.append(
                                         {"type": mtype, "path": None, "filename": None, "error": "file_reference_expired"}
                                     )
                             else:
                                 downloaded_path_raw = None
+                                media_errors_count += 1
                                 media_files.append(
                                     {"type": mtype, "path": None, "filename": None, "error": "file_reference_expired"}
                                 )
@@ -747,6 +750,7 @@ class TelegramParser:
             self._save_json(media_index_path, {"sha256_to_path": hash_index})
 
+        partial_failure = not dry_run and media_errors_count > 0
         summary = {
             ...
+            "media_errors_count": media_errors_count,
+            "partial_failure": partial_failure,
         }
         return {
             "summary": summary,
+            "partial_failure": partial_failure,
             ...
         }
diff --git a/telegram_parser_skill.py b/telegram_parser_skill.py
+from exit_codes import EXIT_FAILURE, EXIT_INTERRUPTED, EXIT_PARTIAL, EXIT_SUCCESS  # noqa: E402
 ...
-            return 0
+            if result.get("partial_failure"):
+                return EXIT_PARTIAL
+            return EXIT_SUCCESS
 ...
-        return 130
+        return EXIT_INTERRUPTED
-        return 1
+        return EXIT_FAILURE
```

**Полный diff:** [2026-02-21-phase1-exit-codes-partial-failure.diff](2026-02-21-phase1-exit-codes-partial-failure.diff)

---

**Новый файл `exit_codes.py` (для воспроизведения без отдельного diff):**

```python
"""Коды выхода процесса (Phase 1: единая матрица для CLI и оркестрации)."""

EXIT_SUCCESS = 0
"""Успешное выполнение команды."""

EXIT_FAILURE = 1
"""Фатальная ошибка: конфиг, авторизация, аргументы, необработанное исключение."""

EXIT_PARTIAL = 2
"""Частичный успех: команда завершилась, но были ошибки (например часть медиа не загружена)."""

EXIT_INTERRUPTED = 130
"""Прерывание пользователем (Ctrl+C)."""
```

---

**Дополнение (по ревью):** partial_failure расширен на случай retry_exhausted/timeout при загрузке медиа: при исчерпании повторов или таймауте загрузки исключения ловятся в цикле, медиа помечается как ошибка (`download_timeout` / `retry_exhausted`), увеличивается `media_errors_count`, парсинг продолжается и в итоге возвращается код 2. См. `telegram_parser.py` — обработчики `except asyncio.TimeoutError` и `except Exception` после блока `FileReferenceExpiredError`.
