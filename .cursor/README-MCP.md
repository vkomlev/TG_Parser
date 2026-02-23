# MCP PostgreSQL (БД Pipeline)

Чтобы подключаться к БД **Pipeline** из Cursor (запросы, схема, отладка):

1. Скопируйте пример конфига:
   ```powershell
   Copy-Item .cursor\mcp.json.example .cursor\mcp.json
   ```
2. Откройте `.cursor/mcp.json` и в строке подключения замените:
   - `USER` — пользователь PostgreSQL
   - `PASSWORD` — пароль
   - при необходимости `localhost:5432` на ваш хост и порт
   Имя БД в примере: **Pipeline**.
3. Полностью перезапустите Cursor (MCP подхватывается при старте).

Файл `.cursor/mcp.json` в .gitignore — в репозиторий не попадёт.

Подробнее: [docs/wp-source-setup.md](../docs/wp-source-setup.md#6-mcp-postgresql-доступ-к-бд-из-cursor).
