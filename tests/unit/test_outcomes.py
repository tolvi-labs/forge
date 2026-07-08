from forge.plan import outcomes


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
