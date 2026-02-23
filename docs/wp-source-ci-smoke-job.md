# Инструкция: включение smoke_wp в CI

**Дата:** 2026-02-17  
**Контекст:** по ТЗ Hardening smoke_wp в CI сейчас не добавляется («нет в наличии»). Ниже — готовый шаблон job/инструкция для включения позже.

## Команды для CI

Рекомендуемый минимальный набор (без доступа к реальному WordPress и без PostgreSQL при использовании SQLite):

```yaml
# Пример для GitHub Actions
- name: WP unit / smoke (unit-only)
  run: python tests/smoke_wp.py --unit-only
  env:
    # Без WP_DATABASE_URL — тесты, не требующие БД, пройдут
    WP_STORAGE_BACKEND: sqlite
```

С полным контуром WP (если в CI есть секреты и БД):

```yaml
- name: WP storage (SQLite)
  run: |
    $env:WP_STORAGE_BACKEND = "sqlite"
    python tests/test_wp_storage.py
    python tests/test_wp_storage.py --integration
  shell: pwsh

- name: WP smoke (unit-only)
  run: python tests/smoke_wp.py --unit-only

# Опционально: sync к тестовому WP (нужны секреты)
# - name: WP sync smoke (real)
#   run: python wp_sync_skill.py sync --site <test_site_id>
#   env:
#     WP_SITE_<ID>_USER: ${{ secrets.WP_TEST_USER }}
#     WP_SITE_<ID>_APP_PASSWORD: ${{ secrets.WP_TEST_APP_PASSWORD }}
```

## Переменные окружения для job

| Переменная | Нужна для | Описание |
|------------|-----------|----------|
| `WP_STORAGE_BACKEND=sqlite` | Тесты storage без Postgres | Использовать SQLite |
| `WP_DATABASE_URL` | Реальный sync в Postgres | Строка подключения |
| `WP_SITE_<ID>_USER` / `WP_SITE_<ID>_APP_PASSWORD` | Реальный sync к WP | Креды тестового сайта |

## Ограничения

- **smoke_wp** с реальным WordPress и с реальным sync в CI не запускался при сдаче Hardening; для этого нужны тестовый сайт и секреты в CI.
- Локально все перечисленные команды должны проходить; при добавлении job в pipeline достаточно подставить свой shell (bash/pwsh) и секреты при необходимости.
