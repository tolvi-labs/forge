# Forge — agent conventions

Forge is a local-first AI dev environment, part of Tolvi Labs. Python core, Click CLI, installed into a 3.12 venv via uv. Match existing style; run `ruff check .` and `pytest` before committing.

<!-- VAULT-INDEX:START repo=forge generated=2026-07-10 -->
## Vault Index

*Auto-generated. Re-run the index generator to refresh.*

### Decisions

- `2026-07-10-trd-external-checklist-ephemeral.md` — Plans live external and uncommitted; the repo keeps code and durable decisions
- `2026-07-10-forge-v0-batch-lane.md` — Forge v0: the local model's lane is async batch execution, not the keystroke line
- `2026-07-08-measure-ship-gate-from-plan-loop.md` — Measure the ship gate as a byproduct of the plan loop
- `2026-07-04-forge-defer-ship-until-usage-data.md` — Ship Forge — but defer until there is real personal usage data
- `2026-06-06-tolvi-modelfile-personality.md` — Tolvi personality in the forge-coder Modelfile
- `2026-06-06-forge-start-stop-runtime.md` — forge start / forge stop — runtime lifecycle commands
- `2026-06-05-watch-state-plumbing-design.md` — Watch state: three artifact files for TUI consumption
- `2026-06-05-forge-watch-tui-design.md` — forge watch: poll-based Rich TUI with auto-discovery and tab navigation
- `2026-06-05-forge-vault-env-var-override.md` — FORGE_VAULT env var overrides the default vault path
- `2026-06-05-cli-path-via-local-bin-symlink.md` — CLI made available on PATH via ~/.local/bin symlink
- `2026-06-02-tree-sitter-language-pack.md` — Tree-sitter language-pack binding
- `2026-06-02-mcp-package-verification.md` — MCP package npm-verification
- `2026-06-02-lightweight-orchestrator-over-langgraph.md` — Multi-agent scaffold; LangGraph deferred
- `2026-06-02-tolvi-vault-bridge.md` — Tolvi vault bridge
- `2026-06-02-class-level-chunking.md` — Class-level chunking granularity
- `2026-06-01-standalone-config-and-python-core.md` — Standalone config and Python core

<!-- VAULT-INDEX:END -->
