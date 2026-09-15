# Contributing to Forge

Forge is part of the Tolvi Labs family of open-source developer tools.

## Development setup

```bash
git clone https://github.com/tolvi-labs/forge
cd forge
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
```

## Conventions

- Match the existing code style. Run `ruff check .` and `ruff format .` before committing.
- New functions get a test. New CLI commands get a `CliRunner` test.
- Keep files focused: one clear responsibility per module.

## Brand isolation

All content in this repo is brand-neutral. The single exception is the [`NOTICE`](./NOTICE) file, which carries the project's attribution.

**Do not reference** parent organizations, sibling products, customer names, private repositories, or non-public infrastructure anywhere else, including code, comments, tests, docs, commit messages, branch names, or PR descriptions. Forge ships under the public `tolvi-labs` brand only.
