# Ревью: setup_aliases replace + auth-2fa путь

**Дата:** 2026-02-23  

**Контекст:** Правки перед merge по замечаниям ревью:
- **P1** — `setup_aliases.ps1` при наличии в профиле блока «TG_Parser aliases» выполняет replace этого блока на новый (актуальные пути в `scripts/`), а не только «уже есть — ничего не делать».
- **P3** — в `docs/auth-2fa-env-setup.md` путь к скрипту алиасов заменён на `.\scripts\setup_aliases.ps1`.

**Изменённые файлы:**  
`scripts/setup_aliases.ps1`, `docs/auth-2fa-env-setup.md`

**Полный diff:** [2026-02-23-setup-aliases-replace-and-2fa-doc.diff](2026-02-23-setup-aliases-replace-and-2fa-doc.diff)
