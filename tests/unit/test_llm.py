import httpx
from forge.llm import generate


def test_generate_posts_prompt_and_returns_response(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["model"] = json["model"]
        captured["prompt"] = json["prompt"]
        captured["stream"] = json["stream"]
        return httpx.Response(200, json={"response": "hello from forge-coder"})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = generate("say hi", model="forge-coder")
    assert out == "hello from forge-coder"
    assert captured["url"].endswith("/api/generate")
    assert captured["model"] == "forge-coder"
    assert captured["prompt"] == "say hi"
    assert captured["stream"] is False
