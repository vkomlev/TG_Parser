#!/usr/bin/env python3
"""
Интеграционные тесты WP: HTTP-отказы 401, 429 (Retry-After), timeout против реального клиента и mock HTTP server.

Проверяет: error_code/status/exit-поведение на уровне запроса к серверу (не только unit-моки).
Запуск из корня проекта:
  python tests/test_wp_integration_http_failures.py
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from errors import WP_AUTH_ERROR, WP_NETWORK_ERROR, WP_RATE_LIMIT
from wp.client import WPClientError, WPRestClient


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --- 401: один раз 401 -> WPClientError, error_code WP_AUTH_ERROR ---
class Handler401(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"code":"rest_not_logged_in"}')

    def log_message(self, format, *args):
        pass


def test_401_auth_fail_error_code_and_status() -> bool:
    port = _free_port()
    server = HTTPServer(("127.0.0.1", port), Handler401)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = WPRestClient(
            base_url=f"http://127.0.0.1:{port}",
            user="u",
            app_password="p",
            timeout_sec=5,
            max_retries=1,
            requests_per_second=10.0,
            site_id="test",
        )
        try:
            client.get("/users", run_id="r1")
            assert False, "expected WPClientError"
        except WPClientError as e:
            assert e.error_code == WP_AUTH_ERROR
            assert e.status_code == 401
        return True
    finally:
        server.shutdown()


# --- 429: первый запрос 429 + Retry-After: 1, второй 200 -> успех после retry ---
class Handler429Then200(BaseHTTPRequestHandler):
    count = 0
    lock = threading.Lock()

    def do_GET(self):
        with Handler429Then200.lock:
            Handler429Then200.count += 1
            n = Handler429Then200.count
        if n <= 1:
            self.send_response(429)
            self.send_header("Retry-After", "1")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"code":"rate_limit"}')
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-WP-Total", "0")
            self.send_header("X-WP-TotalPages", "0")
            self.end_headers()
            self.wfile.write(json.dumps([]).encode())

    def log_message(self, format, *args):
        pass


def test_429_retry_then_success() -> bool:
    Handler429Then200.count = 0
    port = _free_port()
    server = HTTPServer(("127.0.0.1", port), Handler429Then200)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = WPRestClient(
            base_url=f"http://127.0.0.1:{port}",
            user="u",
            app_password="p",
            timeout_sec=5,
            max_retries=3,
            requests_per_second=10.0,
            site_id="test",
        )
        data = client.get("/users", run_id="r1")
        assert data == []
        return True
    finally:
        server.shutdown()


def test_429_all_retries_exhausted() -> bool:
    class Handler429Always(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(429)
            self.send_header("Retry-After", "0")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"code":"rate_limit"}')

        def log_message(self, format, *args):
            pass

    port = _free_port()
    server = HTTPServer(("127.0.0.1", port), Handler429Always)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = WPRestClient(
            base_url=f"http://127.0.0.1:{port}",
            user="u",
            app_password="p",
            timeout_sec=5,
            max_retries=1,
            requests_per_second=10.0,
            site_id="test",
        )
        try:
            client.get("/users", run_id="r1")
            assert False, "expected WPClientError"
        except WPClientError as e:
            assert e.error_code == WP_RATE_LIMIT
            assert e.status_code == 429
        return True
    finally:
        server.shutdown()


# --- Timeout: сервер "висит" дольше timeout клиента -> WPClientError WP_NETWORK_ERROR ---
class QuietHTTPServer(HTTPServer):
    """Подавляет вывод ConnectionAbortedError в stderr после client timeout."""

    def handle_error(self, request, client_address):
        pass


class HandlerTimeout(BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(3)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"[]")
        except (ConnectionAbortedError, BrokenPipeError, OSError):
            pass

    def log_message(self, format, *args):
        pass


def test_timeout_retry_then_final_status() -> bool:
    port = _free_port()
    server = QuietHTTPServer(("127.0.0.1", port), HandlerTimeout)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = WPRestClient(
            base_url=f"http://127.0.0.1:{port}",
            user="u",
            app_password="p",
            timeout_sec=1,
            max_retries=1,
            requests_per_second=10.0,
            site_id="test",
        )
        try:
            client.get("/users", run_id="r1")
            assert False, "expected WPClientError (timeout)"
        except WPClientError as e:
            assert e.error_code == WP_NETWORK_ERROR
        return True
    finally:
        server.shutdown()


def run_all() -> bool:
    cases = [
        ("401 -> error_code WP_AUTH_ERROR, status 401", test_401_auth_fail_error_code_and_status),
        ("429 retry then 200 -> success", test_429_retry_then_success),
        ("429 all retries -> WP_RATE_LIMIT", test_429_all_retries_exhausted),
        ("timeout -> WP_NETWORK_ERROR", test_timeout_retry_then_final_status),
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
    print("WP integration HTTP failures (401, 429, timeout)")
    sys.exit(0 if run_all() else 1)
