---
tags: [decision, forge]
date: 2026-08-14
repo: forge
status: active
ticket: none
user_impact: medium
product_area: Local model runtime
---

# Swap forge-coder's base model to Qwen3-Coder

**Date:** 2026-08-14
**Repo:** forge

## Why

Forge's chat/deep-reasoning model (`forge-coder`) was still built on Qwen2.5-Coder, a superseded generation. Qwen3-Coder is the current open-weight, locally-runnable coding model line from the same family and fits the same hardware this machine already targets, so staying on 2.5 meant leaving quality on the table for no reason. Autocomplete is untouched — it's latency-sensitive and no small Qwen3-Coder variant exists yet, so `qwen2.5-coder:7b` remains correct there.

## How

- `forge-coder` is a custom Ollama Modelfile (`FROM <recommended_model>` + a SYSTEM prompt + PARAMETER overrides) — rebuilding it against a new base is not automatic. `ensure_forge_coder()` in `runtime.py` only creates it if the tag doesn't already exist, so the old `forge-coder` had to be `ollama rm`'d before `forge start` would rebuild it against the new base.
- Ollama's model storage is content-addressable (blob-based, like Docker layers). `ollama create forge-coder -f <modelfile>` logged `using existing layer sha256:...` for the base weights — confirming `forge-coder` and its base tag (`qwen3-coder:30b`) share the same on-disk weight blobs. Keeping both tags installed costs no meaningful extra disk; `ollama list` reporting "18 GB" for each is not two separate 18GB files.
- New base: `qwen3-coder:30b` (30B total, ~3.3B active per token via MoE, 256K native context, ~19GB on disk). Chosen over `qwen3-coder-next` (80B total/3B active) as the default because it's closer in resource footprint to the outgoing `qwen2.5-coder:14b` and hasn't required a fresh benchmarking pass — `qwen3-coder-next` is configured as the stretch option instead.
- `max_context_tokens` deliberately left at 65536 rather than raised toward the new model's 256K ceiling — bigger context window means more RAM/compute pressure per request, and there's no immediate need driving it. Revisit if a workload actually needs more context.
- `setup/detect-hardware.sh` RAM-tier defaults updated so this isn't just a manual override on one machine: 24GB+ → `qwen3-coder:30b` (stretch `qwen3-coder-next`), 48GB+ → `qwen3-coder-next` as the default itself, 16-23GB stays on `qwen2.5-coder:14b` (no small Qwen3-Coder fit), <16GB stays on `qwen2.5-coder:7b`. This machine (32GB) lands in the 24GB+ tier, matching the manually-set `hardware-profile.json`.
- Rejected — leaving `detect-hardware.sh` untouched and treating this machine's `hardware-profile.json` as a pure manual override: rejected because rerunning setup on this exact machine would silently regenerate the stale Qwen2.5-Coder config and undo the change with no warning.
- Cleaned up unreferenced local Ollama models while auditing this (`gpt-oss:20b`, `mistral:latest`, then the now-superseded `qwen2.5-coder:14b`) — none were referenced by any config or script.

## Outcome

`forge-coder` now runs on `qwen3-coder:30b`; `forge status` confirms `Model: forge-coder (qwen3-coder:30b)`. Fresh installs on 24GB+ machines will get Qwen3-Coder by default going forward. Autocomplete and the <24GB tiers are unchanged and correctly still on Qwen2.5-Coder.
