# Отчёт: Этап 2 — HTTP-клиент WP + rate limit

**Дата:** 2026-02-23  
**ТЗ:** Этап 2 — production-ready HTTP-клиент для WordPress REST API.

---

## 1. Что сделано по пунктам требований

### 1.1 WPRestClient

- **Auth:** Basic Auth (Application Password), без изменений.
- **Базовый URL:** `<base_url>/wp-json/wp/v2` + path (base_url без завершающего слэша).
- **Timeout по умолчанию:** 30 секунд (`timeout_sec=30`).
- **Публичные методы:**
  - `get(path, params=None, run_id=None)` — возвращает JSON.
  - `get_with_headers(path, params=None, run_id=None) -> (json, headers)` — для пагинации (X-WP-Total, X-WP-TotalPages).

### 1.2 Rate limit

- Не более 3 req/s на экземпляр: `_min_delay = 1 / max(requests_per_second, 0.1)`.
- Пауза `_wait_rate_limit()` вызывается в начале каждой итерации цикла retry, т.е. перед каждым HTTP-вызовом, включая повторы.

### 1.3 Retry policy

- `max_retries=3` (итого до 4 попыток).
- Backoff: `2^(attempt+1)` сек, cap 60 сек.
- Для 429: при валидном `Retry-After` (int > 0) используется он с cap 60, иначе обычный backoff.
- Retry: timeout, RequestException, 429, 5xx.
- Без retry: 401, 403, 400, 404 и прочие 4xx (кроме 429).

### 1.4 Ошибки и коды

- `WPClientError(message, error_code, status_code=None)`.
- `WP_AUTH_ERROR` — 401/403.
- `WP_RATE_LIMIT` — 429 после исчерпания retry.
- `WP_NETWORK_ERROR` — timeout, сеть, 5xx после retry.
- `WP_DATA_FORMAT_ERROR` — невалидный JSON в ответе.
- Любой другой 4xx (400, 404 и т.д.) — немедленный raise с `WP_NETWORK_ERROR`, без retry.

### 1.5 Логирование

- При каждой неудачной попытке: structured log с `run_id`, `site_id`, `error_code` (через `extra`).
- Для 429/5xx: в сообщении указана задержка до следующей попытки и номер попытки.
- Для auth (401/403): warning без retry.
- Секреты (user/password) в лог не попадают (логируем только method, path, status, delay, attempt).

---

## 2. Список файлов

| Файл | Изменение |
|------|-----------|
| `wp/client.py` | Рефакторинг: единая обработка 4xx (без retry), логи с задержкой и attempt, явный except WPClientError и повторный raise. |
| `tests/test_wp_client.py` | Новый файл: unit-тесты backoff, should_retry, rate limit, get_with_headers (мок). |
| `tests/smoke_wp.py` | В test_should_retry добавлена проверка 400 и 403. |
| `docs/wp-source-implementation-plan.md` | Подпункт «Этап 2 (HTTP-клиент production-ready)» с отсылкой к ТЗ и test_wp_client. |

---

## 3. Команды тестов и результат

```powershell
cd d:\Work\TG_Parser

# Тесты клиента Этапа 2
.\.venv\Scripts\python.exe tests\test_wp_client.py
```
**Результат:** 8/8 OK (backoff no Retry-After, backoff with Retry-After, backoff cap 60, should_retry retry cases, should_retry no retry cases, rate_limit min delay, rate_limit waits, get_with_headers returns tuple).

```powershell
.\.venv\Scripts\python.exe tests\smoke_wp.py --unit-only
```
**Результат:** Unit tests passed (все 11 тестов, включая backoff и should_retry с 400/403).

```powershell
.\.venv\Scripts\python.exe tests\smoke_phase1.py --unit-only
.\.venv\Scripts\python.exe tests\smoke_phase3.py
```
**Результат:** TG smoke без регрессии.

---

## 4. Примеры лог-записей

**429 retry (с задержкой до следующей попытки):**
```
WARNING [wp.client] WP API rate limit (429), retry after 5.0s (attempt 1) site_id=rodina run_id=a1b2c3d4 error_code=WP_RATE_LIMIT
```

**Timeout retry:**
```
WARNING [wp.client] WP API timeout: GET /posts, retry in 2.0s (attempt 1) site_id=rodina run_id=a1b2c3d4 error_code=WP_NETWORK_ERROR
```

**Auth fail (без retry):**
```
WARNING [wp.client] WP API auth failed: GET /users status=401 site_id=rodina run_id=a1b2c3d4 error_code=WP_AUTH_ERROR
```

---

## 5. Совместимость

- Sync/fetcher/storage не менялись; вызовы `client.get_with_headers(...)` и `client.get(...)` сохраняют контракт.
- Зависимости: только `requests` (без новых пакетов).
- Регрессии: `smoke_wp --unit-only`, `smoke_phase1 --unit-only`, `smoke_phase3` проходят.

Полный diff: [2026-02-23-wp-client-stage2.diff](2026-02-23-wp-client-stage2.diff).
