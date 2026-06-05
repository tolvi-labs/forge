---
tags: [decision, forge]
date: 2026-06-05
repo: forge
status: active
ticket: none
user_impact: low
product_area: Developer tooling / forge watch
---

# Watch state: three artifact files for TUI consumption

**Date:** 2026-06-05
**Repo:** forge

## Why

A planned `forge watch` TUI needs to display loop phase (planning/executing/verifying), inference throughput, and context fill. None of this state was persisted — the loop was entirely in the developer's head, inference metadata was discarded, and token counts were computed in memory and thrown away. Without on-disk state, the TUI would need to poll or hook into the running process, coupling it tightly to the CLI's execution model.

## How

Three artifacts written to `~/.local/share/forge/` (the XDG data dir):

**`plans/{repo_hash}/phase.json`** — loop phase marker:
- `load_plan()` writes `{"phase": "executing"}` after initialising the plan
- `verify()` writes `{"phase": "verifying"}` unless phase is already `"done"` (guard prevents clobbering a completed plan)
- `plan_complete` CLI command writes `{"phase": "done"}` when `done == len(manifest.tasks)`
- `read_phase(plan_dir)` returns the current string or `None` if absent

**`inference.log`** — global JSONL append log, one line per `generate()` call:
- `generate()` gained an optional `stats_callback: Callable[[dict], None] | None = None` parameter
- When set, it extracts `eval_count`, `eval_duration`, `prompt_eval_count`, `prompt_eval_duration` from the Ollama `/api/generate` response (already present in the payload, previously discarded) and calls the callback with `{model, tokens_out, tokens_in, tokens_per_sec, duration_ms}`
- `_make_inference_logger(log_path)` in `cli.py` returns a closure that appends a UTC-timestamped JSON line; parent dir is created at closure construction time, not on every write
- `_answer()` wires this logger to `config.data_dir() / "inference.log"`

**`context/{repo_hash}.json`** — last-assembled context fill per repo:
- `_write_context_stats(path, *, tokens_used, tokens_budget)` helper writes `{"tokens_used": N, "tokens_budget": N}`
- Called in `_answer()` after `assemble()`, before `generate()`; overwrites on each call (consumers want current fill, not history)

**Rejected alternatives:**
- Process polling / pid file — couples TUI to process lifetime; breaks when CLI exits between turns
- SQLite state store — generality overkill for three small files; adds a runtime dependency
- In-memory state shared via socket — requires the CLI to run as a daemon; contradicts local-first, one-shot design
- Stats logging inside `generate()` directly (no callback) — would require importing `config` into `llm.py`, coupling a pure HTTP wrapper to filesystem paths; callback keeps `llm.py` infrastructure-free and trivially testable

## Outcome

Three files are written to `~/.local/share/forge/` during normal CLI operation; a future `forge watch` command can poll or `inotify`-watch them to display loop phase, tokens/sec, and context fill without any process coupling.
