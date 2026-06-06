---
tags: [decision, forge]
date: 2026-06-06
repo: forge
status: active
ticket: none
user_impact: medium
product_area: CLI / runtime lifecycle
---

# forge start / forge stop — runtime lifecycle commands

**Date:** 2026-06-06
**Repo:** forge

## Why
Forge needs a local Ollama server running to do anything, but there was no command to start it. The server was only ever launched once during first-time setup (`bootstrap.sh`), so after a reboot or in a fresh shell an engineer had no single command to bring Forge to a ready state. `forge start` does that and shows status in one step; `forge stop` shuts the server back down — but only if Forge was the one that started it, so it never kills an Ollama a user is running for something else.

## How
- New `src/forge/runtime.py` holds orchestration as small, independently testable functions; the CLI commands in `cli.py` are thin wrappers. Functions report progress through an `on_event: Callable[[str], None]` callback so the module has no Rich/Click dependency and tests assert on emitted events.
- `forge start` sequence: `ensure_ollama` → `ensure_models` → `ensure_forge_coder` → `_render_status()` (extracted from the existing `status` command so both share rendering). Fail-fast: any `RuntimeError` prints `✗ <msg>` and exits 1; progress already printed shows how far it got.
- `ensure_ollama`: if `/api/tags` is reachable, no-op (do NOT write a pidfile — Forge doesn't own that server). Else require the `ollama` binary, spawn `subprocess.Popen(["ollama","serve"], stdout/stderr=DEVNULL, start_new_session=True)` (detached, survives the command), write the PID to `config.data_dir()/ollama.pid`, poll reachability every 0.5s up to 15s.
- `ensure_models`: required list is **derived from the hardware profile** — `[recommended_model, autocomplete_model, embedding_model]`, order-preserving dedup, empties dropped — not hardcoded the way `bootstrap.sh` lists them. Missing models pulled via `ollama pull` with inherited stdio so the native progress bar renders in the same window. Auto-pull was chosen over warn-only so `forge start` is genuinely "ready after this," accepting a possible long first-run download.
- `ensure_forge_coder`: skip if `forge-coder` already in tags; else render `ollama/Modelfile.tmpl` via `modelfile.render_modelfile` and `ollama create`.
- `stop_ollama` ownership model: pidfile present → read PID, confirm it is alive AND is an `ollama` process via `ps -p <pid> -o comm=` before `os.kill(pid, SIGTERM)`; then remove the pidfile. A dead or reused PID (different process) is treated as a stale pidfile, cleaned up, no kill. No pidfile + server reachable → "running but not started by forge — leaving it." This is the key safety property: Forge never SIGTERMs a process it can't confirm it owns.
- Rejected: (a) foreground/blocking `ollama serve` — ties the server to the terminal window, defeats the "show status and return to prompt" goal; (b) brew/launchd service integration — more detection surface for no benefit on a single-user setup; (c) "stop any Ollama on :11434" — would kill a brew-service / desktop-app server the user expected to keep running.

## Outcome
`forge start` brings Forge to a ready state (Ollama up, models present, forge-coder built) and prints status in one terminal command; `forge stop` cleanly tears down only a Forge-started server. 20 new tests, full suite 140 passing, live smoke verified end to end.
