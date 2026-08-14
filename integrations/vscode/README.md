# Forge × Continue.dev (VS Code)

1. Install the **Continue** extension in VS Code.
2. Copy `config.yaml` to `~/.continue/config.yaml` (bootstrap.sh does this for you).
3. Ensure Ollama is running and `forge-coder` exists (`forge doctor`).

Routes chat/edit to `forge-coder` (qwen3-coder:30b reasoning), autocomplete to `qwen2.5-coder:7b`
(fast), and embeddings to `nomic-embed-text` — all local. Credentialed MCP servers
(github, jira, gcloud, firebase) are defined in the repo's `mcp/servers.json`; add
them to your Continue config once you've filled in credentials.
