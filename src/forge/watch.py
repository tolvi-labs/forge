"""forge watch — live dashboard for active forge plans."""
from __future__ import annotations

import json
import select
import sys
import termios
import threading
import time
import tty
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class WatchSession:
    plan_dir: Path
    feature: str
    phase: str | None
    tasks: list[dict]          # [{id, title, dependencies}]
    completed: list[str]
    last_inference: dict | None
    context_stats: dict | None


def discover_repos(data_dir: Path) -> list[WatchSession]:
    """Return WatchSession for every plan dir that has a phase.json, sorted by feature name."""
    plans_dir = data_dir / "plans"
    if not plans_dir.exists():
        return []
    sessions = [
        read_session(d, data_dir)
        for d in plans_dir.iterdir()
        if d.is_dir() and (d / "phase.json").exists()
    ]
    return sorted(sessions, key=lambda s: s.feature)


def read_session(plan_dir: Path, data_dir: Path) -> WatchSession:
    """Read all state files for one plan_dir. Missing/malformed files yield safe defaults."""
    feature = "unknown"
    tasks: list[dict] = []
    phase: str | None = None
    completed: list[str] = []

    manifest_path = plan_dir / "manifest.json"
    if manifest_path.exists():
        try:
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            feature = m.get("feature", "unknown")
            tasks = [
                {"id": t["id"], "title": t["title"],
                 "dependencies": t.get("dependencies", [])}
                for t in m.get("tasks", [])
            ]
        except (json.JSONDecodeError, KeyError):
            pass

    phase_path = plan_dir / "phase.json"
    if phase_path.exists():
        try:
            phase = json.loads(phase_path.read_text(encoding="utf-8")).get("phase")
        except (json.JSONDecodeError, KeyError):
            pass

    state_path = plan_dir / "state.json"
    if state_path.exists():
        try:
            completed = json.loads(state_path.read_text(encoding="utf-8")).get("completed", [])
        except (json.JSONDecodeError, KeyError):
            pass

    # inference.log is global — one Ollama instance per machine, shared across all plans
    last_inference = _read_last_inference(data_dir / "inference.log")

    context_stats: dict | None = None
    ctx_path = data_dir / "context" / f"{plan_dir.name}.json"
    if ctx_path.exists():
        try:
            context_stats = json.loads(ctx_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    return WatchSession(
        plan_dir=plan_dir,
        feature=feature,
        phase=phase,
        tasks=tasks,
        completed=completed,
        last_inference=last_inference,
        context_stats=context_stats,
    )


def _read_last_inference(log_path: Path) -> dict | None:
    if not log_path.exists():
        return None
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        line = line.strip()
        if line:
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def _find_current_task_id(tasks: list[dict], completed: list[str] | set[str]) -> str | None:
    """Return the first task whose deps are all done and which is not yet completed."""
    for task in tasks:
        if task["id"] not in completed and all(
            dep in completed for dep in task.get("dependencies", [])
        ):
            return task["id"]
    return None


# ---------------------------------------------------------------------------
# Display builder
# ---------------------------------------------------------------------------

_PHASE_STYLES: dict[str, tuple[str, str, str]] = {
    "executing": ("blue", "⚙", "EXECUTING"),
    "verifying": ("yellow", "⏳", "VERIFYING"),
    "done":      ("green", "✓", "DONE"),
}
_IDLE_STYLE = ("dim", "○", "IDLE")


def build_display(sessions: list[WatchSession], active_idx: int):
    """Return a Rich renderable for the dashboard. Importable for testing."""
    from rich.console import Group

    if not sessions:
        return _build_idle_display()

    session = sessions[active_idx % len(sessions)]
    parts = []
    if len(sessions) >= 2:
        parts.append(_build_tab_bar(sessions, active_idx))
    parts.append(_build_phase_panel(session))
    parts.append(_build_tasks_panel(session))
    parts.append(_build_metrics_panel(session))
    return Group(*parts)


def _build_idle_display():
    from rich.console import Group
    from rich.panel import Panel
    from rich.text import Text

    content = Text()
    content.append("  ○  IDLE\n\n", style="dim bold")
    content.append("  no active plan — run forge plan to start", style="dim")
    return Group(Panel(content, title="forge watch"))


def _build_tab_bar(sessions: list[WatchSession], active_idx: int):
    from rich.text import Text

    text = Text()
    for i, s in enumerate(sessions):
        label = f" {i + 1} {s.feature} "
        text.append(label, style="bold white on blue" if i == active_idx else "dim")
    text.append("  ← / →", style="dim")
    return text


def _build_phase_panel(session: WatchSession):
    from rich.panel import Panel
    from rich.text import Text

    phase = session.phase or "idle"
    color, icon, label = _PHASE_STYLES.get(phase, _IDLE_STYLE)
    content = Text(f"  {icon}  {label}", style=color)
    return Panel(content, title="forge watch")


def _build_tasks_panel(session: WatchSession):
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    if not session.tasks:
        return Panel(Text("no tasks", style="dim"), title="tasks")

    completed_set = set(session.completed)
    current_id = _find_current_task_id(session.tasks, completed_set)

    table = Table(box=None, show_header=False, padding=(0, 1))
    table.add_column(width=2)
    table.add_column()

    for task in session.tasks:
        tid = task["id"]
        if tid in completed_set:
            marker = Text("✓", style="green")
            label = Text(f"{tid}  {task['title']}", style="dim")
        elif tid == current_id:
            marker = Text("→", style="yellow")
            label = Text(f"{tid}  {task['title']}", style="bold")
        else:
            marker = Text("·", style="dim")
            label = Text(f"{tid}  {task['title']}", style="dim")
        table.add_row(marker, label)

    return Panel(table, title="tasks")


def _build_metrics_panel(session: WatchSession):
    from rich.panel import Panel
    from rich.text import Text

    inf = session.last_inference
    ctx = session.context_stats

    if inf is None and ctx is None:
        return Panel(Text("no inference data yet", style="dim"), title="last inference")

    content = Text()
    if inf is not None:
        tps = inf.get("tokens_per_sec", 0.0)
        tin = inf.get("tokens_in", 0)
        tout = inf.get("tokens_out", 0)
        dur = inf.get("duration_ms", 0)
        tps_style = "green bold" if tps >= 30 else ("yellow" if tps >= 15 else "red")
        content.append(f"{tps:.1f} tok/s", style=tps_style)
        content.append(f"   in {tin}   out {tout}   {dur:.0f}ms\n")

    if ctx is not None:
        used = ctx.get("tokens_used", 0)
        budget = max(ctx.get("tokens_budget", 1), 1)
        fill = min(used / budget, 1.0)
        filled = int(fill * 10)
        bar = "█" * filled + "░" * (10 - filled)
        bar_style = "green" if fill < 0.5 else ("yellow" if fill < 0.8 else "red")
        content.append(f"ctx  {used // 1000:.1f}k / {budget // 1000:.0f}k  ", style="dim")
        content.append(bar, style=bar_style)

    return Panel(content, title="last inference")


# ---------------------------------------------------------------------------
# Keyboard handler (background thread, raw terminal mode)
# ---------------------------------------------------------------------------

class KeyboardHandler:
    """Reads keypresses in a daemon thread; exposes current tab index."""

    def __init__(self, tab_count: int = 1) -> None:
        self._tab_count = max(1, tab_count)
        self._idx = 0
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float = 0.5) -> None:
        self._thread.join(timeout=timeout)

    @property
    def idx(self) -> int:
        with self._lock:
            return self._idx

    def update_tab_count(self, count: int) -> None:
        with self._lock:
            self._tab_count = max(1, count)
            if self._idx >= self._tab_count:
                self._idx = self._tab_count - 1

    def was_stopped(self) -> bool:
        return self._stop.is_set()

    def _run(self) -> None:
        fd = sys.stdin.fileno()
        try:
            old = termios.tcgetattr(fd)
        except termios.error:
            self._stop.set()  # stdin is not a TTY; disable keyboard navigation
            return
        try:
            tty.setraw(fd)
            while not self._stop.is_set():
                r, _, _ = select.select([sys.stdin], [], [], 0.1)
                if not r:
                    continue
                ch = sys.stdin.read(1)
                if ch == "\x03":  # Ctrl-C
                    self._stop.set()
                elif ch == "\x1b":  # possible arrow key escape sequence
                    r2, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if not r2:
                        continue
                    ch2 = sys.stdin.read(1)
                    if ch2 == "[":
                        r3, _, _ = select.select([sys.stdin], [], [], 0.05)
                        if not r3:
                            continue
                        ch3 = sys.stdin.read(1)
                        with self._lock:
                            n = self._tab_count
                            if ch3 == "C":  # right arrow
                                self._idx = (self._idx + 1) % n
                            elif ch3 == "D":  # left arrow
                                self._idx = (self._idx - 1) % n
                elif ch.isdigit():
                    n = int(ch)
                    with self._lock:
                        if 1 <= n <= self._tab_count:
                            self._idx = n - 1
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_watch(data_dir: Path) -> None:
    """Start the live watch dashboard. Blocks until Ctrl-C."""
    from rich.live import Live

    kb = KeyboardHandler(tab_count=1)
    kb.start()
    try:
        with Live(refresh_per_second=2) as live:
            while not kb.was_stopped():
                sessions = discover_repos(data_dir)
                kb.update_tab_count(max(1, len(sessions)))
                live.update(build_display(sessions, kb.idx))
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        kb.stop()
        kb.join()
