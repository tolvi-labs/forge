from forge.retriever.retriever import retrieve


class FakeStore:
    def __init__(self, hits):
        self._hits = hits
        self.last_top_k = None

    def query(self, embedding, top_k=6):
        self.last_top_k = top_k
        return list(self._hits)


def fake_embed(texts):
    return [[1.0, 0.0] for _ in texts]


def test_retrieve_embeds_query_and_returns_hits():
    store = FakeStore([{"symbol_name": "a", "distance": 0.1, "content": "x"}])
    out = retrieve(store, fake_embed, "find a", top_k=3, rerank=False)
    assert out[0]["symbol_name"] == "a"
    assert store.last_top_k == 3


def test_retrieve_rerank_boosts_symbol_match():
    hits = [
        {"symbol_name": "helper", "distance": 0.10, "content": "x"},
        {"symbol_name": "signIn", "distance": 0.20, "content": "y"},
    ]
    store = FakeStore(hits)
    out = retrieve(store, fake_embed, "fix the signIn bug", top_k=2, rerank=True)
    assert out[0]["symbol_name"] == "signIn"
    assert store.last_top_k == 4
