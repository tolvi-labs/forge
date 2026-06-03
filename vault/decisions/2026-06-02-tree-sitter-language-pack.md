---
tags: [decision, forge]
status: active
date: 2026-06-02
repo: forge
ticket: none
---

## TL;DR

Chunk with `tree-sitter-language-pack` (not the spec's `tree-sitter-languages`), whose bundled binding has a method-call Node API and a `str`-taking `parse()`. Rejected: `tree-sitter-languages` (effectively unmaintained, no current wheels); reimplementing grammars (NIH).

## Why

The P2 chunker needs prebuilt Tree-sitter grammars for 9 languages that install cleanly on the project's Python 3.12. The TRD named `tree-sitter-languages`, which no longer ships current wheels and is effectively unmaintained.

## How

- Swapped the dependency to `tree-sitter-language-pack` (maintained successor; prebuilt wheels for all 9 grammars on py3.12). Verified all 9 load before building anything else (fail-fast Task 1).
- Its bundled binding is **not** the classic py-tree-sitter API. Verified empirically on this host (`tree-sitter-language-pack` 1.8.1 / `tree-sitter` 0.25): `parser.parse(source)` takes a **`str`** (passing `bytes` raises `TypeError`); `tree.root_node()`, `node.kind()`, `node.named_child_count()`, `node.named_child(i)`, `node.child_by_field_name()`, `node.start_byte()`/`end_byte()`, `node.start_position()`/`end_position()` (`.row`/`.column`) are all **method calls**; there is no `node.text` — slice `source.encode()` by byte offsets.
- The chunker (`src/forge/chunker/treesitter.py`) is written against this API: parse the `str`, walk via a depth-first `_collect` that emits target-kind nodes and recurses through non-targets (so `export_statement` wrappers and json `object`→`pair` containers resolve), slice content from the UTF-8 bytes by byte offset, and read line numbers from `start_position().row + 1`.
- Pattern that paid off: the controller probed the real binding API (and the chromadb 1.x API) up front, then corrected the plan's verbatim code before dispatching implementers — avoiding a long trial-and-error loop on a non-obvious third-party API.

## Outcome

All 9 grammars chunk correctly; the chunker is pinned to a maintained library with a documented, verified binding API.
