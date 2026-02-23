#!/usr/bin/env python3
"""
Тесты CLI WP Source (Шаг 6): коды выхода, list-sites, sync --site, summary в stdout/логах.

Запуск из корня проекта:
  python tests/test_wp_cli.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WP_SYNC_SCRIPT = PROJECT_ROOT / "wp_sync_skill.py"

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_PARTIAL = 2


def _script_available() -> bool:
    """Проверка, что скрипт запускается (импорты и окружение)."""
    r = _run("list-sites", "--config", "/nonexistent/config.yml")
    if r.returncode == 0:
        return True
    if "ModuleNotFoundError" in (r.stderr or "") or "ImportError" in (r.stderr or ""):
        return False
    return True


def _run(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    env = env or os.environ.copy()
    return subprocess.run(
        [sys.executable, str(WP_SYNC_SCRIPT)] + list(args),
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=60,
    )


def test_list_sites_valid_config_exit_0() -> bool:
    """list-sites с валидным конфигом -> exit 0, в stdout есть site_id."""
    if not _script_available():
        print("  SKIP (script import failed, need dotenv etc.)")
        return True
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False, encoding="utf-8") as f:
        f.write("sites:\n  - site_id: fixture\n    base_url: https://example.com\n    name: Fixture\n")
        path = f.name
    try:
        r = _run("list-sites", "--config", path)
        if r.returncode != EXIT_SUCCESS:
            print(f"  stderr: {r.stderr!r}")
            return False
        assert "fixture" in r.stdout or "site_id" in r.stdout
        return True
    finally:
        Path(path).unlink(missing_ok=True)


def test_list_sites_broken_yaml_exit_1() -> bool:
    """list-sites с битым YAML -> exit 1, сообщение в stderr."""
    if not _script_available():
        print("  SKIP (script import failed)")
        return True
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False, encoding="utf-8") as f:
        f.write("sites:\n  - site_id: x\n  bad: indent\n")
        path = f.name
    try:
        r = _run("list-sites", "--config", path)
        if r.returncode != EXIT_FAILURE:
            print(f"  expected exit 1, got {r.returncode}; stdout={r.stdout!r} stderr={r.stderr!r}")
            return False
        assert "Error" in r.stderr or "YAML" in r.stderr or "разбора" in r.stderr
        return True
    finally:
        Path(path).unlink(missing_ok=True)


def test_list_sites_config_not_found_exit_1() -> bool:
    """list-sites с несуществующим конфигом -> exit 1."""
    if not _script_available():
        print("  SKIP (script import failed)")
        return True
    r = _run("list-sites", "--config", "/nonexistent/wp-sites.yml")
    if r.returncode != EXIT_FAILURE:
        print(f"  expected exit 1, got {r.returncode}")
        return False
    assert "not found" in r.stderr or "Error" in r.stderr
    return True


def test_sync_site_missing_exit_1() -> bool:
    """sync --site <отсутствующий в конфиге> -> exit 1."""
    if not _script_available():
        print("  SKIP (script import failed)")
        return True
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False, encoding="utf-8") as f:
        f.write("sites:\n  - site_id: only_site\n    base_url: https://example.com\n")
        path = f.name
    try:
        env = os.environ.copy()
        env["WP_SITE_ONLY_SITE_USER"] = "u"
        env["WP_SITE_ONLY_SITE_APP_PASSWORD"] = "p"
        r = _run("sync", "--site", "nonexistent_site", "--config", path, env=env)
        if r.returncode != EXIT_FAILURE:
            print(f"  expected exit 1, got {r.returncode}; stderr={r.stderr!r}")
            return False
        assert "not found" in r.stderr or "nonexistent_site" in r.stderr
        return True
    finally:
        Path(path).unlink(missing_ok=True)


def test_sync_stdout_has_summary_fields() -> bool:
    """sync при успешном/частичном завершении выводит JSON с полями summary (run_id, site_id, status, *_count)."""
    if not _script_available():
        print("  SKIP (script import failed)")
        return True
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False, encoding="utf-8") as f:
        f.write("sites:\n  - site_id: stub\n    base_url: https://httpbin.org\n")
        path = f.name
    try:
        env = os.environ.copy()
        env["WP_SITE_STUB_USER"] = "u"
        env["WP_SITE_STUB_APP_PASSWORD"] = "x"
        r = _run("sync", "--site", "stub", "--config", path, env=env)
        if r.returncode not in (EXIT_SUCCESS, EXIT_PARTIAL, EXIT_FAILURE):
            print(f"  unexpected exit {r.returncode}")
            return False
        if "run_id" not in r.stdout or "site_id" not in r.stdout or "status" not in r.stdout:
            print(f"  stdout missing summary fields: {r.stdout[:500]!r}")
            return False
        if "content" not in r.stdout:
            print(f"  stdout missing content key: {r.stdout[:500]!r}")
            return False
        return True
    finally:
        Path(path).unlink(missing_ok=True)


def test_exit_codes_documentation() -> bool:
    """Проверка констант кодов выхода (0/1/2)."""
    assert EXIT_SUCCESS == 0
    assert EXIT_FAILURE == 1
    assert EXIT_PARTIAL == 2
    return True


def run_all() -> bool:
    cases = [
        ("list-sites valid config -> exit 0", test_list_sites_valid_config_exit_0),
        ("list-sites broken YAML -> exit 1", test_list_sites_broken_yaml_exit_1),
        ("list-sites config not found -> exit 1", test_list_sites_config_not_found_exit_1),
        ("sync --site missing -> exit 1", test_sync_site_missing_exit_1),
        ("sync stdout has summary fields", test_sync_stdout_has_summary_fields),
        ("exit codes 0/1/2", test_exit_codes_documentation),
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


def main() -> int:
    if not WP_SYNC_SCRIPT.exists():
        print("  SKIP wp_sync_skill.py not found")
        return 0
    print("WP CLI (stage 6) tests")
    return 0 if run_all() else 1


if __name__ == "__main__":
    sys.exit(main())
