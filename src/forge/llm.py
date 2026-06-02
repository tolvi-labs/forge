"""Call the local Ollama model via /api/generate (non-streaming)."""
from __future__ import annotations

import httpx

DEFAULT_MODEL = "forge-coder"
DEFAULT_HOST = "http://localhost:11434"


def generate(prompt: str, *, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST,
             timeout: float = 300.0) -> str:
    resp = httpx.post(
        f"{host}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    if resp.status_code >= 400:
        resp.raise_for_status()
    return resp.json()["response"]
