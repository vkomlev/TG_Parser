# Контракты и адаптеры (Phase 3)

Единый формат сообщений и протоколы источников/приёмников для расширяемости (несколько источников, несколько назначений).

## Контракт данных

**Модуль:** `contracts.py`

- **ContentItem** — нормализованное сообщение: `source_id`, `external_id`, `published_at`, `text`, `media[]`, `metadata`.
- **MediaItem** — элемент медиа: `type`, `path`, `filename`, `size`, `sha256`, `error`.
- **tg_message_to_content_item(msg, source_id)** — текущий словарь сообщения TG (из export.json) → ContentItem.
- **content_item_to_tg_message(item)** — ContentItem → словарь в формате export.json (для обратной записи).

Формат export.json не меняется; контракт используется для обмена между адаптерами.

## SourceAdapter

**Протокол** (в `adapters.py`): метод **fetch_messages(channel_identifier, output_dir, **kwargs)** → `List[ContentItem]`.

- **TelegramSourceAdapter** — фасад над `TelegramParser`: вызывает `parse_channel`, читает export.json из результата и возвращает список ContentItem. Инициализируется готовым экземпляром `TelegramParser`.

## DestinationAdapter

**Протокол**: метод **publish_batch(items, export_dir, **kwargs)** — записать пакет ContentItem в назначение.

- **LocalExportDestinationAdapter** — запись в export.json в каталоге экспорта (формат TG). Поддерживает append и опциональный `channel_info`. Медиа не скачивает; пути в ContentItem уже предполагаются сохранёнными.

Заглушки для VK/YouTube/Дзен/WP добавляются в репозитории общего пайплайна, не в TG_Parser.
