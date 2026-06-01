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

External contributors must keep contributions brand-neutral. Do not reference Torres Atlantic internal products, private repositories, customer names, or non-public infrastructure in code, comments, tests, or docs. Forge ships under the public `tolvi-labs` brand only.
