---
description: "Execute a hardened plan with the local model. Usage: /forge <TICKET-ID | Confluence URL | file path> — reads the peer-reviewed TRD, portions it into local-sized tasks, runs Forge in the background, and walks you through a task-by-task review. Never commits the plan; only code."
---

You are running /forge — the hand-off from a hardened plan to local execution. A frontier model (you) already planned and hardened the work; the local model does the high-volume typing; the engineer keeps the judgment. Your job is to portion the plan so the local model can actually execute it within its context limits, drive Forge, and then force a real review. You do NOT rewrite the plan's intent here — if the plan needs re-shaping, stop and send the engineer back to /bastion.

Arguments: $ARGUMENTS

## Step 1 — Resolve the hardened TRD

The plan is peer-reviewed and lives OUTSIDE the repo. Resolve `$ARGUMENTS` in this order:

1. If empty, ask: "Which plan? Give me a JIRA ticket ID, a Confluence URL, or a path to a local plan file."
2. If it matches a ticket ID (`^[A-Z]+-\d+$`), fetch the ticket via the atlassian MCP and read the hardened plan from its attachments or description. If nothing plan-shaped is attached, say so and stop — the plan belongs on the ticket, not in the repo.
3. If it is a Confluence URL, fetch the page via the atlassian MCP.
4. If it is a filesystem path, read the file. Warn once that a local file forfeits peer review — the value of a plan is the review, so this is the solo fallback, not the norm.

## Step 2 — Confirm it is hardened

Skim the plan for signs it went through the crucible: explicit acceptance criteria, named files/systems, resolved trade-offs. If it reads like raw intent rather than a hardened plan, tell the engineer and offer to send it to /bastion first. Do not portion an unhardened plan.

## Step 3 — Portion into a local-sized manifest

This is the value of this command. Translate the plan into a schema-valid `tasks.json` where every task is small, file-scoped, and self-contained enough to fit the local model's context budget (the local window is a ceiling near 64k, but keep each task's real prompt to a few thousand tokens of *relevant* code — that is where a local coder model is fast and accurate).

- Each task declares the exact files it touches, so Forge can keep retrieval tight.
- Each task carries concrete acceptance criteria — this is what the engineer reviews against later, so make them checkable, not vague.
- Order tasks with `depends` so Forge runs them dependency-first.
- A task the local model cannot do in isolation (cross-file architecture, a judgment call) does not belong here — that is a planning gap; surface it and stop rather than handing the local model work it will fail.

Schema (Forge's `tasks.json`):

```json
{
  "tasks": [
    {
      "id": "task-001",
      "title": "Add validate_token to auth.py",
      "files": ["src/auth.py"],
      "acceptance_criteria": ["validate_token(token) returns Claims", "raises AuthError on expiry"],
      "depends": []
    }
  ]
}
```

Write `tasks.json` to Forge's data dir (`forge plan load` places it under `~/.local/share/forge/plans/`). Never write the plan or a checklist into the repo — only code lands in the repo.

## Step 4 — Execute in the background

1. `forge start` if the models are not up.
2. `forge plan load <tasks.json>`.
3. Kick off execution in the background (`forge agents run <tasks.json>`, or loop `forge plan next` / `forge plan complete <id>`), so the session stays free.
4. Tell the engineer: run `forge watch` in another pane to watch tasks land — that is the visibility surface, and because this is async batch work you can also just walk away and come back.

## Step 5 — Review, task by task

When execution finishes, run `forge verify` to get the diff and manifest, then walk the engineer through it ONE TASK AT A TIME, each task's diff against its own acceptance criteria. There is no blanket "approve everything" — the review is the load-bearing step, and a one-click approval turns Forge into the autopilot it is designed not to be. For each task, show the diff, restate the acceptance criteria, and ask the engineer to accept, reject, or fix.

## Step 6 — Capture drift, then fix

- **Drift accepted:** if the engineer accepts a change that diverges from what the plan said, that is exactly the moment to capture *why* — offer to write a vault decision (or run /tolvi-sync) recording the deviation, which may supersede the TRD. Reconciling intent against reality is the whole point of the vault; do not let the reason evaporate.
- **Fix needed:** re-trigger just that task scoped (`forge plan next` on the single task), engineer watching. Do not open an open-ended chat loop and do not re-plan mid-flight.
- **Outcome:** run `forge outcome <task_id>` per reviewed task so the dogfooding metrics (acceptance, churn, tokens, trust) are recorded.

## Guardrails

- The plan/TRD is never committed to the repo, and neither is a human checklist — `tasks.json` in the data dir is the only scaffold, and it is disposable. The durable record is the TRD (intent, external), the code (reality, repo), and vault decisions (the why of any drift).
- You portion and drive; you do not author the plan's intent and you do not merge without the engineer's task-by-task review.
