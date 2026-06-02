from pathlib import Path
from forge.vault.loader import load_vault

FIXTURE_REPO = Path(__file__).parent.parent / "fixtures"


def _repo_with_vault(tmp_path: Path) -> Path:
    import shutil
    repo = tmp_path / "repo"
    (repo / "vault").mkdir(parents=True)
    shutil.copytree(FIXTURE_REPO / "sample-vault", repo / "vault", dirs_exist_ok=True)
    return repo


def test_load_vault_returns_none_when_absent(tmp_path):
    assert load_vault(tmp_path / "no-repo") is None


def test_load_vault_includes_active_excludes_superseded(tmp_path):
    repo = _repo_with_vault(tmp_path)
    block = load_vault(repo)
    assert block is not None
    assert "use-postgres" in block
    assert "result-type" in block
    assert "old-auth" not in block


def test_load_vault_prefers_tldr(tmp_path):
    repo = _repo_with_vault(tmp_path)
    block = load_vault(repo)
    assert "pgvector + JSON tipped it" in block
    assert "Drizzle migrations" not in block


def test_load_vault_respects_token_budget(tmp_path):
    repo = _repo_with_vault(tmp_path)
    tiny = load_vault(repo, max_tokens=5)
    assert tiny is None or len(tiny) < 200
