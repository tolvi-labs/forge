import json
import subprocess

import pytest

from forge.agents import apply
from forge.chunker.chunk import count_tokens
from forge.plan import outcomes, workflow
from forge.plan.manifest import Manifest


def test_context_budget_uses_smaller_window_minus_reserve_and_margin():
    # min(65536, 32768) = 32768; minus 8192 reserve = 24576; minus 10% = 22118
    assert apply.context_budget(65536, 32768, reply_reserve=8192, margin=0.10) == 22118


def test_context_budget_without_hardware_window_uses_profile():
    assert apply.context_budget(65536, None, reply_reserve=8192, margin=0.0) == 57344


def _task(files=("src/a.py",), context=None):
    return Manifest.from_dict({"feature": "F", "tasks": [
        {"id": "t1", "title": "add g", "files": list(files),
         "acceptance_criteria": ["g returns 2"], "context": context or {}},
    ]}).task("t1")


CTX = {
    "interfaces": {"consumes": ["f() -> int"], "produces": ["g() -> int"]},
    "decisions": [{"path": "vault/decisions/d.md", "title": "Keep it pure", "rationale": "no IO"}],
    "refs": [{"file": "src/a.py", "line": 1, "symbol": "f"}],
}
HIT = {"file_path": "src/b.py", "start_line": 1, "end_line": 2,
       "symbol_name": "h", "content": "def h(): pass"}


def test_prompt_has_edit_instructions_task_and_full_file_contents():
    prompt = apply.build_prompt(_task(), {"src/a.py": "def f():\n    return 1\n"},
                                rag_hits=[], budget=10_000)
    assert "SEARCH" in prompt and "REPLACE" in prompt
    assert "add g" in prompt and "g returns 2" in prompt
    assert "def f():\n    return 1\n" in prompt


def test_prompt_marks_missing_file_as_new():
    prompt = apply.build_prompt(_task(), {"src/a.py": None}, rag_hits=[], budget=10_000)
    assert "src/a.py (new file)" in prompt


def test_prompt_includes_context_and_rag_when_they_fit():
    prompt = apply.build_prompt(_task(context=CTX), {"src/a.py": "x = 1\n"},
                                rag_hits=[HIT], budget=10_000)
    assert "g() -> int" in prompt
    assert "Keep it pure" in prompt and "no IO" in prompt
    assert "src/a.py:1" in prompt
    assert "def h(): pass" in prompt


def test_prompt_drops_rag_before_context_when_tight():
    base = apply.build_prompt(_task(context=CTX), {"src/a.py": "x = 1\n"},
                              rag_hits=[], budget=10_000)
    prompt = apply.build_prompt(_task(context=CTX), {"src/a.py": "x = 1\n"},
                                rag_hits=[HIT], budget=count_tokens(base) + 2)
    assert "Keep it pure" in prompt
    assert "def h(): pass" not in prompt


def test_prompt_is_none_when_files_alone_exceed_budget():
    big = "x = 1\n" * 5000
    assert apply.build_prompt(_task(), {"src/a.py": big}, rag_hits=[], budget=500) is None


def test_prompt_carries_retry_feedback():
    prompt = apply.build_prompt(_task(), {"src/a.py": "x = 1\n"}, rag_hits=[],
                                budget=10_000, feedback="patch does not apply")
    assert "patch does not apply" in prompt


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True)


def _repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "tester")
    (repo / "src" / "a.py").write_text("def f():\n    return 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


GOOD_EDIT = """src/a.py
<<<<<<< SEARCH
def f():
    return 1
=======
def f():
    return 1


def g():
    return 2
>>>>>>> REPLACE
"""

# the same edit, but the SEARCH lines carry trailing whitespace the file does not have
WS_EDIT = GOOD_EDIT.replace("def f():\n    return 1\n=======", "def f():  \n    return 1 \n=======")


def test_parse_edits_reads_path_search_and_replace():
    text = f"Here you go:\n```\n{GOOD_EDIT}```\nadds g"
    assert apply.parse_edits(text) == [
        ("src/a.py", "def f():\n    return 1\n",
         "def f():\n    return 1\n\n\ndef g():\n    return 2\n")]


def test_parse_edits_strips_path_decoration_and_reads_several_blocks():
    text = ("**`src/a.py`**\n<<<<<<< SEARCH\nx = 1\n=======\nx = 2\n>>>>>>> REPLACE\n"
            "README.md\n<<<<<<< SEARCH\n=======\n# Demo\n>>>>>>> REPLACE\n")
    assert apply.parse_edits(text) == [("src/a.py", "x = 1\n", "x = 2\n"),
                                       ("README.md", "", "# Demo\n")]


def test_parse_edits_empty_when_no_blocks():
    assert apply.parse_edits("def g():\n    return 2\n") == []


def test_apply_edits_exact_match():
    files = {"src/a.py": "def f():\n    return 1\n"}
    new, tolerant, error = apply.apply_edits(files, apply.parse_edits(GOOD_EDIT))
    assert error == "" and tolerant is False
    assert new["src/a.py"].endswith("def g():\n    return 2\n")


def test_apply_edits_whitespace_tolerant_match():
    files = {"src/a.py": "def f():\n    return 1\n"}
    new, tolerant, error = apply.apply_edits(files, apply.parse_edits(WS_EDIT))
    assert error == "" and tolerant is True
    assert "def g():" in new["src/a.py"]


def test_apply_edits_creates_new_file_from_empty_search():
    new, _, error = apply.apply_edits({"README.md": None}, [("README.md", "", "# Demo\n")])
    assert error == "" and new["README.md"] == "# Demo\n"


def test_apply_edits_errors_when_search_missing():
    _, _, error = apply.apply_edits({"src/a.py": "x = 1\n"}, [("src/a.py", "y = 2\n", "z\n")])
    assert "not found" in error


def test_apply_edits_errors_when_search_ambiguous():
    _, _, error = apply.apply_edits({"src/a.py": "x = 1\nx = 1\n"},
                                    [("src/a.py", "x = 1\n", "x = 2\n")])
    assert "2 places" in error


def test_apply_edits_rejects_empty_search_on_existing_file():
    _, _, error = apply.apply_edits({"src/a.py": "x = 1\n"}, [("src/a.py", "", "y\n")])
    assert error


def test_review_verdict_uses_last_marker():
    assert apply.review_approved("Looks fine. APPROVE")
    assert not apply.review_approved("I would APPROVE except a bug.\nREQUEST_CHANGES")
    assert not apply.review_approved("no verdict here")


def _plan(tmp_path, repo, tasks):
    pdir = tmp_path / "plandir"
    manifest = Manifest.from_dict({"feature": "Add G", "tasks": tasks})
    workflow.load_plan(repo, pdir, manifest)
    return pdir, manifest


T1 = {"id": "t1", "title": "add g", "files": ["src/a.py"], "acceptance_criteria": ["g returns 2"]}
T2 = {"id": "t2", "title": "use g", "files": ["src/a.py"], "dependencies": ["t1"],
      "acceptance_criteria": ["h calls g"]}
T3 = {"id": "t3", "title": "readme", "files": ["README.md"], "acceptance_criteria": ["exists"]}
README_EDIT = "README.md\n<<<<<<< SEARCH\n=======\n# Demo\n>>>>>>> REPLACE\n"


def _scripted(code_answers, review_answers=None, stats=None):
    """A fake generate that hands out scripted answers per role, in order."""
    code = list(code_answers)
    review = list(review_answers or [])
    calls = []

    def gen(prompt, **kwargs):
        role = "review" if "Reviewer" in prompt else "code"
        calls.append(role)
        if kwargs.get("stats_callback") and stats:
            kwargs["stats_callback"](stats)
        if role == "review":
            return review.pop(0) if review else "APPROVE"
        return code.pop(0)
    gen.calls = calls
    return gen


def _fenced(edit):
    return f"```\n{edit}```\nadds it"


def test_branch_name_slugs_the_feature():
    assert apply.branch_name("Add G: the Thing!") == "forge/add-g-the-thing"


def test_prepare_branch_refuses_dirty_tree(tmp_path):
    repo = _repo(tmp_path)
    (repo / "stray.txt").write_text("x\n")
    baseline = _git(repo, "rev-parse", "HEAD").stdout.strip()
    with pytest.raises(apply.ApplyError, match="stray.txt"):
        apply.prepare_branch(repo, "forge/x", baseline)


def test_prepare_branch_creates_then_resumes(tmp_path):
    repo = _repo(tmp_path)
    baseline = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert apply.prepare_branch(repo, "forge/x", baseline) == "created"
    assert _git(repo, "branch", "--show-current").stdout.strip() == "forge/x"
    assert apply.prepare_branch(repo, "forge/x", baseline) == "resumed"


def test_prepare_branch_errors_when_branch_exists_elsewhere(tmp_path):
    repo = _repo(tmp_path)
    baseline = _git(repo, "rev-parse", "HEAD").stdout.strip()
    apply.prepare_branch(repo, "forge/x", baseline)
    _git(repo, "checkout", "-q", "main")
    with pytest.raises(apply.ApplyError, match="already exists"):
        apply.prepare_branch(repo, "forge/x", baseline)


def test_run_apply_commits_approved_diff_on_branch(tmp_path):
    repo = _repo(tmp_path)
    pdir, manifest = _plan(tmp_path, repo, [T1])
    results = apply.run_apply(repo, pdir, manifest, generate_fn=_scripted([_fenced(GOOD_EDIT)]),
                              budget=10_000)
    assert _git(repo, "branch", "--show-current").stdout.strip() == "forge/add-g"
    assert _git(repo, "log", "-1", "--format=%s").stdout.strip() == "[t1] add g"
    assert "t1" in workflow.read_state(pdir)["completed"]
    entry = results["tasks"][0]
    assert entry["status"] == "applied" and entry["attempts"] == 1
    assert entry["tolerant"] is False and entry["verdict"] == "APPROVE"
    assert entry["diffstat"] == {"added": 4, "deleted": 0, "files": ["src/a.py"]}
    assert json.loads((pdir / "results.json").read_text()) == results


def test_run_apply_retries_once_with_feedback(tmp_path):
    repo = _repo(tmp_path)
    pdir, manifest = _plan(tmp_path, repo, [T1])
    gen = _scripted(["here is g: def g(): return 2", _fenced(GOOD_EDIT)])
    results = apply.run_apply(repo, pdir, manifest, generate_fn=gen, budget=10_000)
    assert results["tasks"][0]["status"] == "applied"
    assert results["tasks"][0]["attempts"] == 2


def test_run_apply_records_tolerant_pass(tmp_path):
    repo = _repo(tmp_path)
    pdir, manifest = _plan(tmp_path, repo, [T1])
    results = apply.run_apply(repo, pdir, manifest,
                              generate_fn=_scripted([_fenced(WS_EDIT)]), budget=10_000)
    assert results["tasks"][0]["tolerant"] is True


def test_run_apply_rejects_out_of_scope_diff(tmp_path):
    repo = _repo(tmp_path)
    pdir, manifest = _plan(tmp_path, repo, [T1])
    both = GOOD_EDIT + README_EDIT
    results = apply.run_apply(repo, pdir, manifest,
                              generate_fn=_scripted([_fenced(both), _fenced(both)]), budget=10_000)
    entry = results["tasks"][0]
    assert entry["status"] == "rejected" and "README.md" in entry["reason"]
    assert not (repo / "README.md").exists()
    assert _git(repo, "status", "--porcelain").stdout == ""


def test_run_apply_rejects_after_reviewer_requests_changes_twice(tmp_path):
    repo = _repo(tmp_path)
    pdir, manifest = _plan(tmp_path, repo, [T1])
    gen = _scripted([_fenced(GOOD_EDIT)] * 2, ["bug. REQUEST_CHANGES"] * 2)
    results = apply.run_apply(repo, pdir, manifest, generate_fn=gen, budget=10_000)
    entry = results["tasks"][0]
    assert entry["status"] == "rejected" and entry["verdict"] == "REQUEST_CHANGES"
    assert "def g" not in (repo / "src" / "a.py").read_text()
    assert _git(repo, "status", "--porcelain").stdout == ""


def test_run_apply_rejects_oversized_task_without_calling_model(tmp_path):
    repo = _repo(tmp_path)
    pdir, manifest = _plan(tmp_path, repo, [T1])
    gen = _scripted([])
    results = apply.run_apply(repo, pdir, manifest, generate_fn=gen, budget=50)
    assert results["tasks"][0]["status"] == "rejected"
    assert "too large" in results["tasks"][0]["reason"]
    assert gen.calls == []


def test_run_apply_skips_dependents_of_rejected_and_continues_independent(tmp_path):
    repo = _repo(tmp_path)
    pdir, manifest = _plan(tmp_path, repo, [T1, T2, T3])
    gen = _scripted(["no diff", "still no diff", _fenced(README_EDIT)])
    results = apply.run_apply(repo, pdir, manifest, generate_fn=gen, budget=10_000)
    status = {t["id"]: t["status"] for t in results["tasks"]}
    assert status == {"t1": "rejected", "t2": "skipped", "t3": "applied"}
    assert "t1" in [t["reason"] for t in results["tasks"] if t["id"] == "t2"][0]


def test_run_apply_auto_records_rejected_outcome(tmp_path):
    repo = _repo(tmp_path)
    pdir, manifest = _plan(tmp_path, repo, [T1])
    apply.run_apply(repo, pdir, manifest, generate_fn=_scripted(["nope", "nope"]), budget=10_000)
    rec = outcomes.read_outcomes(pdir)[0]
    assert rec["task_id"] == "t1" and rec["accepted"] == "rejected"
    assert rec["failure_reason"]


def test_run_apply_resume_skips_completed_tasks(tmp_path):
    repo = _repo(tmp_path)
    pdir, manifest = _plan(tmp_path, repo, [T1, T3])
    apply.run_apply(repo, pdir, manifest,
                    generate_fn=_scripted([_fenced(GOOD_EDIT), "nope", "nope"]), budget=10_000)
    gen = _scripted([_fenced(README_EDIT)])
    results = apply.run_apply(repo, pdir, manifest, generate_fn=gen, budget=10_000)
    assert {t["id"]: t["status"] for t in results["tasks"]} == {"t1": "applied", "t3": "applied"}
    assert gen.calls == ["code", "review"]


def test_run_apply_counts_tokens_and_forwards_stats(tmp_path):
    repo = _repo(tmp_path)
    pdir, manifest = _plan(tmp_path, repo, [T1])
    logged = []
    stats = {"tokens_in": 100, "tokens_out": 20, "duration_ms": 5.0, "tokens_per_sec": 4.0}
    results = apply.run_apply(repo, pdir, manifest,
                              generate_fn=_scripted([_fenced(GOOD_EDIT)], stats=stats),
                              budget=10_000, log_fn=logged.append)
    assert results["tasks"][0]["tokens"] == 240   # code + review call
    assert len(logged) == 2


def test_run_apply_tracks_model_tip_and_last_editor(tmp_path):
    repo = _repo(tmp_path)
    pdir, manifest = _plan(tmp_path, repo, [T1, T3])
    results = apply.run_apply(repo, pdir, manifest,
                              generate_fn=_scripted([_fenced(GOOD_EDIT), _fenced(README_EDIT)]),
                              budget=10_000)
    assert results["model_tip"] == _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert results["file_owner"] == {"src/a.py": "t1", "README.md": "t3"}


def test_run_apply_clears_auto_rejection_when_task_later_applies(tmp_path):
    repo = _repo(tmp_path)
    pdir, manifest = _plan(tmp_path, repo, [T1])
    apply.run_apply(repo, pdir, manifest, generate_fn=_scripted(["nope", "nope"]), budget=10_000)
    apply.run_apply(repo, pdir, manifest, generate_fn=_scripted([_fenced(GOOD_EDIT)]),
                    budget=10_000)
    assert outcomes.read_outcomes(pdir) == []


def test_run_apply_reverts_new_file_when_reviewer_rejects(tmp_path):
    repo = _repo(tmp_path)
    pdir, manifest = _plan(tmp_path, repo, [T3])
    gen = _scripted([_fenced(README_EDIT)] * 2, ["REQUEST_CHANGES"] * 2)
    apply.run_apply(repo, pdir, manifest, generate_fn=gen, budget=10_000)
    assert not (repo / "README.md").exists()
    assert _git(repo, "status", "--porcelain").stdout == ""


def test_run_apply_reviewer_sees_a_real_unified_diff(tmp_path):
    repo = _repo(tmp_path)
    pdir, manifest = _plan(tmp_path, repo, [T1])
    seen = []

    def gen(prompt, **kwargs):
        if "Reviewer" in prompt:
            seen.append(prompt)
            return "APPROVE"
        return _fenced(GOOD_EDIT)
    apply.run_apply(repo, pdir, manifest, generate_fn=gen, budget=10_000)
    assert "+++ b/src/a.py" in seen[0] and "+def g():" in seen[0]
