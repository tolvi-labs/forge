import json

import pytest
from click.testing import CliRunner

from forge import hardware
from forge.cli import main
from forge.config import HardwareProfile, load_hardware_profile


@pytest.mark.parametrize("ram_gb,model,stretch,context", [
    (8, "qwen2.5-coder:7b", "", 32768),
    (15, "qwen2.5-coder:7b", "", 32768),
    (16, "qwen2.5-coder:14b", "", 65536),
    (23, "qwen2.5-coder:14b", "", 65536),
    (24, "qwen3-coder:30b", "qwen3-coder-next", 65536),
    (47, "qwen3-coder:30b", "qwen3-coder-next", 65536),
    (48, "qwen3-coder-next", "", 131072),
    (128, "qwen3-coder-next", "", 131072),
])
def test_profile_for_picks_the_ram_tier(ram_gb, model, stretch, context):
    p = hardware.profile_for(arch="arm64", os_name="Darwin", ram_gb=ram_gb, gpu_type="apple_silicon")
    assert (p["recommended_model"], p["stretch_model"], p["max_context_tokens"]) == (model, stretch, context)


def test_profile_for_is_a_loadable_hardware_profile():
    p = hardware.profile_for(arch="x86_64", os_name="Linux", ram_gb=32, gpu_type="nvidia")
    assert p == {
        "arch": "x86_64", "os": "Linux", "ram_gb": 32, "gpu_type": "nvidia",
        "recommended_model": "qwen3-coder:30b", "stretch_model": "qwen3-coder-next",
        "max_context_tokens": 65536, "embedding_model": "nomic-embed-text",
        "autocomplete_model": "qwen2.5-coder:7b",
    }
    assert HardwareProfile.from_dict(p).ram_gb == 32


@pytest.mark.parametrize("arch,os_name,nvidia,expected", [
    ("arm64", "Darwin", False, "apple_silicon"),
    ("arm64", "Darwin", True, "apple_silicon"),
    ("x86_64", "Darwin", False, "cpu"),
    ("x86_64", "Linux", True, "nvidia"),
    ("x86_64", "Linux", False, "cpu"),
])
def test_gpu_type(arch, os_name, nvidia, expected, monkeypatch):
    monkeypatch.setattr(hardware.shutil, "which", lambda name: "/usr/bin/nvidia-smi" if nvidia else None)
    assert hardware.gpu_type(arch, os_name) == expected


def test_ram_gb_on_linux_floors_meminfo(tmp_path):
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:       32617072 kB\nMemFree: 1 kB\n")
    assert hardware.ram_gb("Linux", meminfo=meminfo) == 31


def test_ram_gb_on_darwin_floors_memsize(monkeypatch):
    monkeypatch.setattr(hardware.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": "34359738368\n"})())
    assert hardware.ram_gb("Darwin") == 32


@pytest.mark.parametrize("os_name", ["Linux", "Windows"])
def test_ram_gb_falls_back_to_8_with_a_warning(os_name, tmp_path, capsys):
    assert hardware.ram_gb(os_name, meminfo=tmp_path / "absent") == 8
    assert "8GB" in capsys.readouterr().err


def test_detect_hardware_writes_the_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(hardware, "detect", lambda: hardware.profile_for(
        arch="arm64", os_name="Darwin", ram_gb=32, gpu_type="apple_silicon"))
    result = CliRunner().invoke(main, ["detect-hardware"])
    assert result.exit_code == 0, result.output
    written = tmp_path / "forge" / "hardware-profile.json"
    assert json.loads(written.read_text())["recommended_model"] == "qwen3-coder:30b"
    assert load_hardware_profile(written).max_context_tokens == 65536
    assert "qwen3-coder:30b" in result.output and str(written) in result.output


def test_missing_profile_names_the_command_that_makes_one(tmp_path):
    with pytest.raises(FileNotFoundError, match="forge detect-hardware"):
        load_hardware_profile(tmp_path / "nope.json")
