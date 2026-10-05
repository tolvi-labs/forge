import subprocess
from pathlib import Path
from forge.plan import workflow
from forge.plan.manifest import load_manifest
import json
import pytest


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True)


def _repo(tmp_path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "tester")
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


def _manifest(tmp_path):
    data = {"feature": "F", "tasks": [
        {"id": "task-001", "title": "first", "acceptance_criteria": ["a"]},
        {"id": "task-002", "title": "second", "dependencies": ["task-001"],
         "acceptance_criteria": ["b"]},
    ]}
    p = tmp_path / "tasks.json"
    p.write_text(json.dumps(data))
    return load_manifest(p)


def test_load_plan_captures_baseline_and_empty_state(tmp_path):
    repo = _repo(tmp_path)
    pdir = tmp_path / "plandir"
    workflow.load_plan(repo, pdir, _manifest(tmp_path))
    state = workflow.read_state(pdir)
    assert state["completed"] == []
    assert len(state["baseline"]) == 40
    assert (pdir / "manifest.json").exists()


def test_complete_marks_done_and_auto_commits(tmp_path):
    repo = _repo(tmp_path)
    pdir = tmp_path / "plandir"
    workflow.load_plan(repo, pdir, _manifest(tmp_path))
    (repo / "feature.py").write_text("def f(): return 1\n")
    workflow.complete(repo, pdir, "task-001", "first")
    assert "task-001" in workflow.read_state(pdir)["completed"]
    last_msg = _git(repo, "log", "-1", "--format=%s").stdout.strip()
    assert "task-001" in last_msg and "first" in last_msg


def test_complete_without_changes_does_not_commit(tmp_path):
    repo = _repo(tmp_path)
    pdir = tmp_path / "plandir"
    workflow.load_plan(repo, pdir, _manifest(tmp_path))
    before = _git(repo, "rev-list", "--count", "HEAD").stdout.strip()
    workflow.complete(repo, pdir, "task-001", "first")
    after = _git(repo, "rev-list", "--count", "HEAD").stdout.strip()
    assert before == after
    assert "task-001" in workflow.read_state(pdir)["completed"]


def test_verify_exports_diff_since_baseline(tmp_path):
    repo = _repo(tmp_path)
    pdir = tmp_path / "plandir"
    workflow.load_plan(repo, pdir, _manifest(tmp_path))
    (repo / "feature.py").write_text("def f(): return 1\n")
    workflow.complete(repo, pdir, "task-001", "first")
    out = workflow.verify(repo, pdir)
    assert "feature.py" in out["diff"]
    assert out["manifest"]["feature"] == "F"
    assert out["completed"] == ["task-001"]


def test_load_plan_on_non_git_dir_raises(tmp_path):
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    with pytest.raises(RuntimeError):
        workflow.load_plan(not_a_repo, tmp_path / "pd", _manifest(tmp_path))


def test_load_plan_writes_phase_executing(tmp_path):
    repo = _repo(tmp_path)
    pdir = tmp_path / "plandir"
    workflow.load_plan(repo, pdir, _manifest(tmp_path))
    assert workflow.read_phase(pdir) == "executing"


def test_verify_writes_phase_verifying(tmp_path):
    repo = _repo(tmp_path)
    pdir = tmp_path / "plandir"
    workflow.load_plan(repo, pdir, _manifest(tmp_path))
    workflow.verify(repo, pdir)
    assert workflow.read_phase(pdir) == "verifying"


def test_read_phase_returns_none_when_absent(tmp_path):
    pdir = tmp_path / "plandir"
    pdir.mkdir()
    assert workflow.read_phase(pdir) is None


def test_verify_does_not_overwrite_done_phase(tmp_path):
    repo = _repo(tmp_path)
    pdir = tmp_path / "plandir"
    m = _manifest(tmp_path)
    workflow.load_plan(repo, pdir, m)
    # complete all tasks so phase becomes "done"
    workflow.complete(repo, pdir, "task-001", "first")
    # manually write "done" phase as plan_complete CLI would
    workflow.write_phase(pdir, "done")
    # verify should not overwrite "done"
    workflow.verify(repo, pdir)
    assert workflow.read_phase(pdir) == "done"


def test_load_plan_snapshot_keeps_task_context(tmp_path):
    repo = _repo(tmp_path)
    pdir = tmp_path / "plandir"
    data = {"feature": "F", "tasks": [
        {"id": "t", "title": "T", "acceptance_criteria": ["a"],
         "context": {"refs": [{"file": "a.py", "line": 1, "symbol": "f"}]}}]}
    p = tmp_path / "tasks.json"
    p.write_text(json.dumps(data))
    workflow.load_plan(repo, pdir, load_manifest(p))
    snap = json.loads((pdir / "manifest.json").read_text())
    assert snap["tasks"][0]["context"] == data["tasks"][0]["context"]


def test_complete_commits_only_task_files_and_reports_leftovers(tmp_path):
    repo = _repo(tmp_path)
    pdir = tmp_path / "plandir"
    workflow.load_plan(repo, pdir, _manifest(tmp_path))
    (repo / "feature.py").write_text("def f(): return 1\n")
    (repo / "stray.txt").write_text("not mine\n")
    leftovers = workflow.complete(repo, pdir, "task-001", "first", files=["feature.py"])
    committed = _git(repo, "show", "--name-only", "--format=", "HEAD").stdout.split()
    assert committed == ["feature.py"]
    assert leftovers == ["stray.txt"]


def test_complete_with_files_but_no_changes_does_not_commit(tmp_path):
    repo = _repo(tmp_path)
    pdir = tmp_path / "plandir"
    workflow.load_plan(repo, pdir, _manifest(tmp_path))
    (repo / "stray.txt").write_text("not mine\n")
    before = _git(repo, "rev-list", "--count", "HEAD").stdout.strip()
    workflow.complete(repo, pdir, "task-001", "first", files=["feature.py"])
    assert _git(repo, "rev-list", "--count", "HEAD").stdout.strip() == before


def test_load_plan_clears_previous_apply_results(tmp_path):
    repo = _repo(tmp_path)
    pdir = tmp_path / "plandir"
    pdir.mkdir()
    (pdir / "results.json").write_text('{"tasks": [], "file_owner": {"a.py": "old"}}')
    workflow.load_plan(repo, pdir, _manifest(tmp_path))
    assert not (pdir / "results.json").exists()
