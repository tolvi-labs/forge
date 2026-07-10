---
tags: [decision, forge]
date: 2026-07-10
repo: forge
status: active
ticket: none
user_impact: none
product_area: Process
---

# Plans live external and uncommitted; the repo keeps code and durable decisions

**Date:** 2026-07-10
**Repo:** forge

## Why

We caught a contradiction: implementation plans and design specs have been committed to `docs/superpowers/` in every repo since day one, yet a plan's real value is peer review *before* any code exists. Committing the peer-review artifact buries it where no one reviews it and ties pre-code intent to a codebase that does not exist yet. Compounding it, capturing every execution artifact bloats the repo with documents that were true for one week and misleading forever after — the exact "repo full of docs that serve no purpose beyond a specific timeframe" we want to avoid.

## How

- **Two artifacts at two altitudes.** The TRD is verbose, spans systems and repos, is peer-reviewed, and is hardened through the bastion crucible. The implementation checklist is focused, single-repo, and is an execution scaffold derived from the TRD.
- **The TRD lives external and uncommitted** — attached to the JIRA ticket, or a Confluence page, or (solo fallback, which forfeits the peer review that is the whole point) a local file. It is the canonical statement of intent; a checklist that drifts loses to it unless a recorded decision overrides it.
- **The implementation checklist is not committed.** Its value ends when execution does, and `tasks.json` in Forge's data dir already is that scaffold. Intent lives in the TRD, reality lives in the code plus git history — Forge auto-commits each task as `[task_id] title`, so `git log` reconstructs the task list and maps each to its diff — so a committed checklist only duplicates the TRD and rots as the code moves past it.
- **Drift is captured, not erased.** Where the code diverges from the TRD, that divergence becomes a vault decision explaining why, and that decision can supersede the TRD. Reconciling intent against reality is Tolvi's reason to exist; the durable record is TRD (intent) + code (reality) + vault decisions (the why of the delta). The task-by-task review step is the drift-detection moment, and it is another reason review stays engineer-led — only the engineer knows why they accepted the drift.
- **The general test: commit an artifact only if it outlives the work that produced it.** Ephemeral scaffolds go to the data dir; durable "why" goes to the vault; peer-reviewed intent lives external. This rule prevents the bloat every time, not just here.
- **Rejected: committing plans/checklists as historical record** — that is the vault decision's job, done better and more durably than a static snapshot.
- **Rejected: purging the 14 already-committed plans/specs** — they are the checklist tier and harmless legacy; the change is forward-looking, not a cleanup.

## Outcome

Repos keep code plus durable vault decisions; pre-code intent is peer-reviewed where review actually happens; and a single test — does it outlive the work? — keeps the repo from accreting stale documents. This changes the superpowers authoring convention across every repo, so rewiring the superpowers skills to stop emitting repo plans is a separate follow-up, and this decision is a candidate for promotion to the `ta-ai-tooling` vault. See [[2026-07-10-forge-v0-batch-lane]].
