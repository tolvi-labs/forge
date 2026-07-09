# Changelog

All notable changes to Forge are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Initial release candidate. Forge has not yet been published to PyPI or Homebrew.

### Added

- Local-first Claude → Local → Claude workflow: Claude plans and verifies, a tuned local model (qwen2.5-coder via Ollama) does the high-volume implementation at zero token cost and full privacy.
- `forge index` — Tree-sitter AST chunking across 9 languages with a line-based fallback, local embeddings via `nomic-embed-text`, and a ChromaDB store with file-checksum incremental re-indexing.
- `forge search` / `forge chat` — semantic retrieval and chat with a hybrid CAG + RAG context window, including the repo's Tolvi vault when present.
- `forge plan load/next/complete/status` and `forge verify` — drive a Claude-produced `tasks.json` in dependency order with per-task auto-commits and an exportable diff.
- `forge outcome` / `forge report` — measure the local-model gate as a byproduct of the plan loop: `outcome` auto-fills rework churn (from git) and local tokens (from `inference.log`) and records accepted/trust/type/failure-reason to a per-plan `outcomes.jsonl`; `report [--all]` pools those into acceptance rate, median churn, token economics, and mean trust.
- `forge start` / `stop` / `status` / `doctor` — Ollama lifecycle, model/`forge-coder` provisioning, and environment diagnostics.
- `forge watch` — live TUI dashboard for active plans, loop phase, inference rate, and context fill.
- `forge profile` — stack profiles that shape the context window.
- Tolvi vault bridge: decisions and rejected alternatives from a repo's `vault/` (or `FORGE_VAULT`) are fed into the model's always-on context, selected by relevance to the query beyond a recency-based core.
- Editor integrations: Continue.dev (VS Code) and Cursor against the same Ollama backend, plus a pre-wired MCP layer for Claude Code.
- `setup/bootstrap.sh` installer: hardware detection, model pulls, `forge-coder` build, CLI install into a dedicated Python 3.12 venv, and editor/MCP config generation.
