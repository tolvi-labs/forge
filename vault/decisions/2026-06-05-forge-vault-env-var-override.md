---
tags: [decision, forge]
date: 2026-06-05
repo: forge
status: active
ticket: none
user_impact: low
product_area: Vault integration
---

# FORGE_VAULT env var overrides the default vault path

**Date:** 2026-06-05
**Repo:** forge

## Why

Forge's vault loader hardcoded `<repo_root>/vault/` as the only vault source. Engineers who already use Tolvi with a standalone vault in a separate location (e.g. `~/Developer-Vault/my-project/`) had no way to point Forge at it without creating a symlink inside the repo — a fragile workaround that pollutes `.gitignore` and breaks on clone.

## How

- `load_vault()` in `src/forge/vault/loader.py` now checks `os.environ.get("FORGE_VAULT")` before constructing the default `<repo_root>/vault/` path.
- If the env var is set, it is used as the vault root directly; the repo root argument is still accepted (signature unchanged) but ignored for path resolution.
- If not set, behavior is identical to before — no change for existing users.
- The intended usage pattern is to set `FORGE_VAULT` per-project via `.envrc` (direnv) or shell profile, not globally.
- Rejected `.forge.json` per-repo config as the first-pass solution: more surface area (new file format, new schema, new config-loading code path) for what is ultimately a one-liner env var. A per-repo config is still the right long-term story for teams (so teammates get the same wiring via git), but the env var covers the solo-dev case at near-zero cost.
- No CLI flag added (`--vault-path`) — would require threading through every command that builds context; env var is the right lever for a session-scoped override.

## Outcome

Engineers with an existing Tolvi vault outside the repo can set `FORGE_VAULT=~/path/to/vault` (or in `.envrc`) and Forge will pick it up in the always-on context window without any symlinks or repo changes.
