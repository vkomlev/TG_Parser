# Review: Phase 1 — доработка по ревью (retry_exhausted/timeout + артефакт)

**Дата:** 2026-02-21  

**Контекст:** Учёт замечаний по Phase 1: (1) расширить partial_failure на случай retry_exhausted и timeout при загрузке медиа (раздел 4.1.2 аудита); (2) сделать артефакт первого ревью самодостаточным (содержимое `exit_codes.py` в .md). Дополнительно обновлена документация по кодам ошибок в `media_files`.

**Изменённые файлы в этом раунде:**
- `telegram_parser.py` — после блока `except FileReferenceExpiredError` добавлены `except asyncio.TimeoutError` и `except Exception`: при исчерпании retry/таймауте загрузки медиа не падаем, увеличиваем `media_errors_count`, добавляем запись в `media_files` с `error: "download_timeout"` или `"retry_exhausted"`, парсинг продолжается → в итоге partial_failure и код 2.
- `docs/output-formats.md` — в описании поля `error` в `media_files` добавлены значения `"download_timeout"` и `"retry_exhausted"`; уточнён текст про продолжение парсинга и код выхода 2.
- `reviews/2026-02-21-phase1-exit-codes-partial-failure.md` — добавлено полное содержимое `exit_codes.py` для воспроизводимости; добавлен блок «Дополнение (по ревью)» про retry_exhausted/timeout.

**Начало diff (фрагмент — telegram_parser.py):**

```diff
diff --git a/telegram_parser.py b/telegram_parser.py
@@ -633,15 +634,32 @@ class TelegramParser:
                                 media_files.append(
                                     {"type": mtype, "path": None, "filename": None, "error": "file_reference_expired"}
                                 )
 
+                        except asyncio.TimeoutError:
+                            logs.error("media_download_failed", {"message_id": msg_id, "error": "download_timeout"})
+                            downloaded_path_raw = None
+                            media_errors_count += 1
+                            media_files.append(
+                                {"type": mtype, "path": None, "filename": None, "error": "download_timeout"}
+                            )
+                        except Exception:
+                            logs.error("media_download_failed", {"message_id": msg_id, "error": "retry_exhausted"})
+                            downloaded_path_raw = None
+                            media_errors_count += 1
+                            media_files.append(
+                                {"type": mtype, "path": None, "filename": None, "error": "retry_exhausted"}
+                            )
+
                         if downloaded_path_raw:
```

**Полный diff** (все незакоммиченные изменения на момент сохранения, включая первоначальный Phase 1): [2026-02-21-phase1-partial-retry-timeout-and-docs.diff](2026-02-21-phase1-partial-retry-timeout-and-docs.diff)
