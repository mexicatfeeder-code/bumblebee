import json
import os
from pathlib import Path

_config = None


def load_config() -> dict:
    global _config
    if _config is not None:
        return _config
    config_path = os.environ.get("DASHBOARD_CONFIG", "dashboard.config.json")
    dashboard_root = Path(__file__).resolve().parent.parent.parent  # dashboard/
    api_root = Path(__file__).resolve().parent.parent  # dashboard/api/
    # Resolve relative paths from the dashboard root
    if not os.path.isabs(config_path):
        config_path = str(dashboard_root / config_path)
    # Fall back to example config if the specified one doesn't exist
    if not os.path.exists(config_path):
        example = str(dashboard_root / "dashboard.config.example.json")
        if os.path.exists(example):
            config_path = example
    with open(config_path) as f:
        _config = json.load(f)
    return _config


def get_config() -> dict:
    return load_config()
