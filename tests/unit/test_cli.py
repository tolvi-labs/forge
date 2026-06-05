import json
import subprocess as _sub
from pathlib import Path
from click.testing import CliRunner
import forge.embedder.embedder as emb
import forge.llm as llm_mod
from forge.cli import main, _dedup_hits, _trim_history
from forge import config as _config


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
    f.write_text(json.dumps(data))
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


def test_verify_out_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    repo = tmp_path / "proj"
    repo.mkdir()
    _init_repo(repo)
    tasks = _tasks_file(repo)
    r = CliRunner()
    r.invoke(main, ["plan", "load", str(tasks), "--path", str(repo)])
    (repo / "feature.py").write_text("x = 1\n")
    r.invoke(main, ["plan", "complete", "task-001", "--path", str(repo)])
    out_file = tmp_path / "bundle.md"
    res = r.invoke(main, ["verify", "--path", str(repo), "--out", str(out_file)])
    assert res.exit_code == 0, res.output
    assert out_file.exists()
    assert "feature.py" in out_file.read_text()


def test_profile_list_and_set(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    r = CliRunner()
    out = r.invoke(main, ["profile", "list"])
    assert out.exit_code == 0
    assert "react-node" in out.output and "fullstack-firebase" in out.output

    out = r.invoke(main, ["profile", "set", "nextjs"])
    assert out.exit_code == 0
    assert _config.load_active_profile() == "nextjs"

    out = r.invoke(main, ["profile", "set", "bogus"])
    assert out.exit_code != 0  # unknown profile rejected


def test_chat_uses_active_profile_static_files(tmp_path, monkeypatch):
    # python-backend profile pulls pyproject.toml into CAG; prove it reaches the prompt
    monkeypatch.setattr(emb, "embed", lambda texts, **k: [[0.0, 1.0] for _ in texts])
    captured = {}
    monkeypatch.setattr(llm_mod, "generate",
                        lambda prompt, **k: captured.setdefault("p", prompt) or "OK")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    (tmp_path / "cfg" / "forge").mkdir(parents=True)
    (tmp_path / "cfg" / "forge" / "active-profile").write_text("python-backend")
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "pyproject.toml").write_text("# MARKER-PYPROJECT\n")
    (proj / "a.py").write_text("def f():\n    return 1\n")
    CliRunner().invoke(main, ["index", str(proj)])
    CliRunner().invoke(main, ["chat", "--path", str(proj), "-m", "hi"])
    assert "MARKER-PYPROJECT" in captured["p"]


def test_agents_run_reports_per_task(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_mod, "generate",
                        lambda prompt, **k: "REVIEW: APPROVE" if "reviewer" in prompt.lower()
                        else "CODE: def f(): ...")
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps({"feature": "Demo", "tasks": [
        {"id": "t1", "title": "first", "acceptance_criteria": ["x"]},
    ]}))
    res = CliRunner().invoke(main, ["agents", "run", str(tasks)])
    assert res.exit_code == 0, res.output
    assert "t1" in res.output
    assert "APPROVE" in res.output


def test_chat_forwards_profile_rerank_and_max_context(tmp_path, monkeypatch):
    import forge.assembler as _asm
    import forge.retriever.retriever as _retr

    monkeypatch.setattr(emb, "embed", lambda texts, **k: [[0.0, 1.0] for _ in texts])
    monkeypatch.setattr(llm_mod, "generate", lambda prompt, **k: "OK")
    cap = {}
    monkeypatch.setattr(_retr, "retrieve",
                        lambda store, embed_fn, q, **k: cap.update(retrieve_kw=k) or [])
    monkeypatch.setattr(_asm, "assemble",
                        lambda q, **k: cap.update(assemble_kw=k) or "PROMPT")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "a.py").write_text("def f():\n    return 1\n")
    CliRunner().invoke(main, ["index", str(proj)])
    CliRunner().invoke(main, ["chat", "--path", str(proj), "-m", "hi"])
    # default profile (react-node): rerank True, top_k 6, max_context 65536 — all forwarded
    assert cap["retrieve_kw"]["rerank"] is True
    assert cap["retrieve_kw"]["top_k"] == 6
    assert cap["assemble_kw"]["max_context"] == 65536


def test_make_inference_logger_appends_json_lines(tmp_path):
    from forge.cli import _make_inference_logger
    log = tmp_path / "inference.log"
    logger = _make_inference_logger(log)
    stats = {"model": "forge-coder", "tokens_out": 100, "tokens_in": 50,
             "tokens_per_sec": 25.0, "duration_ms": 4000.0}
    logger(stats)
    logger(stats)
    lines = log.read_text().splitlines()
    assert len(lines) == 2
    entry = json.loads(lines[0])
    assert entry["model"] == "forge-coder"
    assert entry["tokens_out"] == 100
    assert "ts" in entry
    import datetime as _dt
    _dt.datetime.fromisoformat(entry["ts"])  # raises if not a valid ISO datetime


def test_write_context_stats_creates_json_with_correct_fields(tmp_path):
    from forge.cli import _write_context_stats
    path = tmp_path / "context" / "abc123.json"
    _write_context_stats(path, tokens_used=18000, tokens_budget=65536)
    data = json.loads(path.read_text())
    assert data["tokens_used"] == 18000
    assert data["tokens_budget"] == 65536
