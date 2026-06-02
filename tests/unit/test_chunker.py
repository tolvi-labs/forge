from forge.chunker import chunk_file, detect_language
from forge.chunker.chunk import Chunk, count_tokens, checksum
from forge.chunker.fallback import chunk_lines
from forge.chunker.treesitter import chunk_source

PY_SRC = '''import os


def alpha(x):
    return x + 1


class Beta:
    def method(self):
        return 2
'''

CSS_SRC = ".btn { color: red; }\n.card { padding: 4px; }\n"


def test_treesitter_python_extracts_function_and_class():
    chunks = chunk_source(PY_SRC, language="python", file_path="a.py")
    names = {(c.chunk_type, c.symbol_name) for c in chunks}
    assert ("function", "alpha") in names
    assert ("class", "Beta") in names
    alpha = next(c for c in chunks if c.symbol_name == "alpha")
    assert alpha.start_line == 4 and alpha.language == "python"


def test_treesitter_css_extracts_rule_sets():
    chunks = chunk_source(CSS_SRC, language="css", file_path="a.css")
    assert len(chunks) == 2
    assert all(c.chunk_type == "rule-set" for c in chunks)
    assert chunks[0].symbol_name == ".btn"


def test_treesitter_no_symbols_emits_single_file_chunk():
    chunks = chunk_source("x = 1\n", language="python", file_path="c.py")
    assert len(chunks) == 1
    assert chunks[0].chunk_type == "file"


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


def test_fallback_splits_on_blank_lines():
    src = "block one\nline two\n\nblock two\nline\n"
    chunks = chunk_lines(src, language="text", file_path="x.txt")
    assert len(chunks) == 2
    assert chunks[0].chunk_type == "block"
    assert "block one" in chunks[0].content
    assert chunks[1].start_line == 4


def test_fallback_caps_large_block_with_overlap():
    src = "\n".join(f"line {i}" for i in range(150)) + "\n"
    chunks = chunk_lines(src, language="text", file_path="big.txt")
    assert len(chunks) >= 3
    assert chunks[1].start_line < chunks[0].end_line + 1 + 10


def test_detect_language_by_extension():
    assert detect_language("a.py") == "python"
    assert detect_language("a.tsx") == "tsx"
    assert detect_language("a.unknown") is None


def test_chunk_file_python(tmp_path):
    p = tmp_path / "m.py"
    p.write_text("def foo():\n    return 1\n")
    chunks = chunk_file(p)
    assert any(c.symbol_name == "foo" for c in chunks)
    assert all(c.file_path == str(p) for c in chunks)


def test_chunk_file_unknown_extension_uses_fallback(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("alpha\nbeta\n\ngamma\n")
    chunks = chunk_file(p)
    assert chunks and all(c.chunk_type == "block" for c in chunks)
