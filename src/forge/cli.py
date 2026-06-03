"""Forge command-line interface."""
from __future__ import annotations

import hashlib
import json
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


def _active_profile():
    from forge.profiles import ProfileError, load_profile
    try:
        return load_profile(config.load_active_profile())
    except ProfileError:
        return load_profile("react-node")


def _gather_cag(root: Path) -> tuple[list[str], set[str]]:
    from forge.vault.loader import load_vault

    profile = _active_profile()
    blocks: list[str] = []
    paths: set[str] = set()
    for name in (*profile.static_files, *profile.static_gcp_files):
        f = root / name
        if f.is_file():
            text = f.read_text(encoding="utf-8", errors="replace")
            blocks.append(f"# {name}\n{text}")
            paths.add(str(f))
    if profile.vault_enabled:
        vault_block = load_vault(root, max_tokens=profile.vault_max_tokens)
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
    profile = _active_profile()
    cag_blocks, cag_paths = _gather_cag(root)
    hits = _dedup_hits(retrieve(store, embedder.embed, message, top_k=profile.rag_top_k), cag_paths)
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


def _plan_dir(root: Path) -> Path:
    repo_hash = hashlib.sha256(str(root).encode()).hexdigest()[:16]
    return config.data_dir() / "plans" / repo_hash


@main.group()
def plan() -> None:
    """Load and drive a Claude-produced tasks.json plan."""


@plan.command("load")
@click.argument("tasks_json", type=click.Path(exists=True, dir_okay=False))
@click.option("--path", type=click.Path(exists=True, file_okay=False), default=".")
def plan_load(tasks_json: str, path: str) -> None:
    """Validate a tasks.json and make it the active plan for this repo."""
    from forge.plan.manifest import ManifestError, load_manifest
    from forge.plan.workflow import load_plan

    root = Path(path).resolve()
    try:
        manifest = load_manifest(tasks_json)
        load_plan(root, _plan_dir(root), manifest)
    except (ManifestError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc
    console.print(f"Loaded plan: [bold]{manifest.feature}[/] "
                  f"({len(manifest.tasks)} tasks)")


@plan.command("next")
@click.option("--path", type=click.Path(exists=True, file_okay=False), default=".")
def plan_next(path: str) -> None:
    """Show the next dependency-unblocked task."""
    from forge.plan.manifest import Manifest, next_task
    from forge.plan.workflow import read_state

    root = Path(path).resolve()
    pdir = _plan_dir(root)
    manifest = Manifest.from_dict(json.loads((pdir / "manifest.json").read_text()))
    state = read_state(pdir)
    task = next_task(manifest, set(state["completed"]))
    if task is None:
        console.print("[green]All tasks complete.[/]")
        return
    console.print(f"[bold]{task.id}[/] — {task.title}")
    for crit in task.acceptance_criteria:
        console.print(f"  • {crit}")


@plan.command("complete")
@click.argument("task_id")
@click.option("--path", type=click.Path(exists=True, file_okay=False), default=".")
def plan_complete(task_id: str, path: str) -> None:
    """Mark a task done and auto-commit its changes."""
    from forge.plan.manifest import Manifest
    from forge.plan.workflow import complete, read_state

    root = Path(path).resolve()
    pdir = _plan_dir(root)
    manifest = Manifest.from_dict(json.loads((pdir / "manifest.json").read_text()))
    task = manifest.task(task_id)
    if task is None:
        raise click.ClickException(f"No such task: {task_id}")
    complete(root, pdir, task_id, task.title)
    done = len(read_state(pdir)["completed"])
    console.print(f"Completed [bold]{task_id}[/] ({done}/{len(manifest.tasks)}).")


@plan.command("status")
@click.option("--path", type=click.Path(exists=True, file_okay=False), default=".")
def plan_status(path: str) -> None:
    """Show completion status of every task."""
    from forge.plan.manifest import Manifest, next_task
    from forge.plan.workflow import read_state

    root = Path(path).resolve()
    pdir = _plan_dir(root)
    manifest = Manifest.from_dict(json.loads((pdir / "manifest.json").read_text()))
    completed = set(read_state(pdir)["completed"])
    nxt = next_task(manifest, completed)
    for t in manifest.tasks:
        if t.id in completed:
            mark = "[green]done[/]"
        elif nxt is not None and t.id == nxt.id:
            mark = "[yellow]next[/]"
        elif all(d in completed for d in t.dependencies):
            mark = "ready"
        else:
            mark = "[dim]blocked[/]"
        console.print(f"{mark}\t{t.id}\t{t.title}")


@main.command()
@click.option("--path", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--out", type=click.Path(dir_okay=False), default=None,
              help="Write the verification bundle to a file instead of stdout.")
def verify(path: str, out: str | None) -> None:
    """Export the diff + manifest since plan load for Claude's review."""
    from forge.plan.workflow import verify as run_verify

    root = Path(path).resolve()
    bundle = run_verify(root, _plan_dir(root))
    text = (f"# Verification for: {bundle['manifest']['feature']}\n"
            f"# Completed: {', '.join(bundle['completed']) or 'none'}\n\n"
            f"## Diff since plan baseline\n```diff\n{bundle['diff']}\n```\n")
    if out:
        Path(out).write_text(text, encoding="utf-8")
        console.print(f"Wrote verification bundle to {out}")
    else:
        console.print(text)


@main.group()
def profile() -> None:
    """List or set the active stack profile."""


@profile.command("list")
def profile_list() -> None:
    """List available stack profiles."""
    from forge.profiles import list_profiles
    active = config.load_active_profile()
    for name in list_profiles():
        mark = "[green]*[/]" if name == active else " "
        console.print(f"{mark} {name}")


@profile.command("set")
@click.argument("name")
def profile_set(name: str) -> None:
    """Set the active stack profile."""
    from forge.profiles import ProfileError, load_profile
    try:
        load_profile(name)
    except ProfileError as exc:
        raise click.ClickException(str(exc)) from exc
    path = config.active_profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(name)
    console.print(f"Active profile set to [bold]{name}[/].")


@main.group()
def agents() -> None:
    """Run the multi-agent scaffold over a plan."""


@agents.command("run")
@click.argument("tasks_json", type=click.Path(exists=True, dir_okay=False))
def agents_run(tasks_json: str) -> None:
    """Code + review each task in a tasks.json with the local model (proposes only)."""
    import forge.llm as _llm
    from forge.agents.orchestrator import run_manifest
    from forge.plan.manifest import ManifestError, load_manifest

    try:
        manifest = load_manifest(tasks_json)
    except ManifestError as exc:
        raise click.ClickException(str(exc)) from exc
    for r in run_manifest(manifest, generate_fn=_llm.generate):
        console.print(f"[bold]{r.task_id}[/] — {r.title}")
        console.print(f"[dim]proposal:[/]\n{r.proposal}")
        console.print(f"[dim]review:[/]\n{r.review}\n")
    console.print("[yellow]Scaffold output — review proposals before applying.[/]")


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
