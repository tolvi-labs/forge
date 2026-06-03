# Forge × Cursor

Cursor talks to the same local Ollama backend.

1. **Models:** Cursor Settings → Models → enable "Ollama" and set the base URL to
   `http://localhost:11434`. Add `forge-coder` as a custom model.
2. **MCP:** copy `mcp.json` to `~/.cursor/mcp.json` (global) or `.cursor/mcp.json`
   (per-project), then fill in the credential placeholders for github/jira/gcloud.

Continue.dev (see `../vscode/`) is the primary, fully-scriptable integration; Cursor
is supported as an alternative for its inline UX.
