"""Validate and model a Claude-produced tasks.json manifest."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema

TASKS_SCHEMA = {
    "type": "object",
    "required": ["feature", "tasks"],
    "properties": {
        "feature": {"type": "string"},
        "stack": {"type": "string"},
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "title", "acceptance_criteria"],
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "files": {"type": "array", "items": {"type": "string"}},
                    "dependencies": {"type": "array", "items": {"type": "string"}},
                    "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


class ManifestError(ValueError):
    """Raised when a tasks.json is malformed or schema-invalid."""


@dataclass
class Task:
    id: str
    title: str
    files: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)


@dataclass
class Manifest:
    feature: str
    stack: str
    tasks: list[Task]

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        return cls(
            feature=data["feature"],
            stack=data.get("stack", ""),
            tasks=[
                Task(
                    id=t["id"], title=t["title"],
                    files=list(t.get("files", [])),
                    dependencies=list(t.get("dependencies", [])),
                    acceptance_criteria=list(t.get("acceptance_criteria", [])),
                )
                for t in data["tasks"]
            ],
        )

    def task(self, task_id: str) -> Task | None:
        return next((t for t in self.tasks if t.id == task_id), None)


def load_manifest(path: str | Path) -> Manifest:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Could not read tasks.json: {exc}") from exc
    try:
        jsonschema.validate(data, TASKS_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise ManifestError(f"tasks.json failed schema validation: {exc.message}") from exc
    manifest = Manifest.from_dict(data)
    ids = {t.id for t in manifest.tasks}
    for t in manifest.tasks:
        for dep in t.dependencies:
            if dep not in ids:
                raise ManifestError(
                    f"Task '{t.id}' depends on unknown task '{dep}'")
    return manifest


def next_task(manifest: Manifest, completed: set[str]) -> Task | None:
    for t in manifest.tasks:
        if t.id in completed:
            continue
        if all(dep in completed for dep in t.dependencies):
            return t
    return None
