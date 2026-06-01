from pathlib import Path
from forge import config


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
