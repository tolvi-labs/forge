import signal
import subprocess

import httpx

from forge import config, runtime


def _hp(**overrides) -> config.HardwareProfile:
    base = dict(
        arch="arm64", os="Darwin", ram_gb=32, gpu_type="apple_silicon",
        recommended_model="qwen2.5-coder:14b", stretch_model="",
        max_context_tokens=65536, embedding_model="nomic-embed-text",
        autocomplete_model="qwen2.5-coder:7b",
    )
    base.update(overrides)
    return config.HardwareProfile(**base)


def _tags_response(names):
    return httpx.Response(200, json={"models": [{"name": n} for n in names]})


# ---- required_models ----

def test_required_models_dedup_preserves_order_and_drops_empty():
    hp = _hp(recommended_model="a", autocomplete_model="a", embedding_model="b")
    assert runtime.required_models(hp) == ["a", "b"]


def test_required_models_drops_empty_strings():
    hp = _hp(recommended_model="a", autocomplete_model="", embedding_model="b")
    assert runtime.required_models(hp) == ["a", "b"]


# ---- ollama_reachable / installed_models ----

def test_ollama_reachable_true_on_200(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, timeout: _tags_response([]))
    assert runtime.ollama_reachable() is True


def test_ollama_reachable_false_on_connect_error(monkeypatch):
    def boom(url, timeout):
        raise httpx.ConnectError("nope")
    monkeypatch.setattr(httpx, "get", boom)
    assert runtime.ollama_reachable() is False


def test_installed_models_matches_with_or_without_latest_tag(monkeypatch):
    monkeypatch.setattr(httpx, "get",
                        lambda url, timeout: _tags_response(["nomic-embed-text:latest", "forge-coder"]))
    models = runtime.installed_models()
    assert "nomic-embed-text:latest" in models
    assert "nomic-embed-text" in models
    assert "forge-coder" in models


# ---- ensure_ollama ----

def test_ensure_ollama_noop_when_reachable(monkeypatch):
    monkeypatch.setattr(runtime, "ollama_reachable", lambda *a, **k: True)
    spawned = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: spawned.append(a))
    events = []
    runtime.ensure_ollama(on_event=events.append)
    assert spawned == []
    assert any("already running" in e.lower() for e in events)


def test_ensure_ollama_spawns_and_writes_pidfile(monkeypatch, tmp_path):
    states = iter([False, True])  # down on first check, up after spawn
    monkeypatch.setattr(runtime, "ollama_reachable", lambda *a, **k: next(states))
    monkeypatch.setattr(runtime.shutil, "which", lambda _: "/usr/bin/ollama")

    class FakeProc:
        pid = 4823
    captured = {}
    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeProc()
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    pidfile = tmp_path / "ollama.pid"
    monkeypatch.setattr(runtime, "pidfile_path", lambda: pidfile)

    runtime.ensure_ollama(on_event=lambda _m: None)
    assert captured["args"] == ["ollama", "serve"]
    assert captured["kwargs"].get("start_new_session") is True
    assert pidfile.read_text().strip() == "4823"


def test_ensure_ollama_raises_when_binary_missing(monkeypatch):
    monkeypatch.setattr(runtime, "ollama_reachable", lambda *a, **k: False)
    monkeypatch.setattr(runtime.shutil, "which", lambda _: None)
    try:
        runtime.ensure_ollama(on_event=lambda _m: None)
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "not installed" in str(e).lower()


# ---- ensure_models ----

def test_ensure_models_pulls_only_missing(monkeypatch):
    monkeypatch.setattr(runtime, "installed_models",
                        lambda *a, **k: {"qwen2.5-coder:14b", "qwen2.5-coder:7b"})
    pulled = []
    def fake_run(args, **kwargs):
        pulled.append(args)
        return subprocess.CompletedProcess(args, 0)
    monkeypatch.setattr(subprocess, "run", fake_run)
    runtime.ensure_models(_hp(), on_event=lambda _m: None)
    assert pulled == [["ollama", "pull", "nomic-embed-text"]]


def test_ensure_models_noop_when_all_present(monkeypatch):
    monkeypatch.setattr(runtime, "installed_models",
                        lambda *a, **k: {"qwen2.5-coder:14b", "qwen2.5-coder:7b", "nomic-embed-text"})
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not pull")))
    runtime.ensure_models(_hp(), on_event=lambda _m: None)


def test_ensure_models_raises_on_pull_failure(monkeypatch):
    monkeypatch.setattr(runtime, "installed_models", lambda *a, **k: set())
    monkeypatch.setattr(subprocess, "run",
                        lambda args, **k: subprocess.CompletedProcess(args, 1))
    try:
        runtime.ensure_models(_hp(), on_event=lambda _m: None)
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "pull" in str(e).lower()


# ---- ensure_forge_coder ----

def test_ensure_forge_coder_noop_when_present(monkeypatch):
    monkeypatch.setattr(runtime, "installed_models", lambda *a, **k: {"forge-coder"})
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not create")))
    runtime.ensure_forge_coder(_hp(), on_event=lambda _m: None)


def test_ensure_forge_coder_creates_when_absent(monkeypatch):
    monkeypatch.setattr(runtime, "installed_models", lambda *a, **k: set())
    created = []
    def fake_run(args, **kwargs):
        created.append(args)
        return subprocess.CompletedProcess(args, 0)
    monkeypatch.setattr(subprocess, "run", fake_run)
    runtime.ensure_forge_coder(_hp(), on_event=lambda _m: None)
    assert created[0][:3] == ["ollama", "create", "forge-coder"]


def test_ensure_forge_coder_raises_on_create_failure(monkeypatch):
    monkeypatch.setattr(runtime, "installed_models", lambda *a, **k: set())
    monkeypatch.setattr(subprocess, "run",
                        lambda args, **k: subprocess.CompletedProcess(args, 1))
    try:
        runtime.ensure_forge_coder(_hp(), on_event=lambda _m: None)
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "forge-coder" in str(e).lower()


# ---- stop_ollama ----

def _proc_is_ollama(monkeypatch, is_ollama=True):
    out = "ollama\n" if is_ollama else "Python\n"
    monkeypatch.setattr(subprocess, "run",
                        lambda args, **k: subprocess.CompletedProcess(args, 0, stdout=out))


def test_stop_kills_when_pidfile_owned_and_alive(monkeypatch, tmp_path):
    pidfile = tmp_path / "ollama.pid"
    pidfile.write_text("4823")
    monkeypatch.setattr(runtime, "pidfile_path", lambda: pidfile)
    _proc_is_ollama(monkeypatch, True)
    killed = []
    monkeypatch.setattr(runtime.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    events = []
    runtime.stop_ollama(on_event=events.append)
    assert (4823, signal.SIGTERM) in killed
    assert not pidfile.exists()
    assert any("stopped" in e.lower() for e in events)


def test_stop_cleans_stale_pidfile_when_pid_reused(monkeypatch, tmp_path):
    pidfile = tmp_path / "ollama.pid"
    pidfile.write_text("4823")
    monkeypatch.setattr(runtime, "pidfile_path", lambda: pidfile)
    _proc_is_ollama(monkeypatch, False)  # pid now belongs to a different process
    monkeypatch.setattr(runtime.os, "kill",
                        lambda *a: (_ for _ in ()).throw(AssertionError("should not kill")))
    monkeypatch.setattr(runtime, "ollama_reachable", lambda *a, **k: False)
    events = []
    runtime.stop_ollama(on_event=events.append)
    assert not pidfile.exists()
    assert any("not running" in e.lower() for e in events)


def test_stop_leaves_foreign_server_when_no_pidfile(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "pidfile_path", lambda: tmp_path / "ollama.pid")
    monkeypatch.setattr(runtime, "ollama_reachable", lambda *a, **k: True)
    monkeypatch.setattr(runtime.os, "kill",
                        lambda *a: (_ for _ in ()).throw(AssertionError("should not kill")))
    events = []
    runtime.stop_ollama(on_event=events.append)
    assert any("not started by forge" in e.lower() for e in events)


def test_stop_reports_not_running_when_no_pidfile_and_unreachable(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "pidfile_path", lambda: tmp_path / "ollama.pid")
    monkeypatch.setattr(runtime, "ollama_reachable", lambda *a, **k: False)
    events = []
    runtime.stop_ollama(on_event=events.append)
    assert any("not running" in e.lower() for e in events)
