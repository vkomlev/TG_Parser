# Review: Phase 3 — контракты и адаптеры

**Дата:** 2026-02-21  

**Контекст:** Реализация раздела 4.3 аудита (AUDIT-IMPLEMENTATION): контракт данных ContentItem/MediaItem, маппинг TG ↔ контракт, протоколы SourceAdapter и DestinationAdapter, фасады TelegramSourceAdapter и LocalExportDestinationAdapter.

**Новые файлы:**
- **contracts.py** — ContentItem, MediaItem (dataclass); tg_message_to_content_item(msg, source_id), content_item_to_tg_message(item).
- **adapters.py** — SourceAdapter (Protocol, fetch_messages), TelegramSourceAdapter (фасад над TelegramParser); DestinationAdapter (Protocol, publish_batch), LocalExportDestinationAdapter (запись в export.json).

**Изменённые файлы:**
- **docs/contracts-adapters.md** — описание контрактов и адаптеров.
- **docs/README.md** — ссылка на contracts-adapters.md.

**Кратко:**
- Формат export.json не меняется; контракт используется для обмена между источниками и приёмниками.
- TelegramSourceAdapter вызывает parse_channel, читает export.json из результата и возвращает List[ContentItem].
- LocalExportDestinationAdapter принимает List[ContentItem] и дописывает их в export.json (append или с нуля), с опциональным channel_info. Медиа не скачивает.
- Заглушки VK/YouTube/Дзен/WP — в репозитории общего пайплайна.

**Полный diff:** [2026-02-21-phase3-contracts-adapters.diff](2026-02-21-phase3-contracts-adapters.diff)
