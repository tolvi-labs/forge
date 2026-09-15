# AGENTS.md

Guidance for coding agents working in this repo.

## What this is

Forge runs routine engineering against an on-device model that is not working blind: the Tolvi vault is held in always-on context. Correct-by-recall execution at zero per-token cost, on a machine the code never leaves.

## Build and test

```bash
pip install -e ".[dev]"
pytest
```

## Layout

- `src/forge/` is the package. `src/forge/vault/` is a read-only consumer of `tolvi-format-v2` vaults.
- `integrations/{claude-code,cursor,vscode}/` wire Forge into each host. These are per-host wiring, correctly named for the host: a slash command and installer for Claude Code, an `mcp.json` for Cursor, a `config.yaml` for VS Code. None of them is a skill.

## Conventions

- **The vault bridge is read-only.** Forge consumes vaults; it never writes them. Capture belongs to `tolvi` and `provenance`.
- **The loader does not inspect `.vault-meta.json`.** It reads the doc directories directly, which is why v2 needed no code change here. Keep it that way unless there is a reason to gate on format version.
- **Local means local.** A change that sends repository content to a hosted model defeats the entire premise.

## What not to do

- Do not rename `integrations/claude-code/` to a skills layout. It ships commands and MCP wiring, not a `SKILL.md`, and it sits correctly beside its cursor and vscode siblings.
