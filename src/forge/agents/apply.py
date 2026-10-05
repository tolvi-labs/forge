"""Apply the local model's edits to the plan's target repo, one commit per task.

`forge agents run --apply` drives this: each task gets the current contents of its
files plus the plan's per-task context, and the model answers with SEARCH/REPLACE
blocks. Local models write correct code but unreliable unified-diff markup, so Forge
applies the blocks itself (each SEARCH must match exactly once) and generates the real
git diff. An edit that stays inside the task's files and gets the reviewer's APPROVE
on that diff is committed as `[id] title` on a dedicated `forge/<feature>` branch.
"""
from __future__ import annotations

import datetime
import json
import re
import subprocess
from pathlib import Path
from typing import Callable

from forge.agents.roles import APPLY_AGENT_SYSTEM, review_prompt
from forge.assembler import format_hit
from forge.chunker.chunk import count_tokens, truncate_to_tokens
from forge.plan import outcomes, workflow

GenerateFn = Callable[..., str]

_FEEDBACK_MAX_TOKENS = 2000


def context_budget(profile_max: int, hardware_ctx: int | None, *,
                   reply_reserve: int, margin: float) -> int:
    """Prompt tokens the model can actually see: the smaller window, less the reply and a tokenizer margin.

    Ollama truncates an over-long prompt from the start, which is where the diff
    instructions live, so the budget must never exceed the model's real `num_ctx`.
    """
    window = min(profile_max, hardware_ctx) if hardware_ctx else profile_max
    return int((window - reply_reserve) * (1 - margin))


def _context_pieces(context: dict) -> list[str]:
    """Render plan context in priority order: interfaces, then decisions, then refs."""
    pieces: list[str] = []
    interfaces = context.get("interfaces") or {}
    lines = [f"- consumes: {c}" for c in interfaces.get("consumes", [])]
    lines += [f"- produces: {p}" for p in interfaces.get("produces", [])]
    if lines:
        pieces.append("# Interfaces\n" + "\n".join(lines))
    for d in context.get("decisions", []):
        pieces.append(f"# Decision: {d.get('title', '')} ({d.get('path', '')})\n"
                      f"{d.get('rationale', '')}")
    for r in context.get("refs", []):
        pieces.append(f"# Ref: {r.get('file', '?')}:{r.get('line', '?')} {r.get('symbol', '')}")
    return pieces


def build_prompt(task, files: dict[str, str | None], *, rag_hits: list[dict],
                 budget: int, feedback: str = "") -> str | None:
    """Assemble the code prompt, or None when the never-trimmed part alone exceeds `budget`.

    The instructions, the task, and full file contents are never trimmed: a model that
    sees a truncated file writes diffs against code it cannot see. Plan context and
    then RAG hits fill whatever budget is left, RAG first to go.
    """
    crit = "\n".join(f"- {c}" for c in task.acceptance_criteria)
    fixed = [APPLY_AGENT_SYSTEM, f"# Task: {task.title}\n# Acceptance criteria\n{crit}"]
    for path, text in files.items():
        if text is None:
            fixed.append(f"# File: {path} (new file)")
        else:
            fixed.append(f"# File: {path}\n```\n{text}```")
    if feedback:
        fixed.append("# Your previous attempt was rejected\n"
                     + truncate_to_tokens(feedback, _FEEDBACK_MAX_TOKENS))

    prompt = "\n\n".join(fixed)
    if count_tokens(prompt) > budget:
        return None
    for piece in [*_context_pieces(task.context),
                  *("# Related code\n" + format_hit(h) for h in rag_hits)]:
        candidate = prompt + "\n\n" + piece
        if count_tokens(candidate) > budget:
            break
        prompt = candidate
    return prompt


def review_approved(review: str) -> bool:
    """The reviewer's verdict is the last APPROVE / REQUEST_CHANGES marker it wrote."""
    markers = re.findall(r"\b(APPROVE|REQUEST_CHANGES)\b", review)
    return bool(markers) and markers[-1] == "APPROVE"


_BLOCK = re.compile(
    r"^(?P<path>[^\n]*)\n<{7} SEARCH\n(?P<search>.*?)^={7}\n(?P<replace>.*?)^>{7} REPLACE",
    re.S | re.M)


def _clean_path(line: str) -> str:
    return line.strip().strip("*`#:").strip()


def parse_edits(text: str) -> list[tuple[str, str, str]]:
    """(path, search, replace) for every SEARCH/REPLACE block, in order."""
    return [(_clean_path(m["path"]), m["search"], m["replace"]) for m in _BLOCK.finditer(text)]


def _replace_once(content: str, search: str, replace: str) -> tuple[str, bool, str]:
    """Replace the single occurrence of `search`; fall back to a whitespace-tolerant line match.

    The tolerant match ignores leading/trailing whitespace per line but still requires the
    same lines in the same order at exactly one place, so it never moves where an edit lands.
    """
    count = content.count(search)
    if count == 1:
        return content.replace(search, replace, 1), False, ""
    if count > 1:
        return content, False, f"SEARCH matches {count} places; include more lines"
    lines = content.splitlines(keepends=True)
    want = [ln.strip() for ln in search.splitlines()]
    hits = [i for i in range(len(lines) - len(want) + 1)
            if [ln.strip() for ln in lines[i:i + len(want)]] == want]
    if len(hits) == 1:
        i = hits[0]
        return "".join(lines[:i]) + replace + "".join(lines[i + len(want):]), True, ""
    if len(hits) > 1:
        return content, False, f"SEARCH matches {len(hits)} places; include more lines"
    first = search.strip().splitlines()[0] if search.strip() else ""
    return content, False, f"SEARCH not found: {first!r}"


def apply_edits(files: dict[str, str | None],
                edits: list[tuple[str, str, str]]) -> tuple[dict[str, str], bool, str]:
    """Apply edits in memory; return (new contents by path, needed_tolerance, error)."""
    new = {p: t for p, t in files.items() if t is not None}
    tolerant = False
    for path, search, replace in edits:
        current = new.get(path)
        if not search.strip():
            if current:
                return new, tolerant, f"empty SEARCH on existing file {path}; quote the lines to change"
            new[path] = replace
            continue
        if current is None:
            return new, tolerant, f"{path} does not exist; use an empty SEARCH to create it"
        updated, loose, error = _replace_once(current, search, replace)
        if error:
            return new, tolerant, f"{path}: {error}"
        new[path] = updated
        tolerant = tolerant or loose
    return new, tolerant, ""


def _tracked(repo: Path, path: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"HEAD:{path}"],
                          capture_output=True).returncode == 0


def _write_files(repo: Path, contents: dict[str, str]) -> None:
    for rel, text in contents.items():
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")


def _diff(repo: Path, paths: list[str]) -> str:
    """The unified diff of `paths` against HEAD, new files included."""
    new = [p for p in paths if not _tracked(repo, p) and (repo / p).exists()]
    if new:
        workflow._git(repo, "add", "-N", "--", *new)
    return workflow._git(repo, "diff", "HEAD", "--", *paths)


def _revert(repo: Path, paths: list[str]) -> None:
    """Put `paths` back to HEAD, deleting files the edit created."""
    for rel in paths:
        if _tracked(repo, rel):
            workflow._git(repo, "checkout", "-q", "HEAD", "--", rel)
        else:
            workflow._git(repo, "rm", "-q", "--cached", "--ignore-unmatch", "--", rel)
            (repo / rel).unlink(missing_ok=True)


class ApplyError(RuntimeError):
    """Raised when the target repo is not in a state `--apply` can safely run in."""


def branch_name(feature: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", feature.lower()).strip("-")
    return f"forge/{slug or 'plan'}"


def prepare_branch(repo: Path, branch: str, baseline: str) -> str:
    """Check out the run's branch from a clean tree: 'created' fresh, or 'resumed' in place."""
    dirty = workflow.changed_paths(repo)
    if dirty:
        raise ApplyError("Working tree is not clean; commit or stash first: " + ", ".join(dirty))
    current = workflow._git(repo, "branch", "--show-current").strip()
    if current == branch:
        return "resumed"
    exists = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet",
                             f"refs/heads/{branch}"], capture_output=True).returncode == 0
    if exists:
        raise ApplyError(f"Branch {branch} already exists. Check it out to resume the run, "
                         "or delete it to start over.")
    workflow._git(repo, "checkout", "-q", "-b", branch, baseline)
    return "created"


def _diffstat(diff: str, paths: list[str]) -> dict:
    added = sum(1 for line in diff.splitlines()
                if line.startswith("+") and not line.startswith("+++ "))
    deleted = sum(1 for line in diff.splitlines()
                  if line.startswith("-") and not line.startswith("--- "))
    return {"added": added, "deleted": deleted, "files": paths}


def _read_files(repo: Path, paths: list[str]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for rel in paths:
        f = repo / rel
        out[rel] = f.read_text(encoding="utf-8", errors="replace") if f.is_file() else None
    return out


def _attempt(repo: Path, task, gen: Callable[[str], str], *, budget: int,
             rag_hits: list[dict], feedback: str) -> dict:
    """One code -> apply -> review pass. Leaves the edit in the tree only when it is approved."""
    current = _read_files(repo, task.files)
    prompt = build_prompt(task, current, rag_hits=rag_hits, budget=budget, feedback=feedback)
    if prompt is None:
        return {"ok": False, "final": True, "reason": "too large for local context"}
    edits = parse_edits(gen(prompt))
    if not edits:
        return {"ok": False, "reason": "no SEARCH/REPLACE blocks in the answer"}
    outside = sorted({p for p, _, _ in edits} - set(task.files))
    if outside:
        return {"ok": False, "reason": "edits change files outside the task: " + ", ".join(outside)
                + ". Only these files may change: " + ", ".join(task.files)}
    contents, tolerant, error = apply_edits(current, edits)
    if error:
        return {"ok": False, "reason": f"edit does not apply: {error}"}
    _write_files(repo, contents)
    diff = _diff(repo, task.files)
    if not diff.strip():
        _revert(repo, task.files)
        return {"ok": False, "reason": "the edits change nothing"}
    review = gen(review_prompt(task, diff))
    if not review_approved(review):
        _revert(repo, task.files)
        return {"ok": False, "verdict": "REQUEST_CHANGES",
                "reason": f"reviewer requested changes:\n{review}"}
    return {"ok": True, "diff": diff, "tolerant": tolerant, "verdict": "APPROVE",
            "paths": sorted({p for p, _, _ in edits})}


def results_path(plan_dir: Path) -> Path:
    return plan_dir / "results.json"


def read_results(plan_dir: Path) -> dict | None:
    p = results_path(plan_dir)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def run_apply(repo: Path, plan_dir: Path, manifest, *, generate_fn: GenerateFn, budget: int,
              rag_fn: Callable | None = None, log_fn: Callable | None = None) -> dict:
    """Run every not-yet-completed task on the plan's branch; write and return results."""
    state = workflow.read_state(plan_dir)
    branch = branch_name(manifest.feature)
    prepare_branch(repo, branch, state["baseline"])

    previous = read_results(plan_dir) or {}
    entries = {t["id"]: t for t in previous.get("tasks", [])}
    file_owner = dict(previous.get("file_owner", {}))
    completed = set(state["completed"])
    failed: dict[str, str] = {}

    while True:
        handled = completed | set(failed)
        task = next((t for t in manifest.tasks if t.id not in handled
                     and all(d in handled for d in t.dependencies)), None)
        if task is None:
            break  # all handled, or the rest are blocked (e.g. a cycle)
        blocked_by = [d for d in task.dependencies if d in failed]
        if blocked_by:
            failed[task.id] = "skipped"
            entries[task.id] = {"id": task.id, "title": task.title, "status": "skipped",
                                "reason": f"depends on {', '.join(blocked_by)}"}
            continue

        usage = {"tokens": 0, "duration_ms": 0.0, "rates": []}

        def on_stats(stats: dict) -> None:
            usage["tokens"] += stats.get("tokens_in", 0) + stats.get("tokens_out", 0)
            usage["duration_ms"] += stats.get("duration_ms", 0.0)
            if stats.get("tokens_per_sec", 0) > 0:
                usage["rates"].append(stats["tokens_per_sec"])
            if log_fn:
                log_fn(stats)

        def gen(prompt: str) -> str:
            return generate_fn(prompt, stats_callback=on_stats)

        hits = rag_fn(task) if rag_fn else []
        feedback = ""
        attempts = 0
        result: dict = {}
        for attempts in (1, 2):
            result = _attempt(repo, task, gen, budget=budget, rag_hits=hits, feedback=feedback)
            if result["ok"] or result.get("final"):
                break
            feedback = result["reason"]

        entry = {"id": task.id, "title": task.title, "attempts": attempts,
                 "verdict": result.get("verdict", ""), "tokens": usage["tokens"]}
        if result["ok"]:
            workflow.complete(repo, plan_dir, task.id, task.title, task.files)
            completed.add(task.id)
            entry.update(status="applied", reason="", tolerant=result["tolerant"],
                         diffstat=_diffstat(result["diff"], result["paths"]),
                         commit=workflow._git(repo, "rev-parse", "HEAD").strip())
            for path in result["paths"]:
                file_owner[path] = task.id
            stale = [r for r in outcomes.read_outcomes(plan_dir) if r.get("task_id") != task.id]
            outcomes.write_outcomes(plan_dir, stale)  # a resumed task's earlier auto-rejection
        else:
            failed[task.id] = "rejected"
            entry.update(status="rejected", reason=result["reason"])
            rates = usage["rates"]
            outcomes.upsert_outcome(plan_dir, {
                "task_id": task.id, "type": "other", "title": task.title,
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "commit": None, "produced_lines": 0, "rework_lines": 0, "churn": 0.0,
                "local_tokens": usage["tokens"], "duration_ms": usage["duration_ms"],
                "tokens_per_sec": round(sum(rates) / len(rates), 1) if rates else 0.0,
                "accepted": "rejected", "trust": None,
                "failure_reason": result["reason"].splitlines()[0],
            })
        entries[task.id] = entry

    if len(completed) == len(manifest.tasks):
        workflow.write_phase(plan_dir, "done")
    results = {
        "feature": manifest.feature,
        "branch": branch,
        "baseline": state["baseline"],
        "model_tip": workflow._git(repo, "rev-parse", "HEAD").strip(),
        "tasks": [entries[t.id] for t in manifest.tasks if t.id in entries],
        "file_owner": file_owner,
    }
    results_path(plan_dir).write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results
