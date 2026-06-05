import json
from pathlib import Path
from forge.watch import (
    WatchSession,
    discover_repos,
    read_session,
    _find_current_task_id,
    _read_last_inference,
)


def _write_plan(plan_dir: Path, *, feature="test-feat", phase="executing",
                tasks=None, completed=None):
    plan_dir.mkdir(parents=True, exist_ok=True)
    if tasks is None:
        tasks = [{"id": "t1", "title": "First task", "dependencies": []},
                 {"id": "t2", "title": "Second task", "dependencies": ["t1"]}]
    (plan_dir / "phase.json").write_text(json.dumps({"phase": phase}))
    (plan_dir / "manifest.json").write_text(json.dumps({
        "feature": feature, "stack": "python", "tasks": [
            {**t, "files": [], "acceptance_criteria": []} for t in tasks
        ],
    }))
    (plan_dir / "state.json").write_text(json.dumps({
        "baseline": "abc123", "completed": completed or [],
    }))


def test_discover_repos_returns_dirs_with_phase_json(tmp_path):
    plans = tmp_path / "plans"
    plan_a = plans / "hash_a"
    plan_b = plans / "hash_b"
    no_phase = plans / "hash_c"
    _write_plan(plan_a, feature="alpha")
    _write_plan(plan_b, feature="beta")
    no_phase.mkdir(parents=True)  # no phase.json — should be excluded

    result = discover_repos(tmp_path)

    assert len(result) == 2
    assert all(isinstance(s, WatchSession) for s in result)
    features = {s.feature for s in result}
    assert features == {"alpha", "beta"}


def test_discover_repos_returns_empty_when_plans_dir_absent(tmp_path):
    assert discover_repos(tmp_path) == []


def test_discover_repos_sorted_by_feature(tmp_path):
    plans = tmp_path / "plans"
    _write_plan(plans / "hash_z", feature="zebra")
    _write_plan(plans / "hash_a", feature="antelope")
    result = discover_repos(tmp_path)
    assert [s.feature for s in result] == ["antelope", "zebra"]


def test_read_session_reads_phase_manifest_state(tmp_path):
    plan_dir = tmp_path / "plans" / "myhash"
    _write_plan(plan_dir, feature="my-feature", phase="verifying", completed=["t1"])

    session = read_session(plan_dir, tmp_path)

    assert session.feature == "my-feature"
    assert session.phase == "verifying"
    assert session.completed == ["t1"]
    assert len(session.tasks) == 2
    assert session.tasks[0]["id"] == "t1"
    assert session.tasks[0]["title"] == "First task"


def test_read_session_context_stats(tmp_path):
    plan_dir = tmp_path / "plans" / "myhash"
    _write_plan(plan_dir)
    ctx_dir = tmp_path / "context"
    ctx_dir.mkdir()
    (ctx_dir / "myhash.json").write_text(json.dumps({"tokens_used": 1000, "tokens_budget": 65536}))

    session = read_session(plan_dir, tmp_path)

    assert session.context_stats == {"tokens_used": 1000, "tokens_budget": 65536}


def test_read_session_tolerates_missing_files(tmp_path):
    plan_dir = tmp_path / "plans" / "myhash"
    plan_dir.mkdir(parents=True)
    # No phase.json, manifest.json, or state.json

    session = read_session(plan_dir, tmp_path)

    assert session.phase is None
    assert session.feature == "unknown"
    assert session.tasks == []
    assert session.completed == []
    assert session.context_stats is None
    assert session.last_inference is None


def test_read_last_inference_returns_last_valid_line(tmp_path):
    log = tmp_path / "inference.log"
    log.write_text(
        '{"model":"m","tokens_out":10,"tokens_in":5,"tokens_per_sec":20.0,"duration_ms":500}\n'
        '{"model":"m","tokens_out":20,"tokens_in":8,"tokens_per_sec":35.5,"duration_ms":563}\n'
    )
    result = _read_last_inference(log)
    assert result["tokens_out"] == 20
    assert result["tokens_per_sec"] == 35.5


def test_read_last_inference_absent_log_returns_none(tmp_path):
    assert _read_last_inference(tmp_path / "no.log") is None


def test_find_current_task_id_empty_completed_returns_root():
    tasks = [
        {"id": "t1", "title": "Root", "dependencies": []},
        {"id": "t2", "title": "Child", "dependencies": ["t1"]},
    ]
    assert _find_current_task_id(tasks, set()) == "t1"


def test_find_current_task_id_first_unblocked():
    tasks = [
        {"id": "t1", "title": "A", "dependencies": []},
        {"id": "t2", "title": "B", "dependencies": ["t1"]},
        {"id": "t3", "title": "C", "dependencies": ["t1"]},
    ]
    # t1 done — t2 is first unblocked
    assert _find_current_task_id(tasks, {"t1"}) == "t2"


def test_find_current_task_id_all_done_returns_none():
    tasks = [{"id": "t1", "title": "A", "dependencies": []}]
    assert _find_current_task_id(tasks, {"t1"}) is None


def test_build_display_idle_when_no_sessions():
    from rich.console import Console
    from forge.watch import build_display
    console = Console(width=60)
    renderable = build_display([], 0)
    with console.capture() as cap:
        console.print(renderable)
    output = cap.get()
    assert "IDLE" in output
    assert "no active plan" in output


def test_build_display_shows_phase(tmp_path):
    from rich.console import Console
    from forge.watch import build_display
    plan_dir = tmp_path / "plans" / "h1"
    _write_plan(plan_dir, feature="my-plan", phase="executing")
    plan_dir_b = tmp_path / "plans" / "h2"
    _write_plan(plan_dir_b, feature="other", phase="done")
    sessions = discover_repos(tmp_path)

    console = Console(width=60)
    with console.capture() as cap:
        console.print(build_display(sessions, 0))
    output = cap.get()
    assert "EXECUTING" in output


def test_build_display_tab_bar_appears_for_multiple_sessions(tmp_path):
    from rich.console import Console
    from forge.watch import build_display
    _write_plan(tmp_path / "plans" / "h1", feature="alpha")
    _write_plan(tmp_path / "plans" / "h2", feature="beta")
    sessions = discover_repos(tmp_path)

    console = Console(width=60)
    with console.capture() as cap:
        console.print(build_display(sessions, 0))
    output = cap.get()
    assert "alpha" in output
    assert "beta" in output
    assert "← / →" in output


def test_build_display_no_tab_bar_for_single_session(tmp_path):
    from rich.console import Console
    from forge.watch import build_display
    _write_plan(tmp_path / "plans" / "h1", feature="alpha")
    sessions = discover_repos(tmp_path)

    console = Console(width=60)
    with console.capture() as cap:
        console.print(build_display(sessions, 0))
    assert "← / →" not in cap.get()


def test_build_display_tasks_show_completion_state(tmp_path):
    from rich.console import Console
    from forge.watch import build_display
    plan_dir = tmp_path / "plans" / "h1"
    _write_plan(plan_dir, completed=["t1"])
    sessions = [read_session(plan_dir, tmp_path)]

    console = Console(width=60)
    with console.capture() as cap:
        console.print(build_display(sessions, 0))
    output = cap.get()
    assert "First task" in output
    assert "Second task" in output
    assert "✓" in output   # t1 is completed
    assert "→" in output   # t2 is the current task (t1 done, t2 unblocked)


def test_build_display_metrics_panel_absent_data(tmp_path):
    from rich.console import Console
    from forge.watch import build_display
    plan_dir = tmp_path / "plans" / "h1"
    _write_plan(plan_dir)
    sessions = [read_session(plan_dir, tmp_path)]

    console = Console(width=60)
    with console.capture() as cap:
        console.print(build_display(sessions, 0))
    assert "no inference data" in cap.get()


def test_build_display_metrics_shows_tokens_per_sec(tmp_path):
    from rich.console import Console
    from forge.watch import build_display
    plan_dir = tmp_path / "plans" / "h1"
    _write_plan(plan_dir)
    (tmp_path / "inference.log").write_text(
        '{"model":"m","tokens_out":50,"tokens_in":20,"tokens_per_sec":42.0,"duration_ms":1190}\n'
    )
    sessions = [read_session(plan_dir, tmp_path)]

    console = Console(width=60)
    with console.capture() as cap:
        console.print(build_display(sessions, 0))
    assert "42.0" in cap.get()


def test_build_display_done_phase(tmp_path):
    from rich.console import Console
    from forge.watch import build_display
    plan_dir = tmp_path / "plans" / "h1"
    _write_plan(plan_dir, phase="done")
    sessions = [read_session(plan_dir, tmp_path)]
    console = Console(width=60)
    with console.capture() as cap:
        console.print(build_display(sessions, 0))
    assert "DONE" in cap.get()


def test_build_display_metrics_shows_context_bar(tmp_path):
    from rich.console import Console
    from forge.watch import build_display
    plan_dir = tmp_path / "plans" / "myhash"
    _write_plan(plan_dir)
    ctx_dir = tmp_path / "context"
    ctx_dir.mkdir()
    (ctx_dir / "myhash.json").write_text(
        '{"tokens_used": 8192, "tokens_budget": 65536}'
    )
    sessions = [read_session(plan_dir, tmp_path)]

    console = Console(width=60)
    with console.capture() as cap:
        console.print(build_display(sessions, 0))
    output = cap.get()
    assert "8.0k" in output
    assert "65k" in output
    assert "█" in output
    assert "░" in output
