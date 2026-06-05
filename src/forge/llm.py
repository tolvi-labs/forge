"""Call the local Ollama model via /api/generate (non-streaming)."""
from __future__ import annotations

from collections.abc import Callable

import httpx

DEFAULT_MODEL = "forge-coder"
DEFAULT_HOST = "http://localhost:11434"


def generate(prompt: str, *, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST,
             timeout: float = 300.0,
             stats_callback: Callable[[dict], None] | None = None) -> str:
    resp = httpx.post(
        f"{host}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    if resp.status_code >= 400:
        resp.raise_for_status()
    data = resp.json()
    if stats_callback is not None:
        eval_count = data.get("eval_count", 0)
        eval_duration = data.get("eval_duration", 0)
        prompt_eval_count = data.get("prompt_eval_count", 0)
        prompt_eval_duration = data.get("prompt_eval_duration", 0)
        stats_callback({
            "model": model,
            "tokens_out": eval_count,
            "tokens_in": prompt_eval_count,
            "tokens_per_sec": round(eval_count / (eval_duration / 1_000_000_000), 1) if eval_duration > 0 else 0.0,
            "duration_ms": round((eval_duration + prompt_eval_duration) / 1_000_000, 1),
        })
    return data["response"]
