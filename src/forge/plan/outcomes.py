"""Per-task dogfooding outcomes: capture and aggregate local-model quality metrics."""
from __future__ import annotations

import json
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
