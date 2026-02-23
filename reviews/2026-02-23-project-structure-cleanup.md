# Ревью: упорядочивание структуры проекта

**Дата:** 2026-02-23  
**Контекст:** Анализ корня проекта, временных папок и файлов; предложения по подпапкам, удалению и сохранению артефактов.

## Изменения

- **.gitignore** — добавлены артефакты выходов и смоук-тестов: `out/`, `out_init/`, `out_smoke_phase1/`, `out_smoke_phase2/`, `out_smoke_phase3/`, `videos.db`.
- **AUTH_2FA_ENV_SETUP.md** — перенесён в `docs/auth-2fa-env-setup.md`, ссылка в `docs/setup.md` обновлена.
- **docs/PROJECT-STRUCTURE-CLEANUP-2026-02-23.md** — добавлен отчёт с рекомендациями (что в подпапки, что удалять, что сохранить).

## Фрагмент diff

```diff
--- a/.gitignore
+++ b/.gitignore
+# --- Output / smoke test artifacts (do not commit) ---
+out/
+out_init/
+out_smoke_phase1/
+out_smoke_phase2/
+out_smoke_phase3/
+videos.db
```

Полный diff: [2026-02-23-project-structure-cleanup.diff](2026-02-23-project-structure-cleanup.diff).
