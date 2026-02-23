# Документация TG_Parser

Оглавление вспомогательной и дополнительной документации проекта.

| Документ | Содержание |
|----------|------------|
| [setup.md](setup.md) | Первоначальная настройка: окружение, .env, первый вход, 2FA, алиасы |
| [auth-2fa-env-setup.md](auth-2fa-env-setup.md) | Подробная настройка авторизации и .env (включая 2FA) |
| [cli.md](cli.md) | CLI: команды channels, resolve, parse; опции и примеры запуска |
| [output-formats.md](output-formats.md) | Форматы выходных файлов: export.json, state.json, media-index.json, summary.json, структура каталога |
| [logging.md](logging.md) | Логирование: форматы логов, ротация, расположение (app.log, run.log, errors.log) |
| [functions.md](functions.md) | Описание основных функций и классов модулей парсера |
| [contracts-adapters.md](contracts-adapters.md) | Phase 3: контракт ContentItem, SourceAdapter, DestinationAdapter |
| **WordPress Source (проектирование)** | |
| [wp-source-architecture.md](wp-source-architecture.md) | Архитектура WP Source: встраивание в проект, поток данных, наблюдаемость |
| [wp-source-data-model-postgres.md](wp-source-data-model-postgres.md) | Модель данных и DDL PostgreSQL для WP (sites, sync_runs, authors, terms, content) |
| [wp-source-api-mapping.md](wp-source-api-mapping.md) | Маппинг WP REST API: posts, pages, terms, users, SEO |
| [wp-source-sync-strategy.md](wp-source-sync-strategy.md) | Стратегия синхронизации: full sync, retry, rate limit, идемпотентность |
| [wp-source-test-plan.md](wp-source-test-plan.md) | План тестирования и критерии приёмки MVP |
| [wp-source-implementation-plan.md](wp-source-implementation-plan.md) | План внедрения: MVP → hardening → scale |
| [wp-source-risks-and-open-questions.md](wp-source-risks-and-open-questions.md) | Риски, ограничения и открытые вопросы |
| [wp-source-setup.md](wp-source-setup.md) | Настройка WP sync: конфиг, env, миграции, запуск |
| **WordPress Source — Scale (Phase 2)** | |
| [wp-source-scale-contract.md](wp-source-scale-contract.md) | Контракт этапа Scale: совместимость, флаги, БД/JSON v2, коды ошибок, критерии приёмки |
| [wp-source-scale-tasks.md](wp-source-scale-tasks.md) | ТЗ-пакеты S1–S5: content.raw, incremental, Gutenberg, performance, OpenClaw |
| [AUDIT-ARCHITECTURE-SCALABILITY-2026-02-21.md](AUDIT-ARCHITECTURE-SCALABILITY-2026-02-21.md) | Аудит архитектуры: расширяемость, DRY, стратегия масштабирования |
| [AUDIT-IMPLEMENTATION-2026-02-21.md](AUDIT-IMPLEMENTATION-2026-02-21.md) | Аудит реализации TG_Parser и пошаговый план внедрения (Phase 1–4) |

Главная точка входа — [README.md](../README.md) в корне проекта.
