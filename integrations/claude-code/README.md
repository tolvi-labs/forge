# Forge: Claude Code integration

The `/forge` command hands a hardened, peer-reviewed plan to the local model for execution, then walks you through a task-by-task review of the result.

It is the batch altitude of Forge: a frontier model (Claude) plans and hardens the work, `/forge` portions that plan into local-sized tasks and runs them in the background, and you review the diff. The plan lives outside the repo (JIRA, Confluence, or a local file) where peer review happens. Only code lands in the repo.

## The loop

```
JIRA / Confluence plan → /bastion (harden) → /forge <ref> → local execute → task-by-task review
```

## Prerequisites

- [Claude Code](https://claude.ai/code) installed.
- The `forge` CLI on your `$PATH` (`bash setup/bootstrap.sh` from the repo root, or `pip install tolvi-forge`).
- Ollama running with the Forge models: `forge start`, then `forge doctor` to confirm.
- A plan attached to a JIRA ticket or Confluence page (recommended, so it is peer-reviewed), or a local plan file (solo fallback, no review).

## Install

From the root of your `tolvi-labs/forge` checkout:

```bash
cd integrations/claude-code
./install.sh
```

This symlinks `commands/forge.md` into `~/.claude/commands/forge.md`, so `git pull` updates land automatically. Pass `--copy` to deep-copy instead, or `--uninstall` to remove it.

## Usage

```
/forge PROJ-142                         # read the plan attached to this JIRA ticket
/forge https://…/wiki/…/Plan            # read a Confluence plan
/forge ./plans/feature.md               # local plan file (forfeits peer review)
```

`/forge` will refuse to portion an unhardened plan and point you back to `/bastion`. It never writes the plan or a checklist into the repo: `tasks.json` lives in Forge's data dir and is disposable.
