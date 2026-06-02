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


@main.command()
@click.argument("query")
@click.option("--path", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--top-k", default=6, show_default=True)
def search(query: str, path: str, top_k: int) -> None:
    """Show the code chunks Forge retrieves for a query."""
    from forge.embedder import embedder
    from forge.retriever.retriever import retrieve
    from forge.store.chroma import ChromaStore

    root = Path(path).resolve()
    repo_hash = hashlib.sha256(str(root).encode()).hexdigest()[:16]
    store = ChromaStore(config.data_dir() / "indexes" / repo_hash)
    hits = retrieve(store, embedder.embed, query, top_k=top_k)
    if not hits:
        console.print("[yellow]No results. Have you run `forge index` here?[/]")
        return
    for h in hits:
        console.print(f"[bold]{h['file_path']}:{h['start_line']}-{h['end_line']}[/] "
                      f"({h.get('symbol_name', '')})")


def _dedup_hits(hits: list[dict], cag_paths: set[str]) -> list[dict]:
    """Drop RAG hits already included verbatim as CAG blocks (e.g. README/manifests)."""
    return [h for h in hits if h.get("file_path") not in cag_paths]


def _trim_history(history: str, max_tokens: int = 8000) -> str:
    """Keep the most recent conversation turns under a token budget, dropping oldest turns first."""
    from forge.chunker.chunk import count_tokens

    if count_tokens(history) <= max_tokens:
        return history
    marker = "\nUser: "
    # split into individual turns (each begins with the marker)
    parts = history.split(marker)
    turns = [marker + p for p in parts[1:]]  # drop any pre-marker prefix
    kept: list[str] = []
    for turn in reversed(turns):             # newest first
        if count_tokens("".join([turn] + kept)) > max_tokens:
            break
        kept.insert(0, turn)
    return "".join(kept)


def _gather_cag(root: Path) -> tuple[list[str], set[str]]:
    from forge.vault.loader import load_vault

    blocks: list[str] = []
    paths: set[str] = set()
    for name in ("README.md", "package.json", "pyproject.toml", "tsconfig.json"):
        f = root / name
        if f.is_file():
            text = f.read_text(encoding="utf-8", errors="replace")
            blocks.append(f"# {name}\n{text}")
            paths.add(str(f))
    vault_block = load_vault(root)
    if vault_block:
        blocks.append(vault_block)
    return blocks, paths


def _answer(root: Path, message: str, history: str) -> str:
    from forge.assembler import assemble
    from forge.embedder import embedder
    from forge.llm import generate
    from forge.retriever.retriever import retrieve
    from forge.store.chroma import ChromaStore

    repo_hash = hashlib.sha256(str(root).encode()).hexdigest()[:16]
    store = ChromaStore(config.data_dir() / "indexes" / repo_hash)
    cag_blocks, cag_paths = _gather_cag(root)
    hits = _dedup_hits(retrieve(store, embedder.embed, message, top_k=6), cag_paths)
    prompt = assemble(message, cag_blocks=cag_blocks, rag_hits=hits, history=history)
    return generate(prompt)


@main.command()
@click.option("--path", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--message", "-m", default=None, help="Single-shot question; omit for a REPL.")
def chat(path: str, message: str | None) -> None:
    """Chat with the local model using CAG+RAG context from this repo."""
    root = Path(path).resolve()
    if message is not None:
        console.print(_answer(root, message, history=""))
        return
    console.print("[dim]Forge chat — Ctrl-C or 'exit' to quit.[/]")
    history = ""
    while True:
        try:
            msg = click.prompt("you", prompt_suffix="> ")
        except (EOFError, click.Abort):
            break
        if msg.strip() in {"exit", "quit"}:
            break
        answer = _answer(root, msg, _trim_history(history))
        console.print(answer)
        history += f"\nUser: {msg}\nForge: {answer}\n"


def _watch(root: Path, run) -> None:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    state = {"dirty": False, "last": 0.0}

    class _Handler(FileSystemEventHandler):
        def on_any_event(self, event) -> None:
            if not event.is_directory:
                state["dirty"] = True
                state["last"] = time.monotonic()

    observer = Observer()
    observer.schedule(_Handler(), str(root), recursive=True)
    observer.start()
    console.print("[dim]Watching for changes — Ctrl-C to stop.[/]")
    try:
        while True:
            time.sleep(0.3)
            if state["dirty"] and time.monotonic() - state["last"] >= 0.5:
                state["dirty"] = False
                run()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
