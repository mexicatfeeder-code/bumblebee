import json
import os
import threading
from pathlib import Path

_config = None
_config_path: str | None = None
_lock = threading.Lock()


def _resolve_config_path() -> str:
    """Resolve the dashboard config file path."""
    config_path = os.environ.get("DASHBOARD_CONFIG", "dashboard.config.json")
    dashboard_root = Path(__file__).resolve().parent.parent.parent  # dashboard/
    # Resolve relative paths from the dashboard root
    if not os.path.isabs(config_path):
        config_path = str(dashboard_root / config_path)
    # Fall back to example config if the specified one doesn't exist
    if not os.path.exists(config_path):
        example = str(dashboard_root / "dashboard.config.example.json")
        if os.path.exists(example):
            config_path = example
    return config_path


def load_config() -> dict:
    global _config, _config_path
    with _lock:
        if _config is not None:
            return _config
        _config_path = _resolve_config_path()
        with open(_config_path, encoding="utf-8-sig") as f:
            _config = json.load(f)
        return _config


def get_config() -> dict:
    return load_config()


def save_config(config: dict) -> None:
    """Persist config changes to disk. Thread-safe."""
    global _config, _config_path
    with _lock:
        if _config_path is None:
            _config_path = _resolve_config_path()
        # If we resolved to the example config, create a real config file instead
        if _config_path.endswith("example.json"):
            _config_path = _config_path.replace(".example.json", ".json")
        tmp = Path(_config_path).with_suffix(".tmp")
        tmp.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        tmp.replace(_config_path)
        _config = config
