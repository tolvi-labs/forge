from forge.vault.loader import VaultDoc
from forge.vault.selector import select_docs


def _fake_embed(texts):
    # 2-D toy space: 'postgres' texts point one way, everything else the other.
    return [[1.0, 0.0] if "postgres" in t.lower() else [0.0, 1.0] for t in texts]


def _docs():
    # newest-first order, as read_docs returns them
    return [
        VaultDoc(name="2026-07-01-newest", summary="unrelated alpha"),
        VaultDoc(name="2026-06-01-mid", summary="unrelated beta"),
        VaultDoc(name="2026-05-01-old", summary="use postgres for storage"),
    ]


def test_relevant_old_decision_selected_over_newer_irrelevant():
    chosen = select_docs(_docs(), query="which database, postgres?",
                         embed_fn=_fake_embed, max_tokens=10000, core_recent_n=1)
    names = [d.name for d in chosen]
    assert "2026-05-01-old" in names           # relevant old decision reached context
    assert names[0] == "2026-07-01-newest"      # core (newest) leads
    assert names.index("2026-05-01-old") < names.index("2026-06-01-mid")  # ranked by relevance


def test_core_recent_always_present_even_if_irrelevant():
    chosen = select_docs(_docs(), query="postgres", embed_fn=_fake_embed,
                         max_tokens=10000, core_recent_n=2)
    names = [d.name for d in chosen]
    assert "2026-07-01-newest" in names and "2026-06-01-mid" in names


def test_query_none_is_recency_order():
    chosen = select_docs(_docs(), query=None, embed_fn=None,
                         max_tokens=10000, core_recent_n=0)
    assert [d.name for d in chosen] == ["2026-07-01-newest", "2026-06-01-mid", "2026-05-01-old"]


def test_embed_failure_falls_back_to_recency():
    def boom(texts):
        raise RuntimeError("ollama down")
    chosen = select_docs(_docs(), query="postgres", embed_fn=boom,
                         max_tokens=10000, core_recent_n=1)
    assert [d.name for d in chosen] == ["2026-07-01-newest", "2026-06-01-mid", "2026-05-01-old"]


def test_budget_respected():
    assert select_docs(_docs(), query=None, embed_fn=None,
                       max_tokens=1, core_recent_n=0) == []
