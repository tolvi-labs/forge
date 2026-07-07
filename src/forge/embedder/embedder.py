"""Embed text via Ollama's /api/embed endpoint (local, batch)."""
from __future__ import annotations

import httpx

from forge.chunker.chunk import truncate_to_tokens

DEFAULT_MODEL = "nomic-embed-text"
DEFAULT_HOST = "http://localhost:11434"

# nomic-embed-text exposes a 2048-token context. Its tokenizer isn't cl100k and
# runs denser on punctuation-heavy text (JSON, lockfiles), so we budget inputs
# well under 2048 cl100k tokens to leave margin and never trip a 400. Anything
# longer (an oversized fallback chunk) is truncated for the embedding only; the
# full chunk content is still stored.
MAX_INPUT_TOKENS = 1200


def embed(
    texts: list[str], *, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST,
    timeout: float = 120.0, max_input_tokens: int = MAX_INPUT_TOKENS,
) -> list[list[float]]:
    if not texts:
        return []
    payload = [truncate_to_tokens(t, max_input_tokens) for t in texts]
    resp = httpx.post(
        f"{host}/api/embed", json={"model": model, "input": payload}, timeout=timeout,
    )
    if resp.status_code >= 400:
        resp.raise_for_status()
    return resp.json()["embeddings"]
