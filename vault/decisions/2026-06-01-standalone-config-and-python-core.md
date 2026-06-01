---
tags: [decision, forge]
status: active
date: 2026-06-01
repo: forge
ticket: none
---

## TL;DR

Forge is an independent sibling of Tolvi (own repo, own ~/.config/forge namespace), built on a Python core. Rejected: nesting under Tolvi's namespace; a Go core (fights the Tree-sitter/ChromaDB ecosystem).

## Why

Forge needs the Python RAG ecosystem (Tree-sitter, ChromaDB, tiktoken) and should stand on its own while still bridging to Tolvi vaults when present.

## How

Standalone XDG config at ~/.config/forge and state at ~/.local/share/forge. Python package installed into a dedicated 3.12 venv via uv. The only coupling to Tolvi is a read-only vault bridge that consumes the public tolvi-format-v1, added in P3.

## Outcome

P1 ships the skeleton, installer, hardware detection, and `forge doctor/status` on this basis.
