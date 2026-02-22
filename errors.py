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
