"""Embed a query, rank store hits by vector distance + symbol-name match."""
from __future__ import annotations

from typing import Callable

EmbedFn = Callable[[list[str]], list[list[float]]]


def _score(hit: dict, query_lower: str) -> float:
    base = -float(hit.get("distance", 0.0))
    symbol = str(hit.get("symbol_name", "")).lower()
    boost = 0.5 if symbol and symbol in query_lower else 0.0
    return base + boost


def retrieve(store, embed_fn: EmbedFn, query: str, *, top_k: int = 6,
             rerank: bool = True) -> list[dict]:
    vector = embed_fn([query])[0]
    fetch = top_k * 2 if rerank else top_k
    hits = store.query(vector, top_k=fetch)
    if not rerank:
        return hits[:top_k]
    ranked = sorted(hits, key=lambda h: _score(h, query.lower()), reverse=True)
    return ranked[:top_k]
