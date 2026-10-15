"""Application configuration loader (from YAML).

If r48/config.yaml exists it will be loaded and override defaults.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


@dataclass(frozen=True)
class AppConfig:
    title: str = "Emerson / Vertiv R48 Controller"
    width: int = 1120
    height: int = 940

    # Serial / adapter defaults - leave empty to prefer auto/first-detected port
    serial_port: str = ""
    serial_baud: int = 2_000_000
    can_bitrate: int = 125_000

    poll_interval_ms: int = 1000
    keepalive_ms: int = 10_000
    age_refresh_ms: int = 500
    stale_after_s: float = 5.0
    gui_interval_ms: int = 50
    max_events_per_cycle: int = 200
    max_log_lines: int = 1200
    scan_spacing_ms: int = 90


def _load_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf8")) or {}
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def load_config() -> AppConfig:
    defaults_inst = AppConfig()
    defaults = {f.name: getattr(defaults_inst, f.name) for f in fields(AppConfig)}
    cfg_path = Path(__file__).parent / "config.yaml"
    if cfg_path.exists():
        data = _load_yaml(cfg_path)
        for k, v in list(data.items()):
            if k in defaults:
                defaults[k] = v
    return AppConfig(**defaults)


# module-level config instance for convenience
CONFIG = load_config()