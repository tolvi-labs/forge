"""Forge command-line interface."""
from __future__ import annotations

import datetime
import hashlib
import json
import shutil
import time
from pathlib import Path

import click
from rich.console import Console

from forge import __version__, config

console = Console()

# Forge brand accent (brand lime). Rich downgrades truecolor to the
# nearest ANSI color automatically and strips styling on non-color terminals.
BRAND = "#C6F23E"


def _render_logo() -> None:
    """Print the Forge brand wordmark; degrades to plain text off-color terminals."""
    console.print(f"[bold {BRAND}]⬢ FORGE[/]  [dim]· local-first AI dev environment[/]")
    console.print(f"[{BRAND}]{'─' * 44}[/]")


@click.group()
@click.version_option(__version__, prog_name="forge")
def main() -> None:
    """Forge — local-first AI development environment."""


def _render_status() -> None:
    """Print the active model, context limit, and stack profile."""
    _render_logo()
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


@main.command()
def status() -> None:
    """Show the active model, context limit, and stack profile."""
    console.clear()
    _render_status()


@main.command()
def start() -> None:
    """Start Ollama, ensure models and forge-coder, then show status."""
    from forge import runtime

    try:
        hp = config.load_hardware_profile()
    except FileNotFoundError:
        console.print("[yellow]Hardware profile not detected.[/] Run setup/detect-hardware.sh.")
        raise SystemExit(1)

    def event(msg: str) -> None:
        console.print(f"  {msg}")

    try:
        runtime.ensure_ollama(on_event=event)
        runtime.ensure_models(hp, on_event=event)
        runtime.ensure_forge_coder(hp, on_event=event)
    except RuntimeError as exc:
        console.print(f"[red]✗[/] {exc}")
        raise SystemExit(1)

    console.print()
    _render_status()


@main.command()
def stop() -> None:
    """Stop the Ollama server, only if forge started it."""
    from forge import runtime

    runtime.stop_ollama(on_event=lambda msg: console.print(f"  {msg}"))


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
        summary = (
            f"Indexed {stats.files_indexed} file(s) "
            f"({stats.chunks_written} chunks), skipped {stats.files_skipped}, "
            f"pruned {stats.files_pruned}"
        )
        if stats.files_failed:
            summary += f", failed {stats.files_failed}"
        console.print(summary + ".")

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


def _gather_cag(root: Path, query: str | None = None) -> tuple[list[str], set[str]]:
    from forge.embedder import embedder
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
        vault_block = load_vault(
            root, max_tokens=profile.vault_max_tokens,
            query=query, embed_fn=embedder.embed,
            core_recent_n=profile.vault_core_recent,
        )
        if vault_block:
            blocks.append(vault_block)
    return blocks, paths


def _make_inference_logger(log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    def _log(stats: dict) -> None:
        entry = json.dumps(
            {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(), **stats}
        )
        with log_path.open("a", encoding="utf-8") as f:
            f.write(entry + "\n")
    return _log


def _write_context_stats(path: Path, *, tokens_used: int, tokens_budget: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"tokens_used": tokens_used, "tokens_budget": tokens_budget}),
        encoding="utf-8",
    )


def _answer(root: Path, message: str, history: str) -> str:
    from forge.assembler import assemble
    from forge.embedder import embedder
    from forge.llm import generate
    from forge.retriever.retriever import retrieve
    from forge.store.chroma import ChromaStore

    repo_hash = hashlib.sha256(str(root).encode()).hexdigest()[:16]
    store = ChromaStore(config.data_dir() / "indexes" / repo_hash)
    profile = _active_profile()
    cag_blocks, cag_paths = _gather_cag(root, query=message)
    hits = _dedup_hits(
        retrieve(store, embedder.embed, message,
                 top_k=profile.rag_top_k, rerank=profile.rerank),
        cag_paths,
    )
    prompt = assemble(message, cag_blocks=cag_blocks, rag_hits=hits, history=history,
                      max_context=profile.max_context_tokens)
    from forge.chunker.chunk import count_tokens
    _write_context_stats(
        config.data_dir() / "context" / f"{repo_hash}.json",
        tokens_used=count_tokens(prompt),
        tokens_budget=profile.max_context_tokens,
    )
    return generate(
        prompt,
        stats_callback=_make_inference_logger(config.data_dir() / "inference.log"),
    )


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
    from forge.plan.workflow import complete, read_state, write_phase

    root = Path(path).resolve()
    pdir = _plan_dir(root)
    manifest = Manifest.from_dict(json.loads((pdir / "manifest.json").read_text()))
    task = manifest.task(task_id)
    if task is None:
        raise click.ClickException(f"No such task: {task_id}")
    complete(root, pdir, task_id, task.title)
    done = len(read_state(pdir)["completed"])
    if done == len(manifest.tasks):
        write_phase(pdir, "done")
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


@main.command()
@click.argument("task_id")
@click.option("--path", type=click.Path(exists=True, file_okay=False), default=".")
def outcome(task_id: str, path: str) -> None:
    """Record a completed task's outcome for dogfooding metrics.

    Run this right after you review and fix the task, before `plan next`, so the only working-tree delta on the task's files is your rework.
    """
    from forge.plan.manifest import Manifest
    from forge.plan.outcomes import compute_task_metrics, read_outcomes, upsert_outcome
    from forge.plan.workflow import read_state

    root = Path(path).resolve()
    pdir = _plan_dir(root)
    manifest = Manifest.from_dict(json.loads((pdir / "manifest.json").read_text()))
    task = manifest.task(task_id)
    if task is None:
        raise click.ClickException(f"No such task: {task_id}")
    if task_id not in set(read_state(pdir)["completed"]):
        raise click.ClickException(
            f"Task {task_id} is not completed yet; run `forge plan complete {task_id}` first.")
    if any(r["task_id"] == task_id for r in read_outcomes(pdir)) and not click.confirm(
            f"{task_id} already has an outcome; overwrite?"):
        return

    metrics = compute_task_metrics(root, task, config.data_dir() / "inference.log")
    if metrics["commit"] is None:
        console.print(f"[yellow]No commit found for {task_id}[/] (no-op task); recording zeroed metrics.")
    else:
        console.print(f"rework churn : {metrics['rework_lines']} / {metrics['produced_lines']} lines "
                      f"({metrics['churn'] * 100:.1f}%)  [auto]")
        console.print(f"local tokens : {metrics['local_tokens']} @ "
                      f"{metrics['tokens_per_sec']:.0f} tok/s  [auto]")

    accepted = click.prompt("accepted",
                            type=click.Choice(["clean", "minor", "rework", "rejected"]))
    trust = click.prompt("trust (1-5)", type=click.IntRange(1, 5))
    ttype = click.prompt("type",
                         type=click.Choice(["bugfix", "feature", "refactor", "test", "config", "other"]))
    reason = "" if accepted == "clean" else click.prompt(
        "failure reason", default="", show_default=False)

    upsert_outcome(pdir, {
        "task_id": task.id,
        "type": ttype,
        "title": task.title,
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "commit": metrics["commit"],
        "produced_lines": metrics["produced_lines"],
        "rework_lines": metrics["rework_lines"],
        "churn": metrics["churn"],
        "local_tokens": metrics["local_tokens"],
        "duration_ms": metrics["duration_ms"],
        "tokens_per_sec": metrics["tokens_per_sec"],
        "accepted": accepted,
        "trust": trust,
        "failure_reason": reason,
    })
    console.print(f"[green]Recorded outcome for {task_id}.[/]")


@main.command()
@click.option("--path", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--all", "all_plans", is_flag=True,
              help="Pool outcomes across every plan (and repo) instead of just this one.")
def report(path: str, all_plans: bool) -> None:
    """Summarize dogfooding outcomes: acceptance rate, churn, tokens, trust."""
    from rich.panel import Panel

    from forge.plan.outcomes import aggregate, read_outcomes

    if all_plans:
        records: list[dict] = []
        for plan_dir in sorted((config.data_dir() / "plans").glob("*")):
            records.extend(read_outcomes(plan_dir))
    else:
        records = read_outcomes(_plan_dir(Path(path).resolve()))

    if not records:
        console.print("No outcomes recorded yet. Run `forge outcome <task_id>` "
                      "after completing tasks.")
        return

    agg = aggregate(records)
    lines = [
        f"[bold]acceptance[/]  {agg['accepted_rate'] * 100:.0f}%  "
        f"({agg['accepted']}/{agg['total']} tasks)   clean-only {agg['clean_rate'] * 100:.0f}%",
        "by type: " + " | ".join(
            f"{t} {b['rate'] * 100:.0f}%" for t, b in sorted(agg["by_type"].items())),
        f"rework churn (median)  {agg['median_churn'] * 100:.1f}%",
        f"local tokens  {agg['local_tokens']:,} @ {agg['mean_tokens_per_sec']:.0f} tok/s",
        f"trust (mean)  {agg['mean_trust']:.1f} / 5",
    ]
    if agg["failure_reasons"]:
        tally = ", ".join(f"{reason} ×{n}" for reason, n in sorted(
            agg["failure_reasons"].items(), key=lambda kv: -kv[1]))
        lines.append(f"failures: {tally}")
    if all_plans:
        lines.append("[dim]caveat: concurrent plans share one inference.log; "
                     "token attribution can cross plans.[/]")
    title = "forge report — all plans" if all_plans else "forge report"
    console.print(Panel("\n".join(lines), title=title))


@main.command()
def watch() -> None:
    """Live dashboard for active forge plans."""
    from forge.watch import run_watch
    run_watch(config.data_dir())


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
