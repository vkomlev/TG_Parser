#!/usr/bin/env python3
"""
Unit-тесты WP REST client (Этап 2): backoff, should_retry, rate limit.

Запуск из корня проекта:
  python tests/test_wp_client.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from wp.client import (
    MIN_DELAY_BETWEEN_REQUESTS,
    WPRestClient,
    _backoff_delay,
    _should_retry,
)


def test_backoff_delay_no_retry_after() -> bool:
    """Без Retry-After возвращается экспоненциальная задержка 2^(attempt+1), cap 60."""
    assert _backoff_delay(0, None) == 2.0   # 2^1
    assert _backoff_delay(1, None) == 4.0   # 2^2
    assert _backoff_delay(2, None) == 8.0   # 2^3
    assert _backoff_delay(3, None) == 16.0  # 2^4
    assert _backoff_delay(6, None) == 60.0  # cap
    return True


def test_backoff_delay_with_retry_after() -> bool:
    """С валидным Retry-After используется он (cap 60)."""
    assert _backoff_delay(0, 5) == 5.0
    assert _backoff_delay(1, 10) == 10.0
    assert _backoff_delay(0, 120) == 60.0  # cap
    assert _backoff_delay(0, 0) == 2.0     # 0 -> backoff
    return True


def test_backoff_delay_cap_60() -> bool:
    """Cap 60 соблюдается."""
    assert _backoff_delay(10, None) == 60.0
    assert _backoff_delay(0, 100) == 60.0
    return True


def test_should_retry_retry_cases() -> bool:
    """429, 5xx, network error => True."""
    assert _should_retry(429, None) is True
    assert _should_retry(500, None) is True
    assert _should_retry(502, None) is True
    assert _should_retry(599, None) is True
    assert _should_retry(None, Exception()) is True
    return True


def test_should_retry_no_retry_cases() -> bool:
    """401, 403, 404, 400 => False."""
    assert _should_retry(401, None) is False
    assert _should_retry(403, None) is False
    assert _should_retry(404, None) is False
    assert _should_retry(400, None) is False
    assert _should_retry(422, None) is False
    return True


def test_rate_limit_min_delay() -> bool:
    """Минимальная пауза >= 1/3 сек (допуск 0.01)."""
    assert MIN_DELAY_BETWEEN_REQUESTS >= (1.0 / 3.0) - 0.01
    client = WPRestClient(
        base_url="https://example.com",
        user="u",
        app_password="p",
        requests_per_second=3.0,
    )
    assert client._min_delay >= (1.0 / 3.0) - 0.01
    return True


def test_rate_limit_waits_before_request() -> bool:
    """_wait_rate_limit ждёт при повторном вызове (~1/3 сек)."""
    client = WPRestClient(
        base_url="https://example.com",
        user="u",
        app_password="p",
        requests_per_second=3.0,
    )
    client._last_request_time = 0.0
    t0 = time.monotonic()
    client._wait_rate_limit()
    client._wait_rate_limit()
    elapsed = time.monotonic() - t0
    assert elapsed >= (1.0 / 3.0) - 0.05, f"expected >= ~0.33s, got {elapsed}"
    return True


def test_client_get_with_headers_returns_tuple() -> bool:
    """get_with_headers возвращает (data, headers). Мок."""
    client = WPRestClient(
        base_url="https://example.com",
        user="u",
        app_password="p",
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"id": 1}]
    mock_resp.headers = {"X-WP-Total": "10", "X-WP-TotalPages": "1"}
    mock_resp.raise_for_status = MagicMock()

    with patch("wp.client.requests.request", return_value=mock_resp):
        data, headers = client.get_with_headers("/posts", run_id="test-run")
    assert data == [{"id": 1}]
    assert "X-WP-Total" in headers
    return True


def run_all() -> bool:
    cases = [
        ("backoff_delay no Retry-After", test_backoff_delay_no_retry_after),
        ("backoff_delay with Retry-After", test_backoff_delay_with_retry_after),
        ("backoff_delay cap 60", test_backoff_delay_cap_60),
        ("should_retry retry cases", test_should_retry_retry_cases),
        ("should_retry no retry cases", test_should_retry_no_retry_cases),
        ("rate_limit min delay", test_rate_limit_min_delay),
        ("rate_limit waits", test_rate_limit_waits_before_request),
        ("get_with_headers returns tuple", test_client_get_with_headers_returns_tuple),
    ]
    ok = 0
    for name, fn in cases:
        try:
            if fn():
                ok += 1
                print(f"  OK {name}")
            else:
                print(f"  FAIL {name}")
        except Exception as e:
            print(f"  FAIL {name}: {e}")
    return ok == len(cases)


if __name__ == "__main__":
    print("WP client (stage 2) unit tests")
    sys.exit(0 if run_all() else 1)
