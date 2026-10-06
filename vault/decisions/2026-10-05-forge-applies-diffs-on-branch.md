---
tags: [decision, forge]
date: 2026-10-05
repo: forge
status: active
ticket: none
negotiable: true
user_impact: high
product_area: Batch execution
supersedes_in_part: [2026-06-02-lightweight-orchestrator-over-langgraph, 2026-07-08-measure-ship-gate-from-plan-loop]
---

# Forge applies reviewed local-model edits on a dedicated branch

**Date:** 2026-10-05
**Repo:** forge

## TL;DR

`forge agents run --apply` gives the local model real file contents and the plan's per-task context, has it answer with SEARCH/REPLACE blocks that Forge applies itself, and commits each scoped, reviewer-approved change as `[id] title` on a `forge/<feature-slug>` branch. Rejected: model-written unified diffs, applying without committing, truncating files to fit, loose patch matching, and a fresh branch per run.

## Why

Forge's batch loop only printed proposals, so the local model never did the job Forge exists for, which is replacing a frontier model on routine coding. The model also wrote blind: it received task titles and file names but no file contents, and the per-task context a compiled plan carries was dropped before it reached the model.

## How

- **Command:** `forge agents run --apply --path <repo> [--json]` runs against a plan already loaded for the target repo; without `--apply`, `agents run` behaves as before.
- **Branch:** the first run requires a clean tree (`git status --porcelain` empty, ignored files allowed) and creates and checks out `forge/<feature-slug>` from the plan baseline. A rerun while on that branch resumes, running only tasks that are not completed and committing on top, so fixes made on the branch are kept and visible to the model. If the branch exists and another branch is checked out, the command errors rather than switching or overwriting.
- **Prompt, in priority order:** diff instructions, the task and acceptance criteria, and the full current contents of each task file (empty for new files) are never trimmed; then the task's `context` (interfaces, decisions, refs); then RAG hits only if the repo is indexed. Trimming drops RAG first, then context from the end.
- **Budget:** `min(stack profile max_context_tokens, hardware num_ctx)` minus a reply reserve (default 8K) and a tokenizer margin (default 10%), both stack-profile settings so they can be calibrated. A task whose fixed part does not fit is rejected, because Ollama silently truncates an over-long prompt from the start, which is where the instructions are.
- **Edit format:** the model answers with per-file SEARCH/REPLACE blocks (an empty SEARCH creates a file). Forge applies them itself: each SEARCH must match exactly one place, first verbatim, then with leading and trailing whitespace ignored per line but the same lines in the same order, so tolerance never moves where an edit lands. Forge writes the result and generates the real unified diff with git.
- **Gate:** an edit is accepted only if every block matches, it touches only the task's `files`, and the reviewer returns APPROVE on the git-generated diff. Any failure gets exactly one retry with the error or the review fed back, then the task's files are restored and the task is rejected. A rejection skips its transitive dependents; independent tasks continue.
- **Commit:** each accepted task is committed on the branch as `[<id>] <title>` and marked completed. Rejected and skipped tasks get no commit. Deleting the branch undoes a run.
- **Results:** `results.json` in the plan dir and the same payload on stdout with `--json`, per task: applied, rejected or skipped, reason, reviewer verdict, diff stat, and whether the edit matched verbatim or only with whitespace tolerance. Every model call is logged to `inference.log`, as `chat` does.
- **Manifest:** `TASKS_SCHEMA`, `Task`, and the plan snapshot carry an optional per-task `context`; older manifests still load.
- **`plan complete <id>`** stages only that task's `files` rather than `git add -A`, and reports changed files that belong to no task.
- **Outcomes:** for `--apply` runs, rework is measured from the branch's last model commit, so the model's own later edits never count as human rework; rework on a file shared by several tasks is attributed to the last task that edited it, and the overlap is flagged. Rejected tasks are recorded automatically as not accepted with the failure reason. Hand-run plans are measured as before.
- **Rejected: applying to the working tree without committing.** A branch gives free undo, and per-task commits are exactly what the existing outcome metrics already measure.
- **Rejected: an unreferenced git tree snapshot of the model's output.** A commit captures the same thing without being subject to garbage collection.
- **Rejected: having the model write unified diffs.** Tried first and measured on 2026-10-05: `qwen3-coder:30b` wrote correct code but marked new lines as context and left blank context lines empty, so `git apply` (strict or with `--recount --ignore-whitespace`) failed on 3 of 3 edits to an existing file, while new files succeeded 3 of 3. With SEARCH/REPLACE blocks the same plan applied 3 of 3 tasks on the first attempt.
- **Rejected: loose matching (reduced patch context, three-way merges, fuzzy search).** It can land an edit silently in the wrong place, which is the hardest failure to spot in review.
- **Rejected: truncating file contents to fit the budget.** It re-creates writing against code the model cannot see.
- **Rejected: a fresh branch per run.** Fixes and successful tasks would scatter across branches.

## Outcome

Forge's batch loop edits the target repo on an isolated branch with checked, scoped, reviewed changes, and the outcome metrics separate what the model wrote from what a human fixed.
