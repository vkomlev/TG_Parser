"""Чтение конфигурации WP sync: config/wp-sites.yml + секреты из env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

import yaml



@dataclass
class SiteConfig:
    site_id: str
    base_url: str
    name: Optional[str]
    user: str  # из env WP_SITE_<site_id>_USER
    app_password: str  # из env WP_SITE_<site_id>_APP_PASSWORD


@dataclass
class WPSyncConfig:
    """Параметры sync из конфига и дефолтов."""
    sites: List[SiteConfig]
    per_page: int = 100
    timeout_sec: int = 30
    retries: int = 3
    requests_per_second: float = 3.0  # пауза между запросами = 1/requests_per_second


def _env_key(site_id: str, suffix: str) -> str:
    safe_id = site_id.upper().replace("-", "_")
    return f"WP_SITE_{safe_id}_{suffix}"


def _get_site_credentials(site_id: str) -> tuple[str, str]:
    user = os.environ.get(_env_key(site_id, "USER"), "").strip()
    pwd = os.environ.get(_env_key(site_id, "APP_PASSWORD"), "").strip()
    return user, pwd


def load_sites_yaml(path: Path) -> List[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(
            f"Ошибка разбора YAML в {path}: {e}. Проверьте синтаксис (отступы, кавычки)."
        ) from e
    if not data or not isinstance(data, dict):
        return []
    sites = data.get("sites")
    if not isinstance(sites, list):
        return []
    return sites


def load_sites_list(config_path: Path) -> List[dict]:
    """Загрузить только список сайтов из YAML (без секретов). Для list-sites."""
    raw_sites = load_sites_yaml(config_path)
    return [s for s in raw_sites if isinstance(s, dict) and (s.get("site_id") or "").strip()]


def load_config(
    config_path: Optional[Path] = None,
    project_root: Optional[Path] = None,
) -> WPSyncConfig:
    """Загрузить конфиг и секреты. При отсутствии обязательных полей — ValueError с CONFIG_ERROR."""
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    if config_path is None:
        config_path = project_root / "config" / "wp-sites.yml"

    raw_sites = load_sites_yaml(config_path)
    if not raw_sites:
        raise ValueError(
            f"Конфиг не найден или пуст: {config_path}. "
            "Должен быть YAML с ключом 'sites' и списком объектов site_id, base_url."
        ) from None

    site_configs: List[SiteConfig] = []
    for i, s in enumerate(raw_sites):
        if not isinstance(s, dict):
            raise ValueError(f"config/wp-sites.yml: sites[{i}] должен быть объектом") from None
        site_id = (s.get("site_id") or "").strip()
        base_url = (s.get("base_url") or "").strip().rstrip("/")
        name = (s.get("name") or "").strip() or None
        if not site_id:
            raise ValueError(f"config/wp-sites.yml: sites[{i}] должен содержать site_id") from None
        if not base_url:
            raise ValueError(
                f"config/wp-sites.yml: sites[{i}] (site_id={site_id}) должен содержать base_url"
            ) from None
        user, app_password = _get_site_credentials(site_id)
        if not user or not app_password:
            raise ValueError(
                f"Для сайта {site_id} задайте переменные окружения "
                f"{_env_key(site_id, 'USER')} и {_env_key(site_id, 'APP_PASSWORD')} (Application Password)."
            ) from None
        site_configs.append(
            SiteConfig(site_id=site_id, base_url=base_url, name=name, user=user, app_password=app_password)
        )

    # Опциональные глобальные параметры из YAML
    data: dict = {}
    try:
        if config_path.exists():
            with config_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(
            f"Ошибка разбора YAML в {config_path}: {e}. Проверьте синтаксис."
        ) from e
    per_page = int(data.get("per_page", 100))
    timeout_sec = int(data.get("timeout_sec", 30))
    retries = int(data.get("retries", 3))
    rps = float(data.get("requests_per_second", 3.0))
    if rps <= 0:
        rps = 3.0

    return WPSyncConfig(
        sites=site_configs,
        per_page=per_page,
        timeout_sec=timeout_sec,
        retries=retries,
        requests_per_second=rps,
    )
