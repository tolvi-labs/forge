import httpx
from forge.embedder.embedder import embed


def test_embed_posts_batch_and_returns_vectors(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["input"] = json["input"]
        captured["model"] = json["model"]
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2], [0.3, 0.4]]})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = embed(["a", "b"])
    assert out == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["url"].endswith("/api/embed")
    assert captured["input"] == ["a", "b"]
    assert captured["model"] == "nomic-embed-text"


def test_embed_empty_returns_empty(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("should not POST for empty input")
    monkeypatch.setattr(httpx, "post", boom)
    assert embed([]) == []


def test_embed_truncates_oversized_input(monkeypatch):
    # A chunk larger than the embedding model's context (e.g. a lockfile) must be
    # trimmed before the POST so Ollama never 400s on "input length exceeds context".
    from forge.chunker.chunk import count_tokens

    captured = {}

    def fake_post(url, json, timeout):
        captured["input"] = json["input"]
        return httpx.Response(200, json={"embeddings": [[0.0]]})

    monkeypatch.setattr(httpx, "post", fake_post)
    huge = "lorem ipsum dolor sit amet " * 20000  # ~100k tokens
    embed([huge])
    assert len(captured["input"]) == 1
    assert count_tokens(captured["input"][0]) <= 2048
