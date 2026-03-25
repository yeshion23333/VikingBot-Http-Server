import json
import os
from typing import Dict, Any

_config = None

def load_config() -> Dict[str, Any]:
    global _config
    if _config is not None:
        return _config

    # Get config file path from environment variable or use default
    config_path = os.environ.get("CONFIG_PATH", "config.json")

    # Try to load from current directory, then from parent directory
    possible_paths = [
        config_path,
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), config_path),
        os.path.join("/", config_path)
    ]

    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    _config = json.load(f)
                    return _config
            except Exception as e:
                raise RuntimeError(f"Failed to load config file {path}: {str(e)}")

    raise RuntimeError(f"Config file not found in any of the paths: {possible_paths}")

def get_config(key: str, default: Any = None) -> Any:
    """
    Get config value by key, supports nested keys with dot notation
    Example: get_config("openviking.base_url")
    """
    config = load_config()
    keys = key.split(".")
    value = config

    try:
        for k in keys:
            value = value[k]
        return value
    except KeyError:
        if default is not None:
            return default
        raise KeyError(f"Config key '{key}' not found")
