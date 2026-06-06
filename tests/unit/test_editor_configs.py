# tests/unit/test_editor_configs.py
import json
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
CONTINUE = REPO / "integrations" / "vscode" / "config.yaml"
CURSOR_MCP = REPO / "integrations" / "cursor" / "mcp.json"


def test_continue_config_routes_ollama_models():
    text = CONTINUE.read_text()
    # chat -> forge-coder, autocomplete -> 7b, embed -> nomic
    assert "forge-coder" in text
    assert "qwen2.5-coder:7b" in text
    assert "nomic-embed-text" in text
    assert "provider: ollama" in text
    # uses Continue's current schema, not the deprecated config.json
    assert "schema: v1" in text


def test_continue_config_has_context_and_no_mcp():
    text = CONTINUE.read_text()
    # MCP servers belong in Claude Code, not Continue.dev — they only pollute
    # the model's context here and provoke hallucinated tool-call responses.
    assert "mcpServers" not in text
    for prov in ("code", "diff", "folder"):
        assert prov in text


def test_cursor_mcp_matches_canonical_shape():
    servers = json.loads(CURSOR_MCP.read_text())["mcpServers"]
    canonical = json.loads((REPO / "mcp" / "servers.json").read_text())["mcpServers"]
    assert servers == canonical  # cursor mcp.json is a verbatim copy of the canonical
