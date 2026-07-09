"""Per-task dogfooding outcomes: capture and aggregate local-model quality metrics."""
from __future__ import annotations

import datetime
import json
import statistics
import subprocess
from pathlib import Path


def outcomes_path(plan_dir: Path) -> Path:
    return plan_dir / "outcomes.jsonl"


def read_outcomes(plan_dir: Path) -> list[dict]:
    path = outcomes_path(plan_dir)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_outcomes(plan_dir: Path, records: list[dict]) -> None:
    path = outcomes_path(plan_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def upsert_outcome(plan_dir: Path, record: dict) -> None:
    records = [r for r in read_outcomes(plan_dir) if r.get("task_id") != record.get("task_id")]
    records.append(record)
    write_outcomes(plan_dir, records)


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def _find_task_commit(repo: Path, task_id: str) -> str | None:
    prefix = f"[{task_id}] "
    for line in _git(repo, "log", "--format=%H %s").splitlines():
        sha, _, subject = line.partition(" ")
        if subject.startswith(prefix):
            return sha
    return None


def _commit_time(repo: Path, ref: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(_git(repo, "show", "-s", "--format=%cI", ref).strip())


def _sum_numstat(repo: Path, args: list[str], files: list[str]) -> tuple[int, int]:
    cmd = [*args, "--numstat"]
    if files:
        cmd += ["--", *files]
    added = deleted = 0
    for line in _git(repo, *cmd).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            added += int(parts[0])
            deleted += int(parts[1])
    return added, deleted


def _sum_tokens(inference_log: Path, start: datetime.datetime,
                 end: datetime.datetime) -> tuple[int, float, float]:
    if not inference_log.exists():
        return 0, 0.0, 0.0
    tokens = 0
    duration = 0.0
    rates: list[float] = []
    for line in inference_log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        ts = datetime.datetime.fromisoformat(rec["ts"])
        if start < ts <= end:
            tokens += rec.get("tokens_in", 0) + rec.get("tokens_out", 0)
            duration += rec.get("duration_ms", 0.0)
            if rec.get("tokens_per_sec", 0.0) > 0:
                rates.append(rec["tokens_per_sec"])
    mean_rate = round(sum(rates) / len(rates), 1) if rates else 0.0
    return tokens, duration, mean_rate


def compute_task_metrics(repo: Path, task, inference_log: Path) -> dict:
    sha = _find_task_commit(repo, task.id)
    if sha is None:
        return {"commit": None, "produced_lines": 0, "rework_lines": 0, "churn": 0.0,
                "local_tokens": 0, "duration_ms": 0.0, "tokens_per_sec": 0.0}
    produced, _ = _sum_numstat(repo, ["show", "--format=", sha], task.files)
    r_added, r_deleted = _sum_numstat(repo, ["diff", sha], task.files)
    rework = r_added + r_deleted
    tokens, duration, rate = _sum_tokens(
        inference_log, _commit_time(repo, f"{sha}^"), _commit_time(repo, sha))
    return {
        "commit": sha,
        "produced_lines": produced,
        "rework_lines": rework,
        "churn": round(rework / max(produced, 1), 4),
        "local_tokens": tokens,
        "duration_ms": duration,
        "tokens_per_sec": rate,
    }


_ACCEPTED = {"clean", "minor"}


def aggregate(records: list[dict]) -> dict:
    total = len(records)
    if total == 0:
        return {"total": 0, "accepted": 0, "accepted_rate": 0.0, "clean_rate": 0.0,
                "by_type": {}, "median_churn": 0.0, "local_tokens": 0,
                "mean_tokens_per_sec": 0.0, "mean_trust": 0.0, "failure_reasons": {}}
    accepted = sum(1 for r in records if r.get("accepted") in _ACCEPTED)
    clean = sum(1 for r in records if r.get("accepted") == "clean")
    by_type: dict[str, dict] = {}
    for r in records:
        bucket = by_type.setdefault(r.get("type", "other"), {"total": 0, "accepted": 0})
        bucket["total"] += 1
        if r.get("accepted") in _ACCEPTED:
            bucket["accepted"] += 1
    for bucket in by_type.values():
        bucket["rate"] = round(bucket["accepted"] / bucket["total"], 4)
    rates = [r["tokens_per_sec"] for r in records if r.get("tokens_per_sec", 0) > 0]
    reasons: dict[str, int] = {}
    for r in records:
        reason = r.get("failure_reason", "")
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
    return {
        "total": total,
        "accepted": accepted,
        "accepted_rate": round(accepted / total, 4),
        "clean_rate": round(clean / total, 4),
        "by_type": by_type,
        "median_churn": round(statistics.median(r.get("churn", 0.0) for r in records), 4),
        "local_tokens": sum(r.get("local_tokens", 0) for r in records),
        "mean_tokens_per_sec": round(sum(rates) / len(rates), 1) if rates else 0.0,
        "mean_trust": round(statistics.mean(r.get("trust", 0) for r in records), 2),
        "failure_reasons": reasons,
    }
