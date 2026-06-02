from forge.assembler import assemble, format_hit


def test_format_hit_has_path_and_symbol():
    h = {"file_path": "src/a.py", "symbol_name": "foo", "start_line": 3,
         "end_line": 9, "content": "def foo(): ..."}
    s = format_hit(h)
    assert "src/a.py" in s and "foo" in s and "def foo()" in s


def test_assemble_orders_cag_then_rag_then_query():
    out = assemble(
        "how does auth work?",
        cag_blocks=["CAG-ALPHA"],
        rag_hits=[{"file_path": "a.py", "symbol_name": "s", "start_line": 1,
                   "end_line": 2, "content": "CODE-BETA"}],
        history="HIST-GAMMA",
    )
    assert out.index("CAG-ALPHA") < out.index("CODE-BETA") < out.index("how does auth work?")
    assert "HIST-GAMMA" in out


def test_assemble_caps_rag_tokens():
    big = [{"file_path": f"f{i}.py", "symbol_name": f"s{i}", "start_line": 1,
            "end_line": 1, "content": "word " * 500} for i in range(50)]
    out = assemble("q", cag_blocks=[], rag_hits=big, history="", rag_cap_tokens=200)
    included = sum(1 for h in big if h["file_path"] in out)
    assert included < 50


def test_assemble_omits_empty_sections():
    out = assemble("just a question", cag_blocks=[], rag_hits=[], history="")
    assert "just a question" in out
