# Forge — Go-Forward Plan

**Status:** MVP complete (P1–P5). Ship is the right move — deferred until real usage data exists.
**Last updated:** 2026-07-04

## One-line

A local-first Claude → Local → Claude loop: Claude plans and verifies, a tuned local model (qwen2.5-coder via Ollama) does the bulk implementation at zero token cost and full privacy. Forge indexes the repo, assembles a hybrid CAG+RAG window, and drives a `tasks.json` plan task-by-task with auto-commits.

## Where it stands

The engineering is essentially done — phases P1–P5 shipped, the full local loop works end to end, with a test suite and CI. This is **not a build decision; it is a ship decision.** The remaining work is packaging/distribution (Homebrew / PyPI / Docker) and leaning into the Tolvi vault bridge.

## Decision: ship, but defer until there is real usage data

Shipping Forge is the right move, but we defer distribution until there is **more personal usage data**, so the launch docs, quickstart, and positioning are written from real experience rather than from the TRD. A local-model tool lives or dies on whether the local model actually clears the bar for the "80%" in day-to-day use; we should be able to speak to that from having leaned on it ourselves, not assert it. See [[2026-07-04-forge-defer-ship-until-usage-data]].

Concrete sequence:
1. **Dogfood** Forge on real product work (internal product work) and accumulate usage data — where the local model is good enough, where it isn't, what the real token savings and rework rates are.
2. **Write the docs from that experience** — honest capability boundaries, the actual 80/20 split, real setup friction on real hardware.
3. **Package and distribute** (Homebrew / PyPI / Docker) once the docs are grounded.

Forge needs a lot of testing before ship; the usage data is that testing.

## Durability note

The local model, Ollama, ChromaDB, Tree-sitter, and Continue.dev are all commodity and improving on their own — better open models are a tailwind, not a threat, but also mean anyone can assemble a similar stack. The cost/privacy wedge erodes as frontier prices fall. **The durable lever is the Tolvi vault bridge:** feeding decisions and rejected alternatives into the local model's always-on context converts Forge from "another local-model wrapper" into the execution arm of a proprietary engineering-knowledge substrate. Lean into that in the docs and the integration, not into the raw local-model pitch.

## Ecosystem role

Forge is the **local zero-token execution engine** in the composition thesis: the Tolvi vault (correctness/context) combined with Guild (scoped orchestration) supercharges Forge, so a team can do serious engineering work without paying per-token frontier-LLM cost. Forge is the layer that makes the cost savings real; the vault + Guild are what keep its output correct. See [[2026-07-04-guild-correctness-recall-reframe]].

## Open questions

- Does the local model quality clear the "80%" bar in sustained real use, or does rework eat the token savings? (This is exactly what the dogfooding period answers.)
- Distribution channel priority: Homebrew vs PyPI vs Docker first.
- How deep to wire the Tolvi bridge before ship vs. after.
