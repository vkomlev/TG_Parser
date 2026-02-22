# Ревью: стабилизация парсера — lock, retry, медиа-логи, адаптивный timeout

**Дата:** 2026-02-17  

**Контекст:** ТЗ в `docs/TZ-PARSER-STABILITY-LOCK-RETRY.md`. Внесены: межпроцессный lock на session_file, retry при `database is locked` в connect(), логирование старт/финиш загрузки медиа, адаптивный timeout по размеру файла, тесты в `smoke_session_stability.py`.

**Изменённые файлы:**  
`errors.py`, `telegram_parser.py`, `telegram_parser_skill.py`  
**Новые файлы:**  
`session_lock.py`, `smoke_session_stability.py`, `docs/TZ-PARSER-STABILITY-LOCK-RETRY.md` (обновлён блок «Реализация»).  
В этой же ревью усилено правило `.cursor/rules/review-changes.mdc`: явно указано, что сохранение в `reviews/` обязательно и напоминать пользователю не требуется.

**Фрагмент diff (начало):**

```diff
diff --git a/errors.py b/errors.py
--- a/errors.py
+++ b/errors.py
@@ -10,3 +10,5 @@ EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"
 PARTIAL_FAILURE = "PARTIAL_FAILURE"
+SESSION_LOCKED = "SESSION_LOCKED"
+
diff --git a/telegram_parser.py b/telegram_parser.py
--- a/telegram_parser.py
+++ b/telegram_parser.py
@@ -28,7 +30,7 @@ from telethon.tl.functions.messages import GetHistoryRequest
-from errors import EXTERNAL_API_ERROR, PARTIAL_FAILURE, RATE_LIMIT
+from errors import EXTERNAL_API_ERROR, PARTIAL_FAILURE, RATE_LIMIT, SESSION_LOCKED
...
+    def _is_database_locked_error(self, e: BaseException) -> bool:
+    async def connect(self) -> None:
+        ... max_connect_retries = 5 ...
```

**Полный diff:** [2026-02-17-parser-stability-lock-retry-media.diff](2026-02-17-parser-stability-lock-retry-media.diff)
