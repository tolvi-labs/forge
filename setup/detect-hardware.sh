#!/usr/bin/env bash
# Forge — detect-hardware.sh
# Detects system hardware and writes $XDG_CONFIG_HOME/forge/hardware-profile.json
set -euo pipefail

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/forge"
PROFILE_PATH="$CONFIG_DIR/hardware-profile.json"
mkdir -p "$CONFIG_DIR"

ARCH=$(uname -m)
OS=$(uname -s)

if [[ "$OS" == "Darwin" ]]; then
  RAM_GB=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
elif [[ "$OS" == "Linux" ]]; then
  RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}')
  if [[ "$RAM_KB" =~ ^[0-9]+$ ]]; then
    RAM_GB=$(( RAM_KB / 1024 / 1024 ))
  else
    echo "⚠️  Could not read /proc/meminfo; defaulting to 8GB profile." >&2
    RAM_GB=8
  fi
else
  echo "⚠️  Unsupported OS: $OS. Defaulting to 8GB profile." >&2
  RAM_GB=8
fi

if [[ "$ARCH" == "arm64" && "$OS" == "Darwin" ]]; then
  GPU_TYPE="apple_silicon"
elif command -v nvidia-smi &>/dev/null; then
  GPU_TYPE="nvidia"
else
  GPU_TYPE="cpu"
fi

STRETCH_MODEL=""
if [[ $RAM_GB -ge 48 ]]; then
  RECOMMENDED_MODEL="qwen2.5-coder:32b"; MAX_CONTEXT=131072
elif [[ $RAM_GB -ge 24 ]]; then
  RECOMMENDED_MODEL="qwen2.5-coder:14b"; STRETCH_MODEL="qwen2.5-coder:32b-instruct-q4_K_M"; MAX_CONTEXT=65536
elif [[ $RAM_GB -ge 16 ]]; then
  RECOMMENDED_MODEL="qwen2.5-coder:14b"; MAX_CONTEXT=65536
else
  RECOMMENDED_MODEL="qwen2.5-coder:7b"; MAX_CONTEXT=32768
fi

cat > "$PROFILE_PATH" <<JSON
{
  "arch": "$ARCH",
  "os": "$OS",
  "ram_gb": $RAM_GB,
  "gpu_type": "$GPU_TYPE",
  "recommended_model": "$RECOMMENDED_MODEL",
  "stretch_model": "$STRETCH_MODEL",
  "max_context_tokens": $MAX_CONTEXT,
  "embedding_model": "nomic-embed-text",
  "autocomplete_model": "qwen2.5-coder:7b"
}
JSON

echo "✅ Hardware profile written to $PROFILE_PATH"
echo "   ${ARCH} / ${OS} / ${RAM_GB}GB / ${GPU_TYPE} → ${RECOMMENDED_MODEL} @ ${MAX_CONTEXT} tokens"
