"""Forge command-line interface."""
from __future__ import annotations

import shutil

import click
from rich.console import Console

from forge import __version__, config

console = Console()


@click.group()
@click.version_option(__version__, prog_name="forge")
def main() -> None:
    """Forge — local-first AI development environment."""


@main.command()
def status() -> None:
    """Show the active model, context limit, and stack profile."""
    profile_name = config.load_active_profile()
    try:
        hp = config.load_hardware_profile()
    except FileNotFoundError:
        console.print("[yellow]Hardware profile not detected.[/] Run setup/detect-hardware.sh.")
        console.print(f"Active profile : {profile_name}")
        return
    console.print(f"Model          : forge-coder ({hp.recommended_model})")
    console.print(f"Autocomplete   : {hp.autocomplete_model}")
    console.print(f"Context limit  : {hp.max_context_tokens} tokens")
    console.print(f"Active profile : {profile_name}")


def _check(label: str, ok: bool, detail: str = "") -> None:
    mark = "✅" if ok else "❌"
    suffix = f" — {detail}" if detail else ""
    console.print(f"{mark} {label}{suffix}")


@main.command()
def doctor() -> None:
    """Diagnose the local Forge environment."""
    ollama = shutil.which("ollama")
    _check("Ollama installed", ollama is not None,
           "" if ollama else "install from https://ollama.com")

    profile_path = config.hardware_profile_path()
    _check("Hardware profile present", profile_path.exists(),
           str(profile_path) if profile_path.exists()
           else f"missing at {profile_path}; run setup/detect-hardware.sh")

    cfg = config.config_dir()
    _check("Config directory", cfg.exists(),
           str(cfg) if cfg.exists() else f"will be created at {cfg}")
