# Releasing Forge

Forge ships to **PyPI** (primary, `pip install tolvi-forge`) and **Homebrew**
(`brew install tolvi-labs/tap/tolvi-forge`). Nothing publishes automatically on
push — cutting a GitHub Release is the deliberate trigger.

## One-time setup

- **PyPI Trusted Publishing** (no API token): on PyPI, add a pending publisher
  for project `tolvi-forge` with owner `tolvi-labs`, repo `forge`, workflow
  `release.yml`, environment `pypi`. See https://docs.pypi.org/trusted-publishers/
- **GitHub environment**: create a `pypi` environment on the `forge` repo (used
  by the publish job).

## Per-release steps

1. **Bump the version** in `pyproject.toml` and move the `[Unreleased]` section
   of `CHANGELOG.md` under a new `## [X.Y.Z] - <date>` heading.
2. **Tag and release**: create a GitHub Release with tag `vX.Y.Z`. The `Release`
   workflow builds the sdist + wheel, checks the tag matches the version, and
   publishes to PyPI via Trusted Publishing. (`pip install tolvi-forge` is now live.)
3. **Update the Homebrew formula** (`packaging/homebrew/tolvi-forge.rb`):
   - Set `version` to `X.Y.Z`.
   - Set `sha256` to the hash of the PyPI sdist:
     ```
     curl -sL https://files.pythonhosted.org/packages/source/t/tolvi-forge/tolvi_forge-X.Y.Z.tar.gz | shasum -a 256
     ```
4. **Publish to the tap**: copy the updated formula into the public
   `homebrew-tap` repo as `Formula/tolvi-forge.rb`, add it to the tap README's
   "What's in this tap" table, and commit. (`brew install` is now live.)

## Notes

- The formula installs into an isolated venv and lets pip resolve forge's ~259-package
  dependency tree at install time, rather than vendoring a `resource` block per
  dependency. See the header comment in the formula.
- Homebrew installs the CLI only; `forge start` still pulls Ollama and the local
  models on first run.
