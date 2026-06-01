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


DEFAULT_PROFILE = "react-node"


@dataclass(frozen=True)
class HardwareProfile:
    arch: str
    os: str
    ram_gb: int
    gpu_type: str
    recommended_model: str
    stretch_model: str
    max_context_tokens: int
    embedding_model: str
    autocomplete_model: str

    @classmethod
    def from_dict(cls, d: dict) -> "HardwareProfile":
        return cls(
            arch=d["arch"],
            os=d["os"],
            ram_gb=int(d["ram_gb"]),
            gpu_type=d["gpu_type"],
            recommended_model=d["recommended_model"],
            stretch_model=d.get("stretch_model", ""),
            max_context_tokens=int(d["max_context_tokens"]),
            embedding_model=d["embedding_model"],
            autocomplete_model=d["autocomplete_model"],
        )


def load_hardware_profile(path: Path | None = None) -> HardwareProfile:
    path = path or hardware_profile_path()
    if not path.exists():
        raise FileNotFoundError(
            f"No hardware profile at {path}. Run setup/detect-hardware.sh first."
        )
    return HardwareProfile.from_dict(json.loads(path.read_text()))


def load_active_profile(path: Path | None = None) -> str:
    path = path or active_profile_path()
    if not path.exists():
        return DEFAULT_PROFILE
    name = path.read_text().strip()
    return name or DEFAULT_PROFILE
