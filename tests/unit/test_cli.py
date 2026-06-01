import json
from pathlib import Path
from click.testing import CliRunner
from forge.cli import main


def _profile(tmp_path: Path) -> Path:
    cfg = tmp_path / "forge"
    cfg.mkdir(parents=True)
    (cfg / "hardware-profile.json").write_text(json.dumps({
        "arch": "arm64", "os": "Darwin", "ram_gb": 32, "gpu_type": "apple_silicon",
        "recommended_model": "qwen2.5-coder:14b", "stretch_model": "",
        "max_context_tokens": 65536, "embedding_model": "nomic-embed-text",
        "autocomplete_model": "qwen2.5-coder:7b",
    }))
    return tmp_path


def test_version_flag():
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_status_shows_model_and_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(_profile(tmp_path)))
    result = CliRunner().invoke(main, ["status"])
    assert result.exit_code == 0
    assert "qwen2.5-coder:14b" in result.output
    assert "65536" in result.output
    assert "react-node" in result.output


def test_status_without_profile_is_graceful(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    result = CliRunner().invoke(main, ["status"])
    assert result.exit_code == 0
    assert "not detected" in result.output.lower()


def test_doctor_runs_and_reports_checks(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    result = CliRunner().invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "Ollama" in result.output
    assert "Hardware profile" in result.output
    assert "Config directory" in result.output
    assert ("✅" in result.output) or ("❌" in result.output)
