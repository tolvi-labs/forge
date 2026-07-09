import json as _json
import os
import subprocess

from forge.plan import outcomes
from forge.plan.manifest import Manifest


def _git(repo, *args, when=None):
    env = dict(os.environ)
    if when:
        env["GIT_AUTHOR_DATE"] = when
        env["GIT_COMMITTER_DATE"] = when
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True, env=env)


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@e.com")
    _git(repo, "config", "user.name", "t")
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed", when="2026-07-07T12:00:00Z")
    return repo


def _task(files=None):
    return Manifest.from_dict({"feature": "F", "tasks": [
        {"id": "T3", "title": "third", "files": files or [], "acceptance_criteria": ["a"]},
    ]}).task("T3")


def _inference_log(tmp_path, *records):
    log = tmp_path / "inference.log"
    log.write_text("".join(_json.dumps(r) + "\n" for r in records))
    return log


def test_compute_metrics_no_commit_returns_zeros(tmp_path):
    repo = _repo(tmp_path)
    log = _inference_log(tmp_path)
    m = outcomes.compute_task_metrics(repo, _task(), log)
    assert m["commit"] is None
    assert m["produced_lines"] == 0 and m["rework_lines"] == 0
    assert m["churn"] == 0.0 and m["local_tokens"] == 0


def test_compute_metrics_produced_rework_and_churn(tmp_path):
    repo = _repo(tmp_path)
    # local model's committed output: 3 lines in feature.py
    (repo / "feature.py").write_text("a = 1\nb = 2\nc = 3\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "[T3] third", when="2026-07-07T12:10:00Z")
    # rework: your uncommitted fix changes 1 line on top
    (repo / "feature.py").write_text("a = 1\nb = 99\nc = 3\n")
    log = _inference_log(tmp_path)
    m = outcomes.compute_task_metrics(repo, _task(["feature.py"]), log)
    assert m["produced_lines"] == 3          # 3 insertions in the [T3] commit
    assert m["rework_lines"] == 2            # 1 line changed = 1 add + 1 delete
    assert round(m["churn"], 3) == round(2 / 3, 3)


def test_compute_metrics_token_window_uses_commit_parent(tmp_path):
    repo = _repo(tmp_path)                    # seed (parent) at 12:00:00Z
    (repo / "feature.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "[T3] third", when="2026-07-07T12:10:00Z")
    log = _inference_log(
        tmp_path,
        {"ts": "2026-07-07T11:00:00+00:00", "tokens_in": 100, "tokens_out": 100, "tokens_per_sec": 10.0, "duration_ms": 1000.0},  # before window
        {"ts": "2026-07-07T12:05:00+00:00", "tokens_in": 40, "tokens_out": 60, "tokens_per_sec": 30.0, "duration_ms": 2000.0},    # in window
        {"ts": "2026-07-07T13:00:00+00:00", "tokens_in": 100, "tokens_out": 100, "tokens_per_sec": 50.0, "duration_ms": 3000.0},  # after window
    )
    m = outcomes.compute_task_metrics(repo, _task(["feature.py"]), log)
    assert m["local_tokens"] == 100          # only the in-window record: 40 + 60
    assert m["duration_ms"] == 2000.0
    assert m["tokens_per_sec"] == 30.0


def test_read_outcomes_missing_file_returns_empty(tmp_path):
    assert outcomes.read_outcomes(tmp_path) == []


def test_append_then_read_roundtrips(tmp_path):
    outcomes.upsert_outcome(tmp_path, {"task_id": "T1", "trust": 4})
    outcomes.upsert_outcome(tmp_path, {"task_id": "T2", "trust": 3})
    recs = outcomes.read_outcomes(tmp_path)
    assert [r["task_id"] for r in recs] == ["T1", "T2"]


def test_upsert_replaces_same_task_id(tmp_path):
    outcomes.upsert_outcome(tmp_path, {"task_id": "T1", "trust": 4})
    outcomes.upsert_outcome(tmp_path, {"task_id": "T1", "trust": 1})
    recs = outcomes.read_outcomes(tmp_path)
    assert len(recs) == 1
    assert recs[0]["trust"] == 1
