# Review: Phase 3 — edge-case «новых сообщений нет»

**Дата:** 2026-02-21  

**Контекст:** В `TelegramSourceAdapter.fetch_messages()` при `new_messages=[]` (пустой список) условие `if new_messages:` давало False и выполнялся откат к чтению всего export.json. Требовалось возвращать только новые сообщения и в случае «новых нет» — пустой список.

**Изменение:** `adapters.py` — условие заменено на `if new_messages is not None:`; при пустом списке возвращается `[]`, при `None` (нет ключа в результате) — прежний fallback на чтение export.json.

**Полный diff:** [2026-02-21-phase3-fetch-empty-new-messages.diff](2026-02-21-phase3-fetch-empty-new-messages.diff)
