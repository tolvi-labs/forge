"""Bring the local Forge runtime up and down.

`ensure_*` functions make the local environment ready (Ollama reachable,
required models pulled, forge-coder created); `stop_ollama` shuts down a
server that forge itself started. Presentation is the caller's job — each
function reports progress through an `on_event` callback.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from forge import config, llm, modelfile

OnEvent = Callable[[str], None]

_STARTUP_TIMEOUT_S = 15.0
_POLL_INTERVAL_S = 0.5
_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "ollama" / "Modelfile.tmpl"


def pidfile_path() -> Path:
    return config.data_dir() / "ollama.pid"


def ollama_reachable(host: str = llm.DEFAULT_HOST, timeout: float = 1.0) -> bool:
    try:
        return httpx.get(f"{host}/api/tags", timeout=timeout).status_code < 400
    except httpx.HTTPError:
        return False


def installed_models(host: str = llm.DEFAULT_HOST) -> set[str]:
    """Names from /api/tags, plus a copy with any ``:latest`` tag stripped."""
    resp = httpx.get(f"{host}/api/tags", timeout=5.0)
    names: set[str] = set()
    for model in resp.json().get("models", []):
        name = model["name"]
        names.add(name)
        if name.endswith(":latest"):
            names.add(name[: -len(":latest")])
    return names


def required_models(hp: config.HardwareProfile) -> list[str]:
    """Models forge needs pulled, derived from the profile (order-preserving, deduped)."""
    out: list[str] = []
    for model in (hp.recommended_model, hp.autocomplete_model, hp.embedding_model):
        if model and model not in out:
            out.append(model)
    return out


def ensure_ollama(host: str = llm.DEFAULT_HOST, *, on_event: OnEvent) -> None:
    if ollama_reachable(host):
        on_event("Ollama already running")
        return
    if shutil.which("ollama") is None:
        raise RuntimeError("Ollama not installed — install from https://ollama.com")

    on_event("Starting Ollama…")
    proc = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    pidfile = pidfile_path()
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(proc.pid))

    deadline = time.monotonic() + _STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        if ollama_reachable(host):
            on_event(f"Ollama started (pid {proc.pid})")
            return
        time.sleep(_POLL_INTERVAL_S)
    raise RuntimeError(f"Ollama did not become reachable within {int(_STARTUP_TIMEOUT_S)}s")


def ensure_models(hp: config.HardwareProfile, host: str = llm.DEFAULT_HOST,
                  *, on_event: OnEvent) -> None:
    present = installed_models(host)
    missing = [m for m in required_models(hp) if m not in present]
    if not missing:
        on_event("Models present")
        return
    for model in missing:
        on_event(f"Pulling {model}…")
        if subprocess.run(["ollama", "pull", model]).returncode != 0:
            raise RuntimeError(f"ollama pull {model} failed")


def ensure_forge_coder(hp: config.HardwareProfile, host: str = llm.DEFAULT_HOST,
                       *, on_event: OnEvent) -> None:
    if "forge-coder" in installed_models(host):
        on_event("forge-coder ready")
        return
    rendered = modelfile.render_modelfile(
        _TEMPLATE_PATH.read_text(),
        recommended_model=hp.recommended_model,
        max_context=hp.max_context_tokens,
    )
    with tempfile.NamedTemporaryFile("w", suffix=".Modelfile", delete=False) as tmp:
        tmp.write(rendered)
        tmp_path = tmp.name
    try:
        on_event("Creating forge-coder…")
        if subprocess.run(["ollama", "create", "forge-coder", "-f", tmp_path]).returncode != 0:
            raise RuntimeError("ollama create forge-coder failed")
    finally:
        os.unlink(tmp_path)


def _process_is_ollama(pid: int) -> bool:
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "comm="],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and "ollama" in result.stdout.lower()


def stop_ollama(*, on_event: OnEvent) -> None:
    pidfile = pidfile_path()
    if pidfile.exists():
        try:
            pid = int(pidfile.read_text().strip())
        except ValueError:
            pid = None
        if pid is not None and _process_is_ollama(pid):
            os.kill(pid, signal.SIGTERM)
            pidfile.unlink(missing_ok=True)
            on_event(f"Stopped Ollama (pid {pid}, started by forge)")
            return
        # Dead PID or reused by a different process — stale pidfile.
        pidfile.unlink(missing_ok=True)

    if ollama_reachable():
        on_event("Ollama is running but was not started by forge — leaving it")
    else:
        on_event("Ollama is not running")
