---
description: "Execute a hardened plan with the local model. Usage: /forge <TICKET-ID | Confluence URL | file path | Magellan tasks.json>: reads the peer-reviewed TRD (or loads a Magellan tasks.json as is), portions it into local-sized tasks, runs Forge in the background, and walks you through a task-by-task review. Never commits the plan; only code."
---

You are running /forge, the hand-off from a hardened plan to local execution. A frontier model (you) already planned and hardened the work; the local model does the high-volume typing; the engineer keeps the judgment. Your job is to portion the plan so the local model can actually execute it within its context limits, drive Forge, and then force a real review. You do NOT rewrite the plan's intent here: if the plan needs re-shaping, stop and send the engineer back to /tolvi-bastion.

Arguments: $ARGUMENTS

## Step 1: Resolve the hardened TRD

The plan is peer-reviewed and lives OUTSIDE the repo. Resolve `$ARGUMENTS` in this order:

1. If empty, ask: "Which plan? Give me a JIRA ticket ID, a Confluence URL, a path to a local plan file, or a Magellan tasks.json."
2. If it is a Magellan `tasks.json` (a path ending in `-tasks.json`, typically `docs/superpowers/plans/YYYY-MM-DD-<feature>-tasks.json`, whose tasks carry `context`), it is already hardened and portioned: skip Steps 2 and 3 and go straight to Step 4, loading that file as is.
3. If it matches a ticket ID (`^[A-Z]+-\d+$`), fetch the ticket via the atlassian MCP and read the hardened plan from its attachments or description. If nothing plan-shaped is attached, say so and stop: the plan belongs on the ticket, not in the repo.
4. If it is a Confluence URL, fetch the page via the atlassian MCP.
5. If it is a filesystem path, read the file. Warn once that a local file forfeits peer review: the value of a plan is the review, so this is the solo fallback, not the norm.

## Step 2: Confirm it is hardened

Skim the plan for signs it went through the crucible: explicit acceptance criteria, named files/systems, resolved trade-offs. If it reads like raw intent rather than a hardened plan, tell the engineer and offer to send it to /tolvi-bastion first. Do not portion an unhardened plan. Once it is hardened, `/tolvi-magellan <brief>` is the preferred compile step: it emits a Forge-compatible `tasks.json` with per-task context, which you can load directly in Step 4 instead of portioning by hand in Step 3.

## Step 3: Portion into a local-sized manifest

This is the value of this command. Translate the plan into a schema-valid `tasks.json` where every task is small, file-scoped, and self-contained enough to fit the local model's context budget (the budget depends on the machine's tier: it is the smaller of the stack profile's and the hardware's context window, less a reply reserve, and a task whose files alone exceed it is rejected; keep each task's real prompt to a few thousand tokens of *relevant* code, which is where a local coder model is fast and accurate).

- Each task declares the exact files it touches, so Forge can keep retrieval tight.
- Each task carries concrete acceptance criteria: this is what the engineer reviews against later, so make them checkable, not vague.
- Order tasks with `dependencies` so Forge runs them dependency-first.
- A task the local model cannot do in isolation (cross-file architecture, a judgment call) does not belong here: that is a planning gap; surface it and stop rather than handing the local model work it will fail.

Schema (Forge's `tasks.json`; `feature` and `tasks` are required, `stack` and each task's `context` are optional):

```json
{
  "feature": "token-validation",
  "stack": "python-backend",
  "tasks": [
    {
      "id": "task-001",
      "title": "Add validate_token to auth.py",
      "files": ["src/auth.py"],
      "acceptance_criteria": ["validate_token(token) returns Claims", "raises AuthError on expiry"],
      "dependencies": [],
      "context": {
        "decisions": [{"path": "vault/decisions/2026-01-10-jwt-claims.md", "title": "Validate JWT claims locally", "rationale": "Avoid a network hop per request"}],
        "refs": [{"file": "src/auth.py", "line": 42, "symbol": "decode_token"}],
        "interfaces": {"consumes": ["decode_token(token) -> dict"], "produces": ["validate_token(token) -> Claims"]}
      }
    }
  ]
}
```

Write `tasks.json` to Forge's data dir (`forge plan load` places it under `~/.local/share/forge/plans/`). Never write the plan or a checklist into the repo: only code lands in the repo.

## Step 4: Execute in the background

1. `forge start` if the models are not up.
2. `forge plan load <tasks.json> --path <repo>` from a clean working tree.
3. Kick off execution in the background with `forge agents run --apply --path <repo> --json`, so the session stays free. Forge commits each approved task as `[id] title` on a `forge/<feature>` branch; rejected tasks, and tasks that depend on them, are left uncommitted and listed with the reason.
4. Tell the engineer: run `forge watch` in another pane to watch tasks land. That is the visibility surface, and because this is async batch work you can also just walk away and come back.

## Step 5: Review, task by task

When execution finishes, run `forge verify` (or `git log`/`git diff` on the `forge/<feature>` branch) to get the diff and manifest, then walk the engineer through it ONE TASK AT A TIME, each task's diff against its own acceptance criteria. There is no blanket "approve everything": the review is the load-bearing step, and a one-click approval turns Forge into the autopilot it is designed not to be. For each task, show the diff, restate the acceptance criteria, and ask the engineer to accept, reject, or fix.

## Step 6: Capture drift, then fix

- **Drift accepted:** if the engineer accepts a change that diverges from what the plan said, that is exactly the moment to capture *why*: offer to write a vault decision (or run /tolvi-sync) recording the deviation, which may supersede the TRD. Reconciling intent against reality is the whole point of the vault; do not let the reason evaporate.
- **Fix needed:** fix it on the branch and commit, or rerun `forge agents run --apply --path <repo>` on the branch to retry rejected and skipped tasks, engineer watching. Do not open an open-ended chat loop and do not re-plan mid-flight.
- **Outcome:** run `forge outcome <task_id>` per reviewed applied task so the dogfooding metrics (acceptance, churn, tokens, trust) are recorded. Rejected tasks are recorded automatically.

## Guardrails

- The plan/TRD is never committed to the repo, and neither is a human checklist: `tasks.json` in the data dir (or Magellan's gitignored plan file) is the only scaffold, and it is disposable. The durable record is the TRD (intent, external), the code (reality, repo), and vault decisions (the why of any drift).
- You portion and drive; you do not author the plan's intent and you do not merge without the engineer's task-by-task review.
