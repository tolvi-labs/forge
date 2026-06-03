---
tags: [decision, forge]
status: active
date: 2026-06-02
repo: forge
ticket: none
---

## TL;DR

Chunk code at class/function level — one chunk per class, not per method — for the MVP index. Rejected: method-level chunking (descending into class bodies produces overlapping class+method chunks that duplicate content and complicate dedup).

## Why

Purely technical (RAG index quality). The chunk boundary determines what the local model retrieves: too coarse loses precision, too fine duplicates context and wastes the retrieval budget.

## How

- `chunker/treesitter.py` `_collect` emits a target node (function/class/component/interface/rule-set/element/pair) and does **not** descend into it. A class therefore becomes one chunk including its methods.
- Consequence: `method_definition`/`method_declaration` node kinds are unreachable inside a class with the stop-at-target strategy, so they were removed from the `_CHUNK_NODES` maps (they were dead config that implied method-level support the chunker doesn't deliver). The `refactor(chunker)` commit documents this.
- Rejected — method-level chunking: would require descending into class bodies and emitting methods alongside the class. That yields overlapping chunks (the class chunk's text contains each method's text), duplicating content in the vector store, inflating embedding cost, and polluting retrieval with near-duplicate hits. Not worth the complexity for the MVP; whole-class context is coherent for a 14b model.
- Known limitation: a very large class is a single large chunk. Method-level (or hybrid) chunking with overlap handling is a deferred refinement if retrieval precision on large classes proves insufficient.

## Outcome

The index holds non-overlapping class/function-level chunks; node-type maps honestly reflect that granularity.
