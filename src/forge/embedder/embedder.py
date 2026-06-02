"""Embed text via Ollama's /api/embed endpoint (local, batch)."""
from __future__ import annotations

import httpx

DEFAULT_MODEL = "nomic-embed-text"
DEFAULT_HOST = "http://localhost:11434"


def embed(
    texts: list[str], *, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST,
    timeout: float = 120.0,
) -> list[list[float]]:
    if not texts:
        return []
    resp = httpx.post(
        f"{host}/api/embed", json={"model": model, "input": texts}, timeout=timeout,
    )
    if resp.status_code >= 400:
        resp.raise_for_status()
    return resp.json()["embeddings"]
