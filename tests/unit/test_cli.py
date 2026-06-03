import json
import json as _json
import subprocess as _sub
from pathlib import Path
from click.testing import CliRunner
import forge.embedder.embedder as emb
import forge.llm as llm_mod
from forge.cli import main, _dedup_hits, _trim_history


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


def test_index_command_indexes_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(emb, "embed", lambda texts, **k: [[0.0, 1.0] for _ in texts])
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "a.py").write_text("def foo():\n    return 1\n")

    result = CliRunner().invoke(main, ["index", str(proj)])
    assert result.exit_code == 0, result.output
    assert "indexed" in result.output.lower()
    assert "1" in result.output


def test_search_prints_hits(tmp_path, monkeypatch):
    monkeypatch.setattr(emb, "embed", lambda texts, **k: [[0.0, 1.0] for _ in texts])
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "auth.py").write_text("def sign_in():\n    return 1\n")
    CliRunner().invoke(main, ["index", str(proj)])

    result = CliRunner().invoke(main, ["search", "sign_in", "--path", str(proj)])
    assert result.exit_code == 0, result.output
    assert "sign_in" in result.output


def test_chat_single_shot(tmp_path, monkeypatch):
    monkeypatch.setattr(emb, "embed", lambda texts, **k: [[0.0, 1.0] for _ in texts])
    monkeypatch.setattr(llm_mod, "generate",
                        lambda prompt, **k: f"ANSWER(saw {len(prompt)} chars)")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "auth.py").write_text("def sign_in():\n    return 1\n")
    (proj / "README.md").write_text("# Demo project\n")
    CliRunner().invoke(main, ["index", str(proj)])

    result = CliRunner().invoke(
        main, ["chat", "--path", str(proj), "--message", "how does sign_in work?"])
    assert result.exit_code == 0, result.output
    assert "ANSWER(saw" in result.output


def test_dedup_hits_drops_cag_paths():
    hits = [{"file_path": "/r/README.md", "content": "x"},
            {"file_path": "/r/src/a.py", "content": "y"}]
    out = _dedup_hits(hits, {"/r/README.md"})
    assert [h["file_path"] for h in out] == ["/r/src/a.py"]


def test_trim_history_keeps_recent_under_budget():
    turns = "".join(f"\nUser: q{i}\nForge: {'word ' * 50}\n" for i in range(40))
    trimmed = _trim_history(turns, max_tokens=200)
    from forge.chunker.chunk import count_tokens
    assert count_tokens(trimmed) <= 200
    assert "q39" in trimmed          # most recent turn retained
    assert "q0" not in trimmed       # oldest turns dropped


def test_trim_history_noop_when_small():
    h = "\nUser: hi\nForge: hello\n"
    assert _trim_history(h, max_tokens=8000) == h


def _init_repo(path):
    _sub.run(["git", "-C", str(path), "init", "-q"], check=True)
    _sub.run(["git", "-C", str(path), "config", "user.email", "t@e.com"], check=True)
    _sub.run(["git", "-C", str(path), "config", "user.name", "t"], check=True)
    (path / "seed.txt").write_text("s\n")
    _sub.run(["git", "-C", str(path), "add", "-A"], check=True)
    _sub.run(["git", "-C", str(path), "commit", "-q", "-m", "seed"], check=True)


def _tasks_file(path):
    data = {"feature": "Demo", "tasks": [
        {"id": "task-001", "title": "do first", "acceptance_criteria": ["x"]},
        {"id": "task-002", "title": "do second", "dependencies": ["task-001"],
         "acceptance_criteria": ["y"]},
    ]}
    f = path / "tasks.json"
    f.write_text(_json.dumps(data))
    return f


def test_plan_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    repo = tmp_path / "proj"
    repo.mkdir()
    _init_repo(repo)
    tasks = _tasks_file(repo)
    r = CliRunner()

    out = r.invoke(main, ["plan", "load", str(tasks), "--path", str(repo)])
    assert out.exit_code == 0, out.output
    assert "Demo" in out.output

    out = r.invoke(main, ["plan", "next", "--path", str(repo)])
    assert out.exit_code == 0
    assert "task-001" in out.output

    (repo / "feature.py").write_text("x = 1\n")
    out = r.invoke(main, ["plan", "complete", "task-001", "--path", str(repo)])
    assert out.exit_code == 0

    out = r.invoke(main, ["plan", "next", "--path", str(repo)])
    assert "task-002" in out.output

    out = r.invoke(main, ["plan", "status", "--path", str(repo)])
    assert "task-001" in out.output and "task-002" in out.output

    out = r.invoke(main, ["verify", "--path", str(repo)])
    assert out.exit_code == 0
    assert "feature.py" in out.output
