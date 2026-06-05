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


def test_generate_calls_stats_callback_with_metrics(monkeypatch):
    def fake_post(url, json, timeout):
        return httpx.Response(200, json={
            "response": "hello",
            "model": "forge-coder",
            "eval_count": 80,
            "eval_duration": 2_000_000_000,
            "prompt_eval_count": 200,
            "prompt_eval_duration": 500_000_000,
        })

    monkeypatch.setattr(httpx, "post", fake_post)
    captured = {}
    generate("say hi", model="forge-coder", stats_callback=lambda s: captured.update(s))
    assert captured["tokens_out"] == 80
    assert captured["tokens_in"] == 200
    assert captured["tokens_per_sec"] == 40.0
    assert captured["duration_ms"] == 2500.0
    assert captured["model"] == "forge-coder"
