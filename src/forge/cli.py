"""Forge command-line interface."""
from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path

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


@main.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--watch", is_flag=True, help="Re-index on file changes.")
def index(path: str, watch: bool) -> None:
    """Index a project into the local vector store."""
    from forge.embedder import embedder
    from forge.index import index_repo
    from forge.store.chroma import ChromaStore

    root = Path(path).resolve()
    repo_hash = hashlib.sha256(str(root).encode()).hexdigest()[:16]
    store = ChromaStore(config.data_dir() / "indexes" / repo_hash)

    def run() -> None:
        stats = index_repo(root, store, embedder.embed)
        console.print(
            f"Indexed {stats.files_indexed} file(s) "
            f"({stats.chunks_written} chunks), skipped {stats.files_skipped}, "
            f"pruned {stats.files_pruned}."
        )

    run()
    if watch:
        _watch(root, run)


def _watch(root: Path, run) -> None:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    class _Handler(FileSystemEventHandler):
        def on_any_event(self, event) -> None:
            if not event.is_directory:
                run()

    observer = Observer()
    observer.schedule(_Handler(), str(root), recursive=True)
    observer.start()
    console.print("[dim]Watching for changes — Ctrl-C to stop.[/]")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
