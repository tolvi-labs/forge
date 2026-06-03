"""Walk a manifest in dependency order: code agent proposes, review agent checks.

This is a scaffold. It PROPOSES per-task changes (it does not auto-apply or commit
model-written code) — applying stays under human/Claude review, per the
Claude->Local->Claude design. LangGraph-based branching/retry is a future swap.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from forge.agents.roles import code_prompt, review_prompt
from forge.llm import generate as _default_generate
from forge.plan.manifest import Manifest, next_task

GenerateFn = Callable[..., str]


@dataclass
class TaskResult:
    task_id: str
    title: str
    proposal: str
    review: str


def run_manifest(manifest: Manifest, *, generate_fn: GenerateFn | None = None) -> list[TaskResult]:
    gen = generate_fn or _default_generate
    results: list[TaskResult] = []
    processed: set[str] = set()
    while True:
        task = next_task(manifest, processed)
        if task is None:
            break  # all done, or remaining tasks are blocked (e.g. a cycle)
        proposal = gen(code_prompt(task))
        review = gen(review_prompt(task, proposal))
        results.append(TaskResult(task.id, task.title, proposal, review))
        processed.add(task.id)
    return results
