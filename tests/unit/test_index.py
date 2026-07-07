from pathlib import Path
from forge.index import index_repo, IndexStats
from forge.store.chroma import ChromaStore


def fake_embed(texts):
    return [[float(len(t)), float(sum(map(ord, t[:1])) if t else 0)] for t in texts]


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("def foo():\n    return 1\n")
    (tmp_path / "src" / "b.py").write_text("def bar():\n    return 2\n")
    (tmp_path / ".gitignore").write_text("ignored/\n*.log\n")
    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored" / "c.py").write_text("def nope(): pass\n")
    (tmp_path / "debug.log").write_text("noise\n")
    return tmp_path


def test_index_respects_gitignore(tmp_path):
    root = _repo(tmp_path)
    store = ChromaStore(tmp_path / "idx")
    stats = index_repo(root, store, fake_embed)
    files = set(store.indexed_files())
    assert any(f.endswith("src/a.py") for f in files)
    assert any(f.endswith("src/b.py") for f in files)
    assert not any("ignored" in f for f in files)
    assert not any(f.endswith(".log") for f in files)
    assert isinstance(stats, IndexStats)
    assert stats.files_indexed == 2


def test_reindex_skips_unchanged_and_picks_up_changes(tmp_path):
    root = _repo(tmp_path)
    store = ChromaStore(tmp_path / "idx")
    index_repo(root, store, fake_embed)
    stats2 = index_repo(root, store, fake_embed)
    assert stats2.files_indexed == 0 and stats2.files_skipped == 2
    (root / "src" / "a.py").write_text("def foo():\n    return 999\n")
    stats3 = index_repo(root, store, fake_embed)
    assert stats3.files_indexed == 1 and stats3.files_skipped == 1


def test_index_continues_when_a_file_fails_to_embed(tmp_path):
    # One file that raises during embedding must not abort the whole index run;
    # it is counted as failed and the other files still land.
    root = _repo(tmp_path)
    store = ChromaStore(tmp_path / "idx")

    def flaky_embed(texts):
        if any("bar" in t for t in texts):
            raise RuntimeError("embed boom")
        return fake_embed(texts)

    stats = index_repo(root, store, flaky_embed)
    files = set(store.indexed_files())
    assert any(f.endswith("src/a.py") for f in files)
    assert not any(f.endswith("src/b.py") for f in files)
    assert stats.files_indexed == 1
    assert stats.files_failed == 1


def test_reindex_prunes_deleted_files(tmp_path):
    root = _repo(tmp_path)
    store = ChromaStore(tmp_path / "idx")
    index_repo(root, store, fake_embed)
    (root / "src" / "b.py").unlink()
    stats = index_repo(root, store, fake_embed)
    assert stats.files_pruned == 1
    assert not any(f.endswith("b.py") for f in store.indexed_files())


def test_index_inline_json_no_id_collision(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "config.json").write_text('{"a": 1, "b": 2}\n')
    store = ChromaStore(tmp_path / "idx")
    stats = index_repo(root, store, fake_embed)  # must not raise
    assert any(f.endswith("config.json") for f in store.indexed_files())
    assert stats.files_indexed == 1
