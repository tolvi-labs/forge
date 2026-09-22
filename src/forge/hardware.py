"""Hardware detection: picks the model tier this machine can run.

Lives in the package, not in a setup script, so a pipx install can generate
its own profile with `forge detect-hardware`.
"""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

FALLBACK_RAM_GB = 8


def ram_gb(os_name: str, meminfo: Path = Path("/proc/meminfo")) -> int:
    """Physical memory in whole GB, rounded down; 8 when it cannot be read."""
    try:
        if os_name == "Darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"],
                                 capture_output=True, text=True, check=True).stdout
            return int(out.strip()) // 1024 ** 3
        if os_name == "Linux":
            for line in meminfo.read_text().splitlines():
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // 1024 ** 2
    except (OSError, ValueError, subprocess.CalledProcessError):
        pass
    print(f"⚠️  Could not read memory on {os_name}; defaulting to {FALLBACK_RAM_GB}GB profile.",
          file=sys.stderr)
    return FALLBACK_RAM_GB


def gpu_type(arch: str, os_name: str) -> str:
    if arch == "arm64" and os_name == "Darwin":
        return "apple_silicon"
    if shutil.which("nvidia-smi"):
        return "nvidia"
    return "cpu"


def profile_for(*, arch: str, os_name: str, ram_gb: int, gpu_type: str) -> dict:
    stretch_model = ""
    if ram_gb >= 48:
        recommended_model, max_context = "qwen3-coder-next", 131072
    elif ram_gb >= 24:
        recommended_model, stretch_model, max_context = "qwen3-coder:30b", "qwen3-coder-next", 65536
    elif ram_gb >= 16:
        recommended_model, max_context = "qwen2.5-coder:14b", 65536
    else:
        recommended_model, max_context = "qwen2.5-coder:7b", 32768
    return {
        "arch": arch,
        "os": os_name,
        "ram_gb": ram_gb,
        "gpu_type": gpu_type,
        "recommended_model": recommended_model,
        "stretch_model": stretch_model,
        "max_context_tokens": max_context,
        "embedding_model": "nomic-embed-text",
        "autocomplete_model": "qwen2.5-coder:7b",
    }


def detect() -> dict:
    arch, os_name = platform.machine(), platform.system()
    return profile_for(arch=arch, os_name=os_name, ram_gb=ram_gb(os_name),
                       gpu_type=gpu_type(arch, os_name))


def write_profile(profile: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2) + "\n")
