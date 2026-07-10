#!/usr/bin/env bash
# install.sh — install the Forge Claude Code command.
#
# Default: symlink commands/forge.md → ~/.claude/commands/forge.md so `git pull`
# updates land automatically.
#
# Flags:
#   --copy        Deep-copy instead of symlinking (isolate from repo updates)
#   --uninstall   Remove the installed command
#   --force       Overwrite an existing install (refuses by default)
#   -h, --help    Print usage

set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SRC_DIR/commands/forge.md"
DEST_DIR="$HOME/.claude/commands"
DEST="$DEST_DIR/forge.md"

MODE="symlink"
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --copy) MODE="copy" ;;
    --uninstall) MODE="uninstall" ;;
    --force) FORCE=1 ;;
    -h|--help)
      sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown flag: $1" >&2; exit 1 ;;
  esac
  shift
done

if [[ "$MODE" == "uninstall" ]]; then
  if [[ -e "$DEST" || -L "$DEST" ]]; then
    rm "$DEST"
    echo "Removed $DEST"
  else
    echo "Nothing to remove at $DEST"
  fi
  exit 0
fi

if [[ ! -f "$SRC" ]]; then
  echo "Source command not found: $SRC" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"

if [[ -e "$DEST" || -L "$DEST" ]]; then
  if [[ "$FORCE" -eq 0 ]]; then
    echo "$DEST already exists. Pass --force to overwrite." >&2
    exit 1
  fi
  rm "$DEST"
fi

if [[ "$MODE" == "copy" ]]; then
  cp "$SRC" "$DEST"
  echo "Copied forge command → $DEST"
else
  ln -s "$SRC" "$DEST"
  echo "Linked forge command → $DEST"
fi

echo "Run /forge <TICKET-ID | Confluence URL | file path> in a Claude Code session."
