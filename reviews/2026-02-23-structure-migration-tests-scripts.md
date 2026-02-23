# Ревью: структурная миграция tests/ и scripts/

**Дата:** 2026-02-23  

**Контекст:** Перенос смоук-тестов и PowerShell-скриптов из корня в `tests/` и `scripts/`; обновление путей, документации и алиасов.

**Изменённые/новые файлы:**
- Добавлены: `tests/smoke_phase1.py`, `tests/smoke_phase2.py`, `tests/smoke_phase3.py`, `tests/smoke_session_stability.py`
- Добавлены: `scripts/telegram_parse.ps1`, `scripts/telegram_channels.ps1`, `scripts/setup_aliases.ps1`
- Добавлен: `docs/tests.md` (команды запуска, схема `tests/out/`)
- Обновлены: `README.md`, `docs/setup.md`, `docs/cli.md`, `SKILL.md`
- Удалены из корня: `smoke_phase*.py`, `smoke_session_stability.py`, `telegram_parse.ps1`, `telegram_channels.ps1`, `setup_aliases.ps1`

**Схема output для smoke:** централизована в `tests/out/`: подкаталоги `smoke_phase1`, `smoke_phase2`, `smoke_phase3`; внутри них — артефакты тест-кейсов (t2, t3, …). Описано в `docs/tests.md`.

**Команды прогонов (из корня):**
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\telegram_channels.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\telegram_parse.ps1 --channel @channel --dry-run
.\.venv\Scripts\python.exe tests\smoke_phase1.py --unit-only
.\.venv\Scripts\python.exe tests\smoke_phase3.py
.\.venv\Scripts\python.exe tests\smoke_session_stability.py --no-integration
```

**Полный diff:** [2026-02-23-structure-migration-tests-scripts.diff](2026-02-23-structure-migration-tests-scripts.diff)
