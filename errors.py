"""Таксономия кодов ошибок для логов и контрактов.

Используются в CLI и ядре: при обработке ошибок писать error_code в лог (поле error_code).
"""

CONFIG_ERROR = "CONFIG_ERROR"
AUTH_ERROR = "AUTH_ERROR"
RATE_LIMIT = "RATE_LIMIT"
NETWORK_ERROR = "NETWORK_ERROR"
DATA_FORMAT_ERROR = "DATA_FORMAT_ERROR"
EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"
PARTIAL_FAILURE = "PARTIAL_FAILURE"
SESSION_LOCKED = "SESSION_LOCKED"  # сессия занята другим процессом или database is locked после исчерпания retry

# WordPress Source (wp_sync_skill)
WP_AUTH_ERROR = "WP_AUTH_ERROR"  # 401/403 при обращении к WP REST API
WP_RATE_LIMIT = "WP_RATE_LIMIT"  # 429 или превышение лимита запросов
WP_NETWORK_ERROR = "WP_NETWORK_ERROR"  # таймаут, 5xx, соединение отклонено
WP_DATA_FORMAT_ERROR = "WP_DATA_FORMAT_ERROR"  # неожиданная структура ответа или невалидный JSON
