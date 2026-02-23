# Ревью: архитектурный пакет WordPress Source

**Дата:** 2026-02-23  
**Контекст:** добавлены 7 документов проектирования WP Source и обновлён оглавление docs/README.md. Прод-код не менялся.

## Изменённые файлы

- `docs/wp-source-architecture.md` — новый
- `docs/wp-source-data-model-postgres.md` — новый
- `docs/wp-source-api-mapping.md` — новый
- `docs/wp-source-sync-strategy.md` — новый
- `docs/wp-source-test-plan.md` — новый
- `docs/wp-source-implementation-plan.md` — новый
- `docs/wp-source-risks-and-open-questions.md` — новый
- `docs/README.md` — добавлена секция «WordPress Source» в оглавление

## Фрагмент diff (начало)

```diff
diff --git a/docs/README.md b/docs/README.md
index 4ed7e8a..8d22054 100644
--- a/docs/README.md
+++ b/docs/README.md
@@ -11,6 +11,14 @@
 | [contracts-adapters.md](contracts-adapters.md) | Phase 3: контракт ContentItem, SourceAdapter, DestinationAdapter |
+| **WordPress Source (проектирование)** | |
+| [wp-source-architecture.md](wp-source-architecture.md) | Архитектура WP Source: встраивание в проект, поток данных, наблюдаемость |
...
```

Полный diff: [2026-02-23-wp-source-architecture-docs.diff](2026-02-23-wp-source-architecture-docs.diff).
