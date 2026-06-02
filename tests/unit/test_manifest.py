import json
import pytest
from forge.plan.manifest import load_manifest, next_task, Manifest, ManifestError


VALID = {
    "feature": "User auth",
    "stack": "react-node",
    "tasks": [
        {"id": "task-001", "title": "AuthContext", "files": ["a.tsx"],
         "dependencies": [], "acceptance_criteria": ["exposes user"]},
        {"id": "task-002", "title": "LoginForm", "files": ["b.tsx"],
         "dependencies": ["task-001"], "acceptance_criteria": ["calls signIn"]},
    ],
}


def _write(tmp_path, data):
    p = tmp_path / "tasks.json"
    p.write_text(json.dumps(data))
    return p


def test_load_manifest_parses_valid(tmp_path):
    m = load_manifest(_write(tmp_path, VALID))
    assert isinstance(m, Manifest)
    assert m.feature == "User auth"
    assert [t.id for t in m.tasks] == ["task-001", "task-002"]
    assert m.tasks[1].dependencies == ["task-001"]


def test_load_manifest_rejects_missing_tasks(tmp_path):
    with pytest.raises(ManifestError):
        load_manifest(_write(tmp_path, {"feature": "x"}))


def test_load_manifest_rejects_task_without_acceptance(tmp_path):
    bad = {"feature": "x", "tasks": [{"id": "t1", "title": "t"}]}
    with pytest.raises(ManifestError):
        load_manifest(_write(tmp_path, bad))


def test_load_manifest_rejects_invalid_json(tmp_path):
    p = tmp_path / "tasks.json"
    p.write_text("{not json")
    with pytest.raises(ManifestError):
        load_manifest(p)


def test_next_task_respects_dependencies():
    m = Manifest.from_dict(VALID)
    assert next_task(m, completed=set()).id == "task-001"
    assert next_task(m, completed={"task-001"}).id == "task-002"
    assert next_task(m, completed={"task-001", "task-002"}) is None
