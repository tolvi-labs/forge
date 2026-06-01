"""XDG path resolution and on-disk profile loading for Forge."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "forge"


def _home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home())))


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(_home() / ".config")
    return Path(base) / APP_NAME


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(_home() / ".local" / "share")
    return Path(base) / APP_NAME


def hardware_profile_path() -> Path:
    return config_dir() / "hardware-profile.json"


def active_profile_path() -> Path:
    return config_dir() / "active-profile"
