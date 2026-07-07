"""Select which vault docs enter the CAG block: a recency-based always-on core
plus query-relevant docs for the remaining token budget.

Relevance is scored on the fly (embed the query + candidate summaries with the
existing embedder, cosine-rank) so the vault path stays independent of the code
index. Any embedding failure falls back to recency order — a ranking hiccup must
never break `forge chat`.
"""
from __future__ import annotations

import math
from typing import Callable

from forge.chunker.chunk import count_tokens
from forge.vault.loader import VaultDoc, entry_text

EmbedFn = Callable[[list[str]], list[list[float]]]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _rank_by_relevance(docs: list[VaultDoc], query: str, embed_fn: EmbedFn) -> list[VaultDoc]:
    try:
        qv = embed_fn([query])[0]
        dvs = embed_fn([d.summary for d in docs])
    except Exception:
        return docs  # recency fallback — never let ranking break sign-out/chat
    # stable sort keeps recency order among equal scores
    return [d for d, _ in sorted(zip(docs, dvs), key=lambda p: _cosine(qv, p[1]), reverse=True)]


def select_docs(
    docs: list[VaultDoc], *, query: str | None, embed_fn: EmbedFn | None,
    max_tokens: int, core_recent_n: int,
) -> list[VaultDoc]:
    """Return the docs to render, within `max_tokens` of entry budget. `docs` is
    newest-first. The first `core_recent_n` are the always-on core; the rest are
    ranked by relevance to `query` (recency order if no query/embed_fn)."""
    core = docs[:core_recent_n]
    rest = docs[core_recent_n:]
    ranked_rest = _rank_by_relevance(rest, query, embed_fn) if (query and embed_fn and rest) else rest

    chosen: list[VaultDoc] = []
    used = 0
    for doc in (*core, *ranked_rest):
        cost = count_tokens(entry_text(doc))
        if used + cost > max_tokens:
            continue  # skip, don't break: one large doc must not block smaller ones
        chosen.append(doc)
        used += cost
    return chosen
