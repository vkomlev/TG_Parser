# Review: Phase 3 — findings (нечисловые id, только новые сообщения)

**Дата:** 2026-02-21  

**Контекст:** Учёт findings по Phase 3: (1) LocalExportDestinationAdapter не ломался на нечисловых `external_id`; (2) TelegramSourceAdapter возвращает только сообщения текущего fetch, а не весь export.json.

**Изменения:**

- **adapters.py**
  - **Сортировка в publish_batch:** вместо `int(m.get("id", 0))` введена `_msg_sort_key(m)`: числовые id сортируются по значению, нечисловые (строка) — по строке, без ValueError. Контракт допускает любые источники с произвольным external_id.
  - **fetch_messages:** при наличии в результате парсера списка `new_messages` используются только они для маппинга в ContentItem; иначе — прежнее поведение (чтение всего export.json) для обратной совместимости.

- **telegram_parser.py**
  - В возвращаемый словарь parse_channel добавлено поле **"new_messages"**: список словарей сообщений, добавленных в этом прогоне (те же объекты, что пишутся в export).

**Итог:** расширяемость по нечисловым id обеспечена; дубликаты/непредсказуемость при повторных прогонах сняты за счёт возврата только новых сообщений.

**Полный diff:** [2026-02-21-phase3-findings-ids-and-new-messages.diff](2026-02-21-phase3-findings-ids-and-new-messages.diff)
