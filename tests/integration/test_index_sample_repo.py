from pathlib import Path
from forge.index import index_repo
from forge.store.chroma import ChromaStore

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample-repo"

VOCAB = ["sign_in", "AuthContext", "LoginForm", "btn-primary", "btn-secondary"]


def fake_embed(texts):
    # token-bag pseudo-embedding: deterministic, no Ollama. One dimension per vocab
    # term so an exact-term query vector lands that term's own chunk nearest (L2).
    return [[float(t.count(w)) for w in VOCAB] for t in texts]


def test_indexes_all_languages_and_respects_gitignore(tmp_path):
    store = ChromaStore(tmp_path / "idx")
    stats = index_repo(FIXTURE, store, fake_embed)
    files = set(store.indexed_files())
    assert any(f.endswith("auth.py") for f in files)
    assert any(f.endswith("LoginForm.tsx") for f in files)
    assert any(f.endswith("buttons.css") for f in files)
    assert not any("secret" in f for f in files)
    assert stats.chunks_written >= 4


def test_query_finds_expected_symbol(tmp_path):
    store = ChromaStore(tmp_path / "idx")
    index_repo(FIXTURE, store, fake_embed)
    q = [1.0, 0.0, 0.0, 0.0, 0.0]
    hits = store.query(q, top_k=1)
    assert hits and hits[0]["symbol_name"] == "sign_in"
