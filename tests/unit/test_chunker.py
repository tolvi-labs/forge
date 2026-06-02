from forge.chunker.chunk import Chunk, count_tokens, checksum


def test_count_tokens_nonzero():
    assert count_tokens("def foo(): pass") > 0


def test_checksum_is_stable_and_content_sensitive():
    a = checksum("hello")
    assert a == checksum("hello")
    assert a != checksum("hello!")
    assert len(a) == 64  # sha256 hex


def test_chunk_make_computes_fields():
    c = Chunk.make(
        file_path="src/a.py", language="python", chunk_type="function",
        symbol_name="foo", start_line=1, end_line=2, content="def foo():\n    pass",
    )
    assert c.token_count == count_tokens("def foo():\n    pass")
    assert c.checksum == checksum("def foo():\n    pass")
    assert c.chunk_id == "src/a.py::1-2"
