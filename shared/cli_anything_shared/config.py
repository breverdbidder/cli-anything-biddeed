"""Configuration management for CLI-Anything BidDeed tools.

Loads config from environment variables, config files, or CLI flags.
Priority: CLI flag > env var > config file > default.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

CONFIG_DIR = Path.home() / ".config" / "cli-anything"


def _config_path(cli_name: str) -> Path:
    return CONFIG_DIR / cli_name / "config.json"


def load_config(cli_name: str) -> dict:
    """Load full config dict for a CLI tool."""
    path = _config_path(cli_name)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_config(cli_name: str, key: str, value: Any) -> None:
    """Set a single config key for a CLI tool."""
    path = _config_path(cli_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    config = load_config(cli_name)
    config[key] = value
    path.write_text(json.dumps(config, indent=2))


def get_config(cli_name: str, key: str, env_var: Optional[str] = None, default: Any = None) -> Any:
    """Get a config value. Priority: env var > config file > default."""
    if env_var:
        val = os.environ.get(env_var)
        if val is not None:
            return val
    config = load_config(cli_name)
    return config.get(key, default)


def delete_config(cli_name: str, key: str) -> bool:
    """Remove a config key. Returns True if key existed."""
    path = _config_path(cli_name)
    config = load_config(cli_name)
    if key in config:
        del config[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2))
        return True
    return False
