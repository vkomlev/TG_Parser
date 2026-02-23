# Смоук-тесты и структура tests/

## Расположение

- Тесты: `tests/smoke_phase1.py`, `tests/smoke_phase2.py`, `tests/smoke_phase3.py`, `tests/smoke_session_stability.py`.
- Артефакты (output) всех смоук-тестов централизованы в **`tests/out/`**:
  - `tests/out/smoke_phase1/` — Phase 1 (коды выхода, partial_failure);
  - `tests/out/smoke_phase2/` — Phase 2 (run_id, error_code);
  - `tests/out/smoke_phase3/` — Phase 3 (контракты, адаптеры);
  - подкаталоги тест-кейсов (t2, t3, …) создаются внутри этих директорий.

Запуск из **корня проекта** (с активированным `.venv` или с явным путём к python).

## Команды запуска

```powershell
.\.venv\Scripts\python.exe tests\smoke_phase1.py --unit-only
.\.venv\Scripts\python.exe tests\smoke_phase1.py

.\.venv\Scripts\python.exe tests\smoke_phase2.py --unit-only
.\.venv\Scripts\python.exe tests\smoke_phase2.py

.\.venv\Scripts\python.exe tests\smoke_phase3.py

.\.venv\Scripts\python.exe tests\smoke_session_stability.py --no-integration
.\.venv\Scripts\python.exe tests\smoke_session_stability.py
```

Тесты добавляют корень проекта в `sys.path`, поэтому импорты (`telegram_parser`, `contracts`, `adapters` и т.д.) работают при запуске из корня.

## См. также

- [CLI и формы запуска](cli.md)
- [Первоначальная настройка](setup.md)
