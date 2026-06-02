---
tags: [decision, forge]
status: active
date: 2026-06-02
repo: forge
ticket: none
---

## TL;DR

Forge consumes a repo's Tolvi vault as a read-only, format-only CAG layer (the substrate that makes it work best), never importing Tolvi code and auto-no-opping when no vault exists. Rejected: importing the Tolvi SDK/CLI (couples the two products); making the vault required (Forge must run standalone).

## Why

Forge codes better when the local model knows *why* the codebase is the way it is — the decisions and rejected alternatives a team already records in a Tolvi vault. But Forge and Tolvi are separate products under one umbrella, and Forge must run fully standalone for users who don't keep a vault.

## How

- `src/forge/vault/loader.py` `load_vault(repo_root, max_tokens=6000)` walks `<repo>/vault/` (tolvi-format-v1): `decisions/*.md` newest-first, then `patterns/*.md` alphabetical.
- Couples to the **format only** — no Tolvi package is imported. The contract is `tolvi-format-v1` (frontmatter + `## TL;DR` + body), which is public.
- Applies the default-retrieval status filter (excludes `superseded`/`deprecated`/`draft`), case-insensitively and tolerant of inline `# comments` and a leading blank line / BOM — a capitalized `Superseded` must not leak a rejected decision into context as if authoritative.
- Prefers each doc's `## TL;DR` over the full body to keep the block dense, and budgets the whole block by tokens (per-profile, default 6k).
- Returns `None` when no `vault/` exists (or nothing survives the filter/budget); the assembler simply omits the section. This is the "substrate, not dependency" guarantee.
- The chat path (`_gather_cag`) appends the vault block alongside README/manifests as CAG, and de-dups any of those files out of the RAG hits so content isn't included twice.

## Outcome

P3A ships the bridge: a repo with a Tolvi vault feeds its decisions into every `forge chat` turn; a repo without one is unaffected. No code coupling between the two products.
