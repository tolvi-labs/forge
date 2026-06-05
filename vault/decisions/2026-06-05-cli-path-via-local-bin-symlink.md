---
tags: [decision, forge]
date: 2026-06-05
repo: forge
status: active
ticket: none
user_impact: medium
product_area: Developer setup
---

# CLI made available on PATH via ~/.local/bin symlink

**Date:** 2026-06-05
**Repo:** forge

## Why

`bootstrap.sh` installed the CLI into a project-local Python 3.12 venv but did not put it on `PATH`. After running bootstrap, `forge` was `command not found` in any new terminal — users had to manually run `source .venv/bin/activate` before every session. This contradicts the README's quickstart, which shows `forge index .` as an immediate post-install step.

## How

- Bootstrap creates `~/.local/bin/` (XDG standard user bin dir) if absent, then runs `ln -sf "$REPO_DIR/.venv/bin/forge" "$HOME/.local/bin/forge"`.
- If `~/.local/bin` is not already referenced in the user's shell profile (`.zshrc` for zsh, `.bashrc` for bash), bootstrap appends `export PATH="$HOME/.local/bin:$PATH"` to it.
- `/usr/local/bin` was the first candidate but does not exist on Apple Silicon Macs (Homebrew uses `/opt/homebrew/bin`); `/opt/homebrew/bin` was rejected as the wrong convention for non-Homebrew-managed binaries. `~/.local/bin` is the correct XDG location and is already present on most Linux distros out of the box.
- Bootstrap summary message changed from "activate with `source …/activate`" to just `forge status` — the expected post-install command.
- `uv tool install` was considered (would handle PATH automatically via `~/.local/bin` on modern uv) but would require restructuring the install step away from an editable project-local venv, which is load-bearing for development workflow. Deferred.

## Outcome

After bootstrap completes and a new terminal is opened (or `source ~/.zshrc` is run), `forge` is available directly on PATH with no venv activation required.
