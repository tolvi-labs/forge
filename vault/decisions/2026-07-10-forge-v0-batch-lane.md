---
tags: [decision, forge]
date: 2026-07-10
repo: forge
status: active
ticket: none
user_impact: none
product_area: Product
---

# Forge v0: the local model's lane is async batch execution, not the keystroke line

**Date:** 2026-07-10
**Repo:** forge

## Why

The local model cannot hold a working session's context on the hardware most engineers actually have — that constraint is the entire reason for the plan/execute split, where a frontier model plans and the local model executes. It follows that the worst possible place to put the local model is the latency-critical keystroke line (IDE autocomplete): it is always-on, judged head-to-head against cloud tools like Copilot and Cursor, and when it lags at 15–25 tok/s the failure reads as "Forge is broken" even though the cause is hardware. You cannot gate hardware latency — a policy that tells a user their machine is too weak is just the brand damage delivered politely. The differentiated, defensible lane is the opposite profile: async batch execution, where slow does not read as broken because the engineer fired it and walked away.

## How

- **v0 local-model lane = async batch execution.** The motion is plan → local execute → review, run as a fire-and-report batch, never on the interactive keystroke path.
- **Two altitudes, both engineer-led.** The Continue.dev keystroke assist (in-editor autocomplete/edit, already shipped) stays installed but is opt-in and never the headline; the Forge batch loop is the v0 bet. They are two altitudes of one tool — keystroke→line vs ticket→feature — not competing paths for the same job.
- **The cycle is clean and non-iterative.** Forge executes a hardened plan; it is not a "now do this, now change that" conversation. Iteration mid-flight undoes the crucible; if a hardened plan needs re-shaping, that is a return to bastion, not a chat loop.
- **Engineer-led review is load-bearing.** The review step must resist rubber-stamping — task-by-task against each task's acceptance criteria, no blanket approve button — because the moment review becomes a rubber stamp, Forge becomes the hero-AI it exists to reject. Forge does the high-volume typing; the engineer keeps the judgment.
- **Surgical/fix edits are the local model's good case**, delivered by re-triggering a scoped task inside the Forge cycle (small context, engineer-triggered, watched), not by standing up a separate persistent editor pair-coder surface. For the tiniest edits the engineer just types them — being in the loop is not a gap to automate.
- **Rejected: autocomplete-as-headline** — hardware latency tarnishes the brand and cannot be gated, and it is the surface with the least differentiation and the most risk.
- **Rejected: a dedicated VS Code iteration surface for v0** — it reintroduces the latency surface even when engineer-triggered, splits the evidence before the core loop is proven, and is at best a data-driven v1 question. The existing return trip (review a diff, re-trigger a scoped task) already covers legitimate fixing.

## Outcome

Forge v0 puts the local model only where it is strong — async batch execution and scoped surgical re-runs — and never on the latency-critical path, which keeps the product consistent with the Tolvi thesis of keeping the engineer in the loop while the AI supercharges the labor. Whether this lane clears the bar is exactly what the dogfooding harness measures; see [[2026-07-08-measure-ship-gate-from-plan-loop]] and the ship gate in [[2026-07-04-forge-defer-ship-until-usage-data]].
