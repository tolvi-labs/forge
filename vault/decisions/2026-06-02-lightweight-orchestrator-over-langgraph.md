---
tags: [decision, forge]
status: active
date: 2026-06-02
repo: forge
ticket: none
---

## TL;DR

The P5 multi-agent scaffold is a plain-Python orchestrator that proposes per-task changes for review; it does not auto-apply model output, and LangGraph is deferred until branching/retry/parallel graphs are actually needed. Rejected: adding LangGraph/CrewAI now (heavy dep for a scaffold); auto-applying + auto-committing model-written code (unsafe, defeats the verify step).

## Why

The spec names LangGraph/CrewAI for multi-agent orchestration. For the MVP "scaffold," a full graph framework is weight without payoff, and auto-applying code the local model writes is exactly the risk the Claude→Local→Claude design exists to contain.

## How

- `agents/orchestrator.run_manifest(manifest, generate_fn=...)` walks a tasks.json in dependency order (reusing `plan.manifest.next_task`), runs each task through a Code agent then a Review agent (role prompts in `agents/roles.py`), and returns a list of `TaskResult(task_id, title, proposal, review)`.
- **Proposes, does not apply.** Nothing in `agents/` writes files, runs git, or shells out — verified by grep. Applying a proposal stays a human/Claude decision, consistent with the verify stage. `forge agents run` prints proposals + reviews with a "review before applying" caveat.
- `generate_fn` is injectable (defaults to `llm.generate`), so the whole layer tests offline.
- Cyclic/blocked manifests stop cleanly (returns the tasks it could unblock; no hang).
- Rejected — LangGraph/CrewAI now: a dependency-ordered code→review pass needs no graph engine. LangGraph earns its keep once we want conditional branching (retry on REQUEST_CHANGES), parallel agents, or a Test/Git agent in the loop — a clean future swap behind `run_manifest`.
- Rejected — auto-apply + auto-commit of model output: the local 14b model's output must be reviewed before it touches the tree; auto-applying would make `forge verify` meaningless.

## Outcome

Forge ships a testable, safe multi-agent scaffold with zero new dependencies; richer orchestration (LangGraph) is a documented, isolated future addition.
