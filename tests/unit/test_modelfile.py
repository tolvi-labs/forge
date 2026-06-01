from forge.modelfile import render_modelfile

TEMPLATE = "FROM {{RECOMMENDED_MODEL}}\nPARAMETER num_ctx {{MAX_CONTEXT}}\n"


def test_render_substitutes_model_and_context():
    out = render_modelfile(TEMPLATE, recommended_model="qwen2.5-coder:14b", max_context=65536)
    assert "FROM qwen2.5-coder:14b" in out
    assert "PARAMETER num_ctx 65536" in out
    assert "{{" not in out


def test_render_from_file(tmp_path):
    tmpl = tmp_path / "Modelfile.tmpl"
    tmpl.write_text(TEMPLATE)
    out = render_modelfile(tmpl.read_text(), recommended_model="qwen2.5-coder:7b", max_context=32768)
    assert "FROM qwen2.5-coder:7b" in out
    assert "PARAMETER num_ctx 32768" in out
