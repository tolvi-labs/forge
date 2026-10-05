# Changelog

All notable changes to Forge are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `forge agents run --apply [--path <repo>] [--json]`: the local model implements each task of the loaded plan. It sees the full current contents of the task's files plus the plan's per-task `context`, answers with SEARCH/REPLACE blocks that Forge applies and checks itself, and each change that stays inside the task's files and passes the review agent is committed as `[id] title` on a `forge/<feature>` branch. A failed task gets one retry, then is rejected, and the tasks that depend on it are skipped. Rerunning on the branch resumes. Results are written to `results.json` in the plan directory.
- `tasks.json` tasks may carry an optional `context` object (decisions, refs, interfaces, as Magellan emits), which the plan snapshot now keeps.
- Stack profiles accept `reply_reserve_tokens` (default 8192) and `tokenizer_margin` (default 0.10). The apply budget is the smaller of the profile's and the hardware profile's context windows, less both.

### Changed

- `forge plan complete <id>` commits only the task's own `files` when it declares them, and lists any other changed files it left uncommitted.
- `forge outcome` measures rework for an `--apply` task from the branch's last model commit, on the files that task edited last, and takes its token count from the run. Rejected `--apply` tasks are recorded automatically, and `forge report` averages trust only over outcomes that have one.

## [0.2.0] - 2026-09-22

### Added

- `forge detect-hardware`: detects RAM, GPU and architecture and writes the hardware profile that picks the model tier. It ships in the package, so a `pipx install` can generate its own profile.
- `forge status --json` and `forge doctor --json`: machine-readable output for tools that drive Forge. Both include `forge_version`, and each doctor check has a stable `id`. Text output is unchanged.

### Changed

- `setup/bootstrap.sh` installs the CLI first, then detects hardware with `forge detect-hardware`.
- Missing-profile messages in `forge start`, `forge status` and `forge doctor` now name `forge detect-hardware`.

### Removed

- `setup/detect-hardware.sh`, replaced by `forge detect-hardware` with the same RAM tiers, GPU detection and 8GB fallback.

### Fixed

- A `pipx install` could not run `forge start`, `forge status` or `forge chat`: the hardware profile they need came from a setup script the package does not ship. The README's pipx steps now run `forge detect-hardware` first.

## [0.1.0] - 2026-09-09

Initial release. Published to PyPI as `tolvi-forge`.

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
