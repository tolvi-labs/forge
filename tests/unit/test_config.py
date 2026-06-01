import json
from pathlib import Path

import pytest

from forge import config
from forge.config import HardwareProfile, load_active_profile, load_hardware_profile


def test_config_dir_respects_xdg(monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xdg-config")
    assert config.config_dir() == Path("/tmp/xdg-config/forge")


def test_config_dir_defaults_to_dot_config(monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", "/home/tester")
    assert config.config_dir() == Path("/home/tester/.config/forge")


def test_data_dir_respects_xdg(monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/xdg-data")
    assert config.data_dir() == Path("/tmp/xdg-data/forge")


def test_hardware_profile_path(monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/xdg-config")
    assert config.hardware_profile_path() == Path("/tmp/xdg-config/forge/hardware-profile.json")


def _write_profile(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "arch": "arm64", "os": "Darwin", "ram_gb": 32, "gpu_type": "apple_silicon",
        "recommended_model": "qwen2.5-coder:14b", "stretch_model": "qwen2.5-coder:32b-instruct-q4_K_M",
        "max_context_tokens": 65536, "embedding_model": "nomic-embed-text",
        "autocomplete_model": "qwen2.5-coder:7b",
    }))


def test_load_hardware_profile_parses_fields(tmp_path):
    p = tmp_path / "hardware-profile.json"
    _write_profile(p)
    hp = load_hardware_profile(p)
    assert isinstance(hp, HardwareProfile)
    assert hp.ram_gb == 32
    assert hp.recommended_model == "qwen2.5-coder:14b"
    assert hp.max_context_tokens == 65536


def test_load_hardware_profile_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_hardware_profile(tmp_path / "nope.json")


def test_load_active_profile_defaults_when_absent(tmp_path):
    assert load_active_profile(tmp_path / "active-profile") == "react-node"


def test_load_active_profile_reads_file(tmp_path):
    f = tmp_path / "active-profile"
    f.write_text("nextjs\n")
    assert load_active_profile(f) == "nextjs"
