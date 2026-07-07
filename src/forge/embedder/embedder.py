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
# Floor for the adaptive shrink; well under any real model context.
_MIN_INPUT_TOKENS = 128


def _post_embed(
    payload: list[str], *, model: str, host: str, timeout: float,
) -> list[list[float]]:
    resp = httpx.post(
        f"{host}/api/embed", json={"model": model, "input": payload}, timeout=timeout,
    )
    if resp.status_code >= 400:
        resp.raise_for_status()
    return resp.json()["embeddings"]


def _embed_one(
    text: str, *, model: str, host: str, timeout: float, max_tokens: int,
) -> list[float]:
    # Shrink until the model accepts it: cl100k is only a proxy for the model's
    # tokenizer, so a chunk at the budget can still overflow. Halve on each 400.
    budget = max_tokens
    while budget > _MIN_INPUT_TOKENS:
        try:
            return _post_embed(
                [truncate_to_tokens(text, budget)], model=model, host=host, timeout=timeout,
            )[0]
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 400:
                raise
            budget //= 2
    return _post_embed(
        [truncate_to_tokens(text, _MIN_INPUT_TOKENS)], model=model, host=host, timeout=timeout,
    )[0]


def embed(
    texts: list[str], *, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST,
    timeout: float = 120.0, max_input_tokens: int = MAX_INPUT_TOKENS,
) -> list[list[float]]:
    if not texts:
        return []
    payload = [truncate_to_tokens(t, max_input_tokens) for t in texts]
    try:
        return _post_embed(payload, model=model, host=host, timeout=timeout)
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 400:
            raise
        # One input still exceeds the model context. Retry per-input so good
        # inputs keep full budget and only the offenders get shrunk.
        return [
            _embed_one(t, model=model, host=host, timeout=timeout, max_tokens=max_input_tokens)
            for t in texts
        ]
