---
tags: [decision, forge]
date: 2026-06-05
repo: forge
status: active
ticket: none
user_impact: low
product_area: Developer tooling / forge watch
---

# forge watch: poll-based Rich TUI with auto-discovery and tab navigation

**Date:** 2026-06-05
**Repo:** forge

## Why

Engineers running `forge plan` in a terminal have no visibility into what the loop is doing — whether it is executing tasks, verifying diffs, or idle — without staring at CLI output. A live dashboard showing phase, task progress, and inference throughput makes the loop transparent without requiring any changes to the running CLI process.

## How

- **No process coupling.** `forge watch` reads the three state files written during normal `forge ask`/`forge plan` operation (`phase.json`, `manifest.json`/`state.json` for task progress, `inference.log` for inference metrics, `context/{hash}.json` for token fill). The watcher can start before or after the plan loop; no IPC, no daemon mode, no pid file.
- **Display: stacked-dashboard layout.** Three Rich panels rendered via `console.Group`: phase header (coloured by state), task list table (✓/→/· per task), metrics footer (tok/s + context fill bar). Tab bar appears only when 2+ repos are active, with "← / →" navigation hint.
- **Phase colour mapping:** executing → blue, verifying → yellow, done → green, idle/absent → dim.
- **Auto-discovery.** No arguments required. `discover_repos(data_dir)` scans `~/.local/share/forge/plans/` for subdirs containing `phase.json`, reads their `manifest.json` for the human-readable `feature` label, and returns them sorted alphabetically. Re-runs each poll tick so new plans appear automatically.
- **Idle state.** When no plans are found, shows `○ IDLE` and "no active plan — run forge plan to start". Stays running until Ctrl-C.
- **Done state.** Plans in `phase="done"` remain visible (green `✓ DONE`) until Ctrl-C.
- **Keyboard input.** `KeyboardHandler` is a daemon `threading.Thread` that puts stdin in raw mode via `termios`/`tty`. Uses `select.select` with 0.1s timeout to poll without blocking. Handles `\x03` (Ctrl-C → stop), ESC `[` C/D (right/left arrow → tab navigation mod n), and digits 1–9 (direct tab jump, 0-indexed).
- **Non-TTY degradation.** `termios.tcgetattr` raises `termios.error` when stdin is a pipe or redirect. `_run()` catches this at startup, sets `_stop`, and returns — the dashboard renders headless with no keyboard navigation.
- **Thread safety.** `threading.Lock` protects shared `_idx` and `_tab_count`. All read-modify-write operations on those fields in both the main thread (`update_tab_count`) and keyboard thread (arrow/digit handling) are lock-guarded.
- **Terminal restoration.** `termios.tcgetattr` is captured before `tty.setraw`. The `finally` block in `_run` always calls `termios.tcsetattr(fd, TCSADRAIN, old)` regardless of how the thread exits.
- **Poll interval.** 0.5s in the main loop. Keyboard thread polls at 0.1s via `select` timeout, so key responsiveness is not bottlenecked by the main loop sleep.
- **`inference.log` is intentionally global.** One Ollama instance runs per machine; all plan tabs share the same last-inference entry. Noted in code with an inline comment.
- **Rejected alternatives:**
  - Textual framework — adds a heavy dependency and a new component model; Rich `Live` + thread is sufficient for a 3-panel read-only display
  - inotify/FSEvents file watching — adds platform-specific dependency for marginal latency improvement; 0.5s polling is imperceptible at human scale
  - Subprocess/socket coupling — requires the CLI to run as a daemon, contradicting local-first one-shot design

## Outcome

`forge watch` renders a live stacked-dashboard TUI by polling five files in `~/.local/share/forge/`; tab navigation works for multi-repo sessions; the keyboard thread exits cleanly and always restores the terminal via `termios.tcsetattr` in a `finally` block; 118 tests pass (20 new unit tests covering the data layer and display builder).
