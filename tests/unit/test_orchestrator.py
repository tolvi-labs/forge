from forge.agents.orchestrator import run_manifest, TaskResult
from forge.plan.manifest import Manifest


MANIFEST = Manifest.from_dict({
    "feature": "Auth",
    "tasks": [
        {"id": "t1", "title": "context", "acceptance_criteria": ["exposes user"]},
        {"id": "t2", "title": "form", "dependencies": ["t1"],
         "acceptance_criteria": ["calls signIn"]},
    ],
})


def test_run_manifest_processes_in_dependency_order():
    calls = []

    def fake_generate(prompt, **kwargs):
        # record which task + role each call is for
        role = "review" if "reviewer" in prompt.lower() else "code"
        calls.append(role)
        return f"<{role} output>"

    results = run_manifest(MANIFEST, generate_fn=fake_generate)
    assert [r.task_id for r in results] == ["t1", "t2"]   # dependency order
    assert all(isinstance(r, TaskResult) for r in results)
    assert results[0].proposal == "<code output>"
    assert results[0].review == "<review output>"
    # each task ran code then review → 2 calls per task
    assert calls == ["code", "review", "code", "review"]


def test_run_manifest_stops_on_cycle_without_hanging():
    cyclic = Manifest.from_dict({
        "feature": "X",
        "tasks": [
            {"id": "a", "title": "a", "dependencies": ["b"], "acceptance_criteria": ["x"]},
            {"id": "b", "title": "b", "dependencies": ["a"], "acceptance_criteria": ["y"]},
        ],
    })
    results = run_manifest(cyclic, generate_fn=lambda p, **k: "out")
    assert results == []  # nothing is unblocked; returns cleanly, no hang
