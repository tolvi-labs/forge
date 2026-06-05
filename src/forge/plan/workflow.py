"""Per-repo plan state + git glue for the Claude->Local->Claude loop."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from forge.plan.manifest import Manifest


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def _state_path(plan_dir: Path) -> Path:
    return plan_dir / "state.json"


def read_state(plan_dir: Path) -> dict:
    return json.loads(_state_path(plan_dir).read_text(encoding="utf-8"))


def write_state(plan_dir: Path, state: dict) -> None:
    _state_path(plan_dir).write_text(json.dumps(state, indent=2), encoding="utf-8")


def _phase_path(plan_dir: Path) -> Path:
    return plan_dir / "phase.json"


def write_phase(plan_dir: Path, phase: str) -> None:
    _phase_path(plan_dir).write_text(json.dumps({"phase": phase}), encoding="utf-8")


def read_phase(plan_dir: Path) -> str | None:
    p = _phase_path(plan_dir)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8")).get("phase")


def load_plan(repo: Path, plan_dir: Path, manifest: Manifest) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    baseline = _git(repo, "rev-parse", "HEAD").strip()
    (plan_dir / "manifest.json").write_text(
        json.dumps({
            "feature": manifest.feature,
            "stack": manifest.stack,
            "tasks": [
                {"id": t.id, "title": t.title, "files": t.files,
                 "dependencies": t.dependencies,
                 "acceptance_criteria": t.acceptance_criteria}
                for t in manifest.tasks
            ],
        }, indent=2),
        encoding="utf-8",
    )
    write_state(plan_dir, {"baseline": baseline, "completed": []})
    write_phase(plan_dir, "executing")


def complete(repo: Path, plan_dir: Path, task_id: str, title: str) -> None:
    state = read_state(plan_dir)
    if task_id not in state["completed"]:
        state["completed"].append(task_id)
    write_state(plan_dir, state)

    if _git(repo, "status", "--porcelain").strip():
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", f"[{task_id}] {title}")


def verify(repo: Path, plan_dir: Path) -> dict:
    state = read_state(plan_dir)
    write_phase(plan_dir, "verifying")
    baseline = state["baseline"]
    diff = _git(repo, "diff", baseline)
    manifest = json.loads((plan_dir / "manifest.json").read_text(encoding="utf-8"))
    return {"diff": diff, "manifest": manifest, "completed": state["completed"]}
