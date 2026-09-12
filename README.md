# Forge

A local-first AI development environment. A tuned local model (qwen2.5-coder via Ollama) does the high-volume implementation work; Claude plans and verifies. Zero token cost and full privacy during execution.

> **Status:** Pre-1.0. MVP complete (phases P1–P5). The full local loop works end-to-end; packaged distribution (Homebrew / PyPI / Docker) is the remaining work. See [`ROADMAP.md`](./ROADMAP.md).

## The workflow

```
Claude (plan → tasks.json) → Forge (execute, local, $0) → Claude (verify diff)
```

Claude is better at *thinking*; the local model is better at *doing at scale*. Forge is the execution layer between them. It indexes your codebase, answers questions with that code (and your decisions) in context, drives a Claude-produced plan task-by-task, and hands the diff back for review.

## Tolvi is the substrate

Forge runs standalone. But it runs **best** with [Tolvi](https://github.com/tolvi-labs/tolvi), the per-repo engineering-knowledge vault. Tolvi is the engine oil. A local model that knows *what* the code is makes plausible changes; a model that also knows *why* the codebase is the way it is (the decisions and rejected alternatives captured in a Tolvi vault) makes changes that respect intent. When a `vault/` exists in your repo, Forge feeds it into the model's always-on context.

**Already have a Tolvi vault?** If your vault lives outside the repo (e.g. a standalone Tolvi setup with a shared `~/vaults/my-project/` directory), point Forge at it with the `FORGE_VAULT` env var instead of symlinking:

```bash
export FORGE_VAULT=~/Developer-Vault/my-project
forge chat -m "how does sign-in work?"
```

Add it to your shell profile or a per-project `.envrc` (via [direnv](https://direnv.net)) so it's always set when working in that repo.

**You may not need it.** A solo dev on a greenfield repo, or a team without a decision vault, gets full value from Forge's code retrieval alone. Tolvi is the multiplier, not the dependency.

## Install

Install the CLI from PyPI, then bring up the local models:

```bash
pipx install tolvi-forge
# or: pip install tolvi-forge

forge start     # pulls the Ollama models and builds forge-coder on first run
forge doctor    # diagnose any missing pieces
```

`pipx` is recommended over `pip` for CLI tools: it installs Forge into its own isolated environment rather than your active virtualenv, avoiding dependency conflicts with whatever else you have installed. No Homebrew formula yet; Forge's dependency tree (ChromaDB, tree-sitter, tiktoken) doesn't fit Homebrew's typical vendored-resource packaging model well, so PyPI is the primary distribution channel.

For a fully guided setup (hardware detection, model pulls, and the Continue.dev + MCP editor configs written for you) install from source:

```bash
git clone https://github.com/tolvi-labs/forge && cd forge
bash setup/bootstrap.sh
```

The installer detects your hardware, pulls the right Ollama models, builds the `forge-coder` model, installs the CLI into a dedicated Python 3.12 venv, writes the Continue.dev + MCP configs, and symlinks `forge` into `~/.local/bin` (adding it to `PATH` in your shell profile if needed).

`forge start` is also the command to use after a reboot or in a fresh shell: it starts Ollama in the background and leaves it running. `forge stop` shuts down that server (only if Forge started it).

## VS Code (Continue.dev): optional keystroke assist

Forge's real surface is the batch loop above: a frontier model plans, the local model executes a whole task set, and you review the diff. This section is the *other altitude*: opt-in, in-editor assistance for when you want a local model at your cursor. It runs entirely on your hardware, so treat it as best-effort: on a laptop, local autocomplete will not match a cloud tool's latency, and that is a hardware reality rather than a defect Forge is hiding. Reach for the batch loop when you want the local model's real strength; reach for this only when you want a quick local completion or edit without leaving the editor.

Bootstrap writes the Continue config to `~/.continue/config.yaml` automatically. To finish the setup:

1. Install the **[Continue](https://marketplace.visualstudio.com/items?itemName=Continue.continue)** extension in VS Code.
2. Open the Continue panel (sidebar). It will pick up `~/.continue/config.yaml` on first load.
3. Confirm Ollama is running (`ollama list` should show `forge-coder` and `qwen2.5-coder:7b`).

The config wires four models automatically:
- **Chat / Edit / Apply** → `qwen2.5-coder:7b` (fast, best for everyday coding questions)
- **Chat (Deep)** → `forge-coder` (qwen3-coder:30b, long context, switch to this for architecture or multi-file work)
- **Autocomplete** → `qwen2.5-coder:7b` (best-effort; latency tracks your hardware)
- **Embeddings** → `nomic-embed-text`

MCP tool integrations (git, github, jira, gcloud, firebase, context7, sequential-thinking, playwright) are configured for Claude Code, not Continue.dev. See [`mcp/servers.json`](./mcp/servers.json). Wiring MCP servers into Continue.dev injects tool definitions that cause smaller models to emit tool-call JSON instead of answers.

## Quickstart

```bash
forge index .                       # index this repo (incremental, respects .gitignore)
forge search "auth token refresh"   # inspect what retrieval returns
forge chat -m "how does sign-in work?"   # ask, with CAG+RAG (and your Tolvi vault) in context

# Claude → Local → Claude
forge plan load tasks.json          # load a Claude-produced plan (schema-validated)
forge plan next                     # next dependency-unblocked task
forge plan complete task-001        # mark done + auto-commit the work
forge verify                        # export the diff + manifest for Claude to review
```

## Commands

| Command | What it does |
|---|---|
| `forge start` / `stop` | Bring Ollama up + ensure models/`forge-coder` then show status; stop the server (only if Forge started it) |
| `forge status` / `doctor` | Active model/context/profile; environment diagnostics |
| `forge index [--watch]` | Tree-sitter chunk + embed a repo into a local ChromaDB index |
| `forge watch` | Live TUI dashboard: auto-discovers active plans, loop phase, inference rate, context fill |
| `forge search` / `chat` | Semantic retrieval; chat with CAG+RAG context (Tolvi vault included) |
| `forge plan load/next/complete/status` | Drive a Claude `tasks.json` in dependency order, auto-committing per task |
| `forge verify` | Export the diff since plan baseline + manifest for Claude's review |
| `forge outcome` / `forge report` | Record a completed task's outcome (rework churn + local tokens, auto-filled) and pool the dogfooding metrics: acceptance, churn, tokens, trust |
| `forge profile list/set` | Choose the stack profile that shapes the context window |
| `forge agents run` | Multi-agent scaffold: code + review per task (proposes, doesn't auto-apply) |

### Measuring the local-model gate

Forge can tell you whether the local model is actually pulling its weight, as a byproduct of the normal plan loop. After the local model implements a task, review and fix it, then record the outcome **before** you move on:

```bash
forge plan complete task-001    # the local model's work is auto-committed
# ...you review the diff and fix anything the model got wrong...
forge outcome task-001          # auto-fills rework churn + local tokens; prompts for accepted/trust/type
forge plan next                 # on to the next task
```

`forge outcome` must run before `forge plan next` touches the same files, because the working-tree delta on the task's files is what it counts as your rework. When you want the picture across a plan, or across every plan and repo, pool it:

```bash
forge report          # this plan: acceptance rate, median churn, tokens, mean trust
forge report --all    # pooled across all plans, broken down by task type
```

Acceptance rate is the "is the local model good enough" number, and rework churn is whether fixing its output eats the token savings.

## How it works

- **Index**: Tree-sitter AST chunking across 9 languages (with a line-based fallback), local embeddings via `nomic-embed-text`, a ChromaDB store with file-checksum incremental re-indexing.
- **Context**: a hybrid **CAG + RAG** window: stable always-on context (manifests, README, the Tolvi vault) plus the top semantically-relevant code chunks (hard-capped to avoid lost-in-the-middle), tuned per [stack profile](./src/forge/profiles_data).
- **Workflow**: `tasks.json` is the Claude↔Forge handoff contract; Forge validates it, tracks completion, auto-commits per task, and exports a verifiable diff.
- **Editors & tools**: Continue.dev (VS Code, primary) and Cursor against the same Ollama backend; a pre-wired, npm-verified [MCP layer](./mcp/servers.json) (git, github, jira, gcloud, firebase, context7, sequential-thinking, playwright) configured for Claude Code.

Everything runs locally. No code leaves the machine during execution. Architecture and design notes live in [`docs/`](./docs).

## License

[Apache 2.0](./LICENSE).
