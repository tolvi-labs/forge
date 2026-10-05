# Releasing Forge

Forge ships to **PyPI** (`pipx install tolvi-forge`). There is no Homebrew formula yet; see "Why there is no Homebrew formula yet" below. Nothing publishes automatically on push — cutting a GitHub Release is the deliberate trigger.

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
Homebrew is not a release step yet: see below.

## Why there is no Homebrew formula yet

Forge ships on PyPI only (`pipx install tolvi-forge`, as the README says). A formula is staged in `packaging/homebrew/tolvi-forge.rb` but is not published to the tap, because current Homebrew (tested with 7.0.8 on 2026-10-05) leaves no compliant way to package a dependency tree this heavy:

- Vendoring a `resource` per dependency (~259 of them) fails, because Homebrew's pip helper builds every package from source and `onnxruntime` (via `chromadb`) publishes no sdist.
- Installing the published package into a venv inside the keg builds, but `brew install` then fails while fixing linkage: Homebrew rewrites the install name of every Mach-O file in the keg, and prebuilt wheels such as `orjson` have no header room for that.
- Building the venv in `post_install` under `var/` works and passes `brew test`, but `post_install` is deprecated in favour of `post_install_steps`, which is declarative and cannot run pip. That formula fails `brew audit` and stops working when Homebrew removes `post_install`.

Revisit if Homebrew adds a way to run a command after install, or if Forge's dependency tree loses its binary-only packages. If it is ever published, set `url` to the sdist's "Source" URL from PyPI and `sha256` to its hash, and check it with `brew style` and `brew audit --strict --online` from a tap first.

## Notes

- However Forge is installed, it is the CLI only; `forge start` still pulls Ollama and the local models on first run.
