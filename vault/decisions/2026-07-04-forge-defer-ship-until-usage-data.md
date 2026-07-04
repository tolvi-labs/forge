---
tags: [decision, forge]
date: 2026-07-04
repo: forge
status: active
ticket: none
user_impact: none
product_area: Release
---

# Ship Forge — but defer until there is real personal usage data

**Date:** 2026-07-04
**Repo:** forge

## Why

Forge's MVP is complete and the local loop works end to end, so the only question is when to distribute it. A local-model developer tool is credible only if its docs speak honestly about where the local model is good enough and where it isn't — and that can only come from having leaned on it in real work. Shipping now would mean writing the quickstart and positioning from the TRD rather than from experience, which is the weakest possible launch for a tool whose entire value proposition rests on the local model clearing the "80%" bar in practice.

## How

- **Shipping Forge is endorsed as the right next move for the ecosystem** — it is a done asset generating zero return while unshipped, and it is the execution layer of the composition thesis.
- **Deferred until there is more personal usage data**, so launch docs are grounded in real experience: the actual 80/20 split, honest capability boundaries, real setup friction on real hardware, and real token-savings/rework numbers.
- **Sequence:** dogfood on real product work (internal product work) → write docs from that experience → package and distribute (Homebrew / PyPI / Docker).
- **Durability comes from the vault bridge, not the local model.** The local model, Ollama, ChromaDB, Tree-sitter, and Continue.dev are commodity and improving on their own; the cost/privacy wedge erodes as frontier prices fall. Feeding vault decisions and rejected alternatives into the model's always-on context is the durable, non-commoditizable lever — the docs and integration should lead with that.
- **Rejected: ship now on TRD-based docs.** Faster, but it launches the least-defensible framing (raw local-model cost play) with no experiential backing, on a tool that needs a lot of real-world testing first.
- **Ecosystem thesis:** the Tolvi vault (correctness) + Guild (scoped orchestration) supercharge Forge (local zero-token execution), so teams can do serious work without per-token frontier-LLM cost. See [[2026-07-04-guild-correctness-recall-reframe]].

## Outcome

Forge is committed to ship on the strength of real usage data and a vault-bridge-forward story, not on an unvalidated cost pitch — dogfooding is the gate.
