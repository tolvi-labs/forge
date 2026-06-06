---
tags: [decision, forge]
date: 2026-06-06
repo: forge
status: active
ticket: none
user_impact: medium
product_area: Model persona / Modelfile
---

# Tolvi personality in the forge-coder Modelfile

**Date:** 2026-06-06
**Repo:** forge

## Why
Forge's local model previously spoke as a generic "expert software engineer." Giving it a named persona — Tolvi, the brain inside Forge — ties the assistant's voice to the product's premise: that the reasoning behind engineering decisions is captured with the repo and queryable. The persona sets tone and behavior (direct, accurate over fast, flags risks, has opinions but updates on real pushback) so responses feel consistent and purposeful rather than generic-AI.

## How
- Replaced the `SYSTEM """..."""` block in `ollama/Modelfile.tmpl` with the Tolvi personality text. Each paragraph is written as one continuous line (per the prose convention — no mid-sentence breaks), with blank lines only between stanzas.
- Kept the prior operational directives rather than dropping them: appended a "Working rules:" tail covering tasks.json dependency ordering, treating the vault context block as authoritative, never hallucinating APIs/signatures/versions, and the React/TS/Tailwind frontend defaults. These wire into Forge's plan/vault features, so losing them would have quietly regressed behavior. Decision was personality-leads-voice, operational-rules-preserved (chosen over a clean full-replace that would have dropped them).
- The template already flows through both setup paths — `setup/bootstrap.sh` and `runtime.ensure_forge_coder` (`ollama create forge-coder`) — so no new wiring was needed; a fresh bootstrap or `forge start` builds Tolvi automatically.
- Added `tests/unit/test_modelfile.py::test_real_template_carries_tolvi_personality_and_rules` rendering the real template and asserting both the Tolvi identity and the operational rules survive, with no unrendered `{{ }}`.
- Known limitation: an already-created `forge-coder` does NOT pick up template changes on a plain `forge start` (creation is skipped when the model exists). The live model was recreated manually this session and verified via `ollama show --system forge-coder`. A `--rebuild-model` path is deferred (see session Left open).

## Outcome
`forge-coder` now answers as Tolvi with the intended tone while retaining all prior operational behavior; the persona is guarded by a test and built automatically on any fresh setup.
