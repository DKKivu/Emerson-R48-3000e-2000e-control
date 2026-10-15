"""User-level persistent settings (last-used port and last-used target address)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

USER_SETTINGS_FILE = Path.home() / ".r48_controller.yaml"


def load_user_settings() -> Dict[str, Any]:
    defaults = {"last_port": "", "last_target": None}
    if yaml is None:
        return defaults
    try:
        if USER_SETTINGS_FILE.exists():
            data = yaml.safe_load(USER_SETTINGS_FILE.read_text(encoding="utf8")) or {}
            if isinstance(data, dict):
                defaults.update(data)
    except Exception:
        # ignore errors and return defaults
        pass
    return defaults


def save_user_settings(settings: Dict[str, Any]) -> None:
    if yaml is None:
        return
    try:
        USER_SETTINGS_FILE.write_text(yaml.safe_dump(settings), encoding="utf8")
    except Exception:
        # best effort only
        pass