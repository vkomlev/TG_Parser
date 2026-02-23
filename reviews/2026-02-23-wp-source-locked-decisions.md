# Ревью: зафиксированные решения WP Source до старта разработки

**Дата:** 2026-02-23  
**Контекст:** в документы wp-source-* внесены шесть решений: конфиг YAML + env, run_id один на запуск + site_id в записях, post_content = content.rendered в MVP / content.raw phase 2, min WP 6.0+, миграции в migrations/wp/, интеграция ContentItem не в MVP.

## Изменённые файлы

- `docs/wp-source-architecture.md` — конфиг, run_id/site_id, ContentItem (не в MVP), структура каталогов, CLI вариант A зафиксирован
- `docs/wp-source-api-mapping.md` — min WP 6.0+, post_content = content.rendered в MVP, content.raw phase 2
- `docs/wp-source-data-model-postgres.md` — путь миграций migrations/wp/
- `docs/wp-source-implementation-plan.md` — шаги 1–5 и Hardening обновлены под зафиксированные решения
- `docs/wp-source-test-plan.md` — критерии приёмки MVP уточнены (конфиг, run_id/site_id, ContentItem, миграции)
- `docs/wp-source-risks-and-open-questions.md` — раздел «Зафиксированные решения» (6 пунктов), открытые вопросы сокращены

## Фрагмент diff

```diff
--- a/docs/wp-source-architecture.md
+++ b/docs/wp-source-architecture.md
+**Зафиксированные решения (до старта разработки):**
+- **Конфиг:** YAML-файл `config/wp-sites.yml` ...
+- **run_id:** один на весь запуск sync; в каждой записи БД и в логах дополнительно указывается `site_id`.
+- **Интеграция с ContentItem (contracts.py):** в MVP не включать; только экспорт в БД и единый JSON output.
```

Полный diff: [2026-02-23-wp-source-locked-decisions.diff](2026-02-23-wp-source-locked-decisions.diff).
