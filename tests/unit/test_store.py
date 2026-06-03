from pathlib import Path
from forge.store.chroma import ChromaStore
from forge.chunker.chunk import Chunk


def _chunk(fp, line, text):
    return Chunk.make(file_path=fp, language="python", chunk_type="function",
                      symbol_name=f"s{line}", start_line=line, end_line=line, content=text)


def _store(tmp_path: Path) -> ChromaStore:
    return ChromaStore(tmp_path / "idx")


def test_replace_file_then_indexed_files_reports_checksum(tmp_path):
    s = _store(tmp_path)
    chunks = [_chunk("a.py", 1, "def s1(): pass")]
    s.replace_file("a.py", "sum-a", chunks, [[0.1, 0.2]])
    assert s.indexed_files() == {"a.py": "sum-a"}


def test_replace_file_overwrites_prior_chunks(tmp_path):
    s = _store(tmp_path)
    s.replace_file("a.py", "v1", [_chunk("a.py", 1, "old")], [[0.1, 0.2]])
    s.replace_file("a.py", "v2", [_chunk("a.py", 2, "new")], [[0.3, 0.4]])
    assert s.indexed_files() == {"a.py": "v2"}
    assert s.count() == 1


def test_delete_file_removes_chunks(tmp_path):
    s = _store(tmp_path)
    s.replace_file("a.py", "v1", [_chunk("a.py", 1, "x")], [[0.1, 0.2]])
    s.delete_file("a.py")
    assert s.indexed_files() == {}
    assert s.count() == 0


def test_query_returns_nearest(tmp_path):
    s = _store(tmp_path)
    s.replace_file("a.py", "v1",
                   [_chunk("a.py", 1, "alpha"), _chunk("a.py", 2, "beta")],
                   [[1.0, 0.0], [0.0, 1.0]])
    hits = s.query([0.9, 0.1], top_k=1)
    assert len(hits) == 1
    assert hits[0]["symbol_name"] == "s1"


def test_persistence_across_instances(tmp_path):
    s1 = _store(tmp_path)
    s1.replace_file("a.py", "v1", [_chunk("a.py", 1, "x")], [[0.1, 0.2]])
    s2 = _store(tmp_path)
    assert s2.indexed_files() == {"a.py": "v1"}


def test_replace_file_handles_same_line_chunks(tmp_path):
    # Two chunks sharing a start/end line (e.g. inline JSON pairs) must not collide.
    s = _store(tmp_path)
    c1 = _chunk("a.json", 1, '"a": 1')
    c2 = _chunk("a.json", 1, '"b": 2')
    s.replace_file("a.json", "v1", [c1, c2], [[1.0, 0.0], [0.0, 1.0]])
    assert s.count() == 2


def test_query_includes_chunk_id(tmp_path):
    s = _store(tmp_path)
    s.replace_file("a.py", "v1", [_chunk("a.py", 1, "alpha")], [[1.0, 0.0]])
    hits = s.query([1.0, 0.0], top_k=1)
    assert hits[0]["chunk_id"].startswith("a.py::1-1")
