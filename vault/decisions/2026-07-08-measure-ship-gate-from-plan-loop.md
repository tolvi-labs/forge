---
tags: [decision, forge]
date: 2026-07-08
repo: forge
status: active
ticket: none
user_impact: none
product_area: Release
---

# Measure the ship gate as a byproduct of the plan loop

**Date:** 2026-07-08
**Repo:** forge

## Why

Forge's ship decision hinges on whether the local model is actually good enough in sustained real work, and that question can only be answered with usage data rather than assertion — so the dogfooding period needs to produce hard numbers, not impressions. Making the operator tally acceptance and rework by hand would guarantee the data never gets collected, so the measurement has to fall out of the normal work loop with near-zero extra effort. This is the instrument that turns the deferred-ship gate in [[2026-07-04-forge-defer-ship-until-usage-data]] into something decidable.

## How

- **Four operational metrics stand in for the vague "80% bar":** acceptance rate (share of tasks shipped with at most trivial edits — the 80% number), rework churn (lines changed on top of the local output ÷ lines it produced — the "does rework eat the savings" signal), local-token economics (tokens generated at zero cost, with throughput), and a subjective 1–5 trust score.
- **Objective fields are computed post-hoc from artifacts Forge already writes**, so nothing in the `llm.py` / `generate()` call path changes. `plan complete` auto-commits each task as `[task_id] title`, so `produced_lines` is the insertions in that commit and `rework_lines` is the git-numstat delta between that commit and the working tree, both restricted to the task's declared files.
- **Local tokens are attributed by a git-DAG timestamp window, not by threading a task id through the model call.** `inference.log` records carry a UTC `ts`; the window for a task is `commit_time(parent) < ts <= commit_time(commit)`, where the parent is the previous task's commit or the plan baseline. Zero plumbing, at the cost of cross-attribution if two plans run against one Ollama at once — surfaced as a caveat in the `--all` report rather than hidden.
- **Subjective fields are captured by an interactive `forge outcome <task_id>`** that echoes the auto-filled numbers then prompts for accepted/trust/type/failure_reason and appends one line to `outcomes.jsonl`; `forge report [--all]` pools the records (per plan, or across every plan and repo via the shared data dir) into the metrics with a per-type breakdown and a failure-reason tally.
- **Rejected: stamping the active task id into every inference-log record.** More correct under concurrency, but it requires a current-task pointer and threading the id through the chat → answer → generate path; not worth it for a single-operator sequential dogfooding period.
- **Rejected: a `--json` export, charts, and new `tasks.json` schema fields.** YAGNI for the gate; `--json` is a trivial add later if the launch docs need machine-readable numbers. Task `type` is captured as an `outcome` prompt instead of extending the manifest schema.
- **Known limitation:** rework is measured against the working tree, so `forge outcome` must run after reviewing/fixing a task and before `plan next` mutates the same files — enforced by workflow ordering and documented in the command's help.

## Outcome

The dogfooding loop can emit acceptance, churn, token, and trust numbers per task and pooled across the whole period without manual bookkeeping, so the ship gate becomes a measured threshold instead of a judgment call; the harness itself is mid-build (outcomes IO and metric computation landed, the CLI commands pending).
