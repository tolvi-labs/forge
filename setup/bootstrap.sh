#!/usr/bin/env bash
# Forge — bootstrap.sh : one-command setup
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/forge"

echo "⚒️  Forge — local AI dev environment"
echo "────────────────────────────────────"

# 1. Hardware detection
echo "Step 1/7 — Detecting hardware..."
bash "$REPO_DIR/setup/detect-hardware.sh"
PROFILE="$CONFIG_DIR/hardware-profile.json"
RECOMMENDED_MODEL=$(grep '"recommended_model"' "$PROFILE" | sed 's/.*: "\(.*\)".*/\1/')
MAX_CONTEXT=$(grep '"max_context_tokens"' "$PROFILE" | sed 's/[^0-9]//g')

# 2. Ollama
echo "Step 2/7 — Checking Ollama..."
if ! command -v ollama &>/dev/null; then
  if [[ "$(uname -s)" == "Darwin" ]] && command -v brew &>/dev/null; then
    brew install ollama
  else
    echo "   Install Ollama manually: https://ollama.com/download" >&2; exit 1
  fi
fi
if ! ollama list &>/dev/null; then
  ollama serve &>/dev/null & sleep 3
fi

# 3. Models
echo "Step 3/7 — Pulling models (may take a while)..."
ollama pull "$RECOMMENDED_MODEL"
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text

# 4. forge-coder Modelfile
echo "Step 4/7 — Building forge-coder..."
RENDERED="$CONFIG_DIR/Modelfile"
sed -e "s|{{RECOMMENDED_MODEL}}|$RECOMMENDED_MODEL|g" \
    -e "s|{{MAX_CONTEXT}}|$MAX_CONTEXT|g" \
    "$REPO_DIR/ollama/Modelfile.tmpl" > "$RENDERED"
ollama create forge-coder -f "$RENDERED"

# 5. Python env (dedicated 3.12 venv — system Python is 3.14)
echo "Step 5/7 — Installing Forge CLI into a Python 3.12 venv..."
if ! command -v uv &>/dev/null; then
  if [[ "$(uname -s)" == "Darwin" ]] && command -v brew &>/dev/null; then
    brew install uv
  else
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  fi
fi
uv venv --python 3.12 "$REPO_DIR/.venv"
# shellcheck disable=SC1091
source "$REPO_DIR/.venv/bin/activate"
uv pip install -e "$REPO_DIR"
mkdir -p "$HOME/.local/bin"
ln -sf "$REPO_DIR/.venv/bin/forge" "$HOME/.local/bin/forge"
echo "   forge -> $HOME/.local/bin/forge"
# Add ~/.local/bin to PATH in shell profile if not already present
SHELL_RC="$HOME/.zshrc"
if [[ "$(basename "$SHELL")" == "bash" ]]; then SHELL_RC="$HOME/.bashrc"; fi
if ! grep -q 'local/bin' "$SHELL_RC" 2>/dev/null; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
  echo "   Added ~/.local/bin to PATH in $SHELL_RC (restart shell or: source $SHELL_RC)"
fi

# 6. Editor + MCP configs
echo "Step 6/7 — Installing editor + MCP configs..."
mkdir -p "$HOME/.continue" "$CONFIG_DIR/mcp"
cp "$REPO_DIR/integrations/vscode/config.yaml" "$HOME/.continue/config.yaml"
cp "$REPO_DIR/mcp/servers.json" "$CONFIG_DIR/mcp/servers.json"
echo "   Continue config -> ~/.continue/config.yaml"
echo "   MCP servers     -> $CONFIG_DIR/mcp/servers.json (add credentials before use)"

# 7. Summary
echo "Step 7/7 — Done."
echo "────────────────────────────────────"
echo "   Model        : forge-coder ($RECOMMENDED_MODEL)"
echo "   Context      : $MAX_CONTEXT tokens"
echo "   Config       : $CONFIG_DIR"
echo "   CLI          : forge status"
echo ""
echo "   Editors      : Continue config installed; see integrations/cursor for Cursor"
echo "   Next         : add MCP credentials in $CONFIG_DIR/mcp/servers.json, then 'forge index .'"
