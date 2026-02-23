"""HTTP-клиент для WP REST API: Basic Auth, timeout, retries, rate limit."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests
from requests.auth import HTTPBasicAuth

from errors import WP_AUTH_ERROR, WP_DATA_FORMAT_ERROR, WP_NETWORK_ERROR, WP_RATE_LIMIT

logger = logging.getLogger("wp.client")

# Минимальная пауза между запросами (сек) для соблюдения 3 req/s
MIN_DELAY_BETWEEN_REQUESTS = 1.0 / 3.0


def _backoff_delay(attempt: int, retry_after_header: Optional[int] = None) -> float:
    """Задержка перед повтором: Retry-After или exponential backoff, кап 60 с."""
    if retry_after_header is not None and retry_after_header > 0:
        return min(float(retry_after_header), 60.0)
    return min(2.0 ** (attempt + 1), 60.0)


def _should_retry(status_code: Optional[int], error: Optional[Exception]) -> bool:
    """Повторять при: сетевые ошибки, таймаут, 5xx, 429. Не повторять при 400, 401, 403, 404."""
    if error is not None:
        return True
    if status_code is None:
        return True
    if status_code == 429:
        return True
    if 500 <= (status_code or 0) < 600:
        return True
    return False


class WPClientError(Exception):
    """Ошибка запроса к WP API с привязкой к error_code для логов."""

    def __init__(self, message: str, error_code: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


class WPRestClient:
    """Клиент к WordPress REST API с Basic Auth, лимитом запросов и retry."""

    def __init__(
        self,
        base_url: str,
        user: str,
        app_password: str,
        timeout_sec: int = 30,
        max_retries: int = 3,
        requests_per_second: float = 3.0,
        site_id: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(user, app_password)
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.site_id = site_id or ""
        self._min_delay = 1.0 / max(requests_per_second, 0.1)
        self._last_request_time: float = 0.0

    def _wait_rate_limit(self) -> None:
        """Соблюдение лимита запросов в секунду."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._min_delay:
            time.sleep(self._min_delay - elapsed)
        self._last_request_time = time.monotonic()

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        run_id: Optional[str] = None,
    ) -> Any:
        """Выполнить запрос с retry и rate limit. Возвращает JSON. При ошибке — WPClientError."""
        url = f"{self.base_url}/wp-json/wp/v2{path}"
        last_status: Optional[int] = None
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            self._wait_rate_limit()
            try:
                resp = requests.request(
                    method,
                    url,
                    params=params,
                    auth=self.auth,
                    timeout=self.timeout_sec,
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                )
                last_status = resp.status_code

                if resp.status_code == 401 or resp.status_code == 403:
                    logger.warning(
                        "WP API auth failed: %s %s status=%s",
                        method,
                        path,
                        resp.status_code,
                        extra={"site_id": self.site_id, "run_id": run_id, "error_code": WP_AUTH_ERROR},
                    )
                    raise WPClientError(
                        f"WP API auth failed: {resp.status_code}",
                        WP_AUTH_ERROR,
                        status_code=resp.status_code,
                    )
                if resp.status_code == 404:
                    raise WPClientError(
                        f"WP API not found: {url}",
                        WP_NETWORK_ERROR,
                        status_code=404,
                    )
                if resp.status_code == 429:
                    retry_after = None
                    if "Retry-After" in resp.headers:
                        try:
                            retry_after = int(resp.headers["Retry-After"])
                        except ValueError:
                            pass
                    delay = _backoff_delay(attempt, retry_after)
                    logger.warning(
                        "WP API rate limit (429), retry after %.1fs",
                        delay,
                        extra={"site_id": self.site_id, "run_id": run_id, "error_code": WP_RATE_LIMIT},
                    )
                    if attempt < self.max_retries:
                        time.sleep(delay)
                        continue
                    raise WPClientError(
                        "WP API rate limit (429) after retries",
                        WP_RATE_LIMIT,
                        status_code=429,
                    )
                if 500 <= resp.status_code < 600:
                    delay = _backoff_delay(attempt, None)
                    logger.warning(
                        "WP API server error %s, retry in %.1fs",
                        resp.status_code,
                        delay,
                        extra={"site_id": self.site_id, "run_id": run_id, "error_code": WP_NETWORK_ERROR},
                    )
                    if attempt < self.max_retries:
                        time.sleep(delay)
                        continue
                    raise WPClientError(
                        f"WP API server error: {resp.status_code}",
                        WP_NETWORK_ERROR,
                        status_code=resp.status_code,
                    )

                resp.raise_for_status()
                last_error = None
                try:
                    data = resp.json()
                except ValueError as e:
                    raise WPClientError(
                        f"Invalid JSON from WP API: {e}",
                        WP_DATA_FORMAT_ERROR,
                        status_code=resp.status_code,
                    ) from e
                return (data, resp)

            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(
                    "WP API timeout: %s %s",
                    method,
                    path,
                    extra={"site_id": self.site_id, "run_id": run_id, "error_code": WP_NETWORK_ERROR},
                )
                if attempt < self.max_retries:
                    time.sleep(_backoff_delay(attempt, None))
                    continue
                raise WPClientError(
                    f"WP API timeout: {e}",
                    WP_NETWORK_ERROR,
                ) from e
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.warning(
                    "WP API request error: %s",
                    e,
                    extra={"site_id": self.site_id, "run_id": run_id, "error_code": WP_NETWORK_ERROR},
                )
                if attempt < self.max_retries:
                    time.sleep(_backoff_delay(attempt, None))
                    continue
                raise WPClientError(
                    f"WP API request failed: {e}",
                    WP_NETWORK_ERROR,
                ) from e

        raise WPClientError(
            "WP API request failed after retries",
            WP_NETWORK_ERROR,
            status_code=last_status,
        )

    def get(self, path: str, params: Optional[dict] = None, run_id: Optional[str] = None) -> Any:
        data, _ = self._request("GET", path, params=params, run_id=run_id)
        return data

    def get_with_headers(
        self,
        path: str,
        params: Optional[dict] = None,
        run_id: Optional[str] = None,
    ) -> tuple[Any, dict]:
        """GET с возвратом заголовков для пагинации (X-WP-Total, X-WP-TotalPages)."""
        data, resp = self._request("GET", path, params=params, run_id=run_id)
        return data, dict(resp.headers)
