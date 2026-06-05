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


def _repo_with_decision(tmp_path: Path, name: str, text: str) -> Path:
    repo = tmp_path / "repo"
    (repo / "vault" / "decisions").mkdir(parents=True)
    (repo / "vault" / "decisions" / name).write_text(text)
    return repo


def test_load_vault_excludes_capitalized_status(tmp_path):
    # status filtering must be case-insensitive — a capitalized Superseded must
    # NOT leak into the model's context.
    repo = _repo_with_decision(
        tmp_path, "x.md",
        "---\nstatus: Superseded\n---\n\n## Why\nleaks-through\n",
    )
    assert load_vault(repo) is None


def test_load_vault_excludes_status_with_inline_comment(tmp_path):
    repo = _repo_with_decision(
        tmp_path, "x.md",
        "---\nstatus: deprecated # legacy\n---\n\n## Why\nleaks-through\n",
    )
    assert load_vault(repo) is None


def test_load_vault_tolerates_leading_blank_line(tmp_path):
    # a leading blank line before --- must not blank the frontmatter (which would
    # default status to active and leak an excluded doc)
    repo = _repo_with_decision(
        tmp_path, "x.md",
        "\n---\nstatus: draft\n---\n\n## Why\nleaks-through\n",
    )
    assert load_vault(repo) is None


def test_forge_vault_env_var_overrides_repo_root(tmp_path, monkeypatch):
    # An external vault pointed to by FORGE_VAULT is used even when the repo
    # has no vault/ directory of its own.
    external_vault = tmp_path / "external-vault"
    (external_vault / "decisions").mkdir(parents=True)
    (external_vault / "decisions" / "external-decision.md").write_text(
        "---\nstatus: active\n---\n\nexternal-vault-content\n"
    )
    monkeypatch.setenv("FORGE_VAULT", str(external_vault))
    repo_without_vault = tmp_path / "repo"
    repo_without_vault.mkdir()
    block = load_vault(repo_without_vault)
    assert block is not None
    assert "external-vault-content" in block
