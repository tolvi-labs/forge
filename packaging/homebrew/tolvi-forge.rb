# Homebrew formula for tolvi-forge (staged here; copied into the public
# homebrew-tap at release time — see RELEASE.md).
#
# Why pip-into-venv instead of a vendored `resource`-per-dependency formula:
# forge's dependency tree resolves to ~259 packages (chromadb pulls onnxruntime,
# grpcio, opentelemetry, the kubernetes client, and more). Vendoring 259 resource
# blocks and regenerating them on every bump is impractical and brittle, so the
# formula installs the published package into an isolated venv and lets pip
# resolve the tree at install time. This is standard for heavy Python CLIs in a
# custom tap (it is not Homebrew-core-eligible, which is fine — this is a tap).
#
# RELEASE TODO (per version): set `version`, and set `sha256` to the hash of the
# PyPI sdist (shasum -a 256 of tolvi_forge-<version>.tar.gz).
class TolviForge < Formula
  include Language::Python::Virtualenv

  desc "Local-first AI development: Claude plans, a tuned local model implements, vault-fed"
  homepage "https://tolvilabs.com/forge"
  version "0.1.0"
  url "https://files.pythonhosted.org/packages/source/t/tolvi-forge/tolvi_forge-#{version}.tar.gz"
  sha256 "REPLACE_AT_RELEASE_WITH_SDIST_SHA256"
  license "Apache-2.0"

  depends_on "python@3.12"
  depends_on "ollama" # forge drives a local Ollama; `forge start` pulls the models

  def install
    virtualenv_create(libexec, "python3.12")
    # Build + install the sdist into the venv; pip resolves the full tree from PyPI.
    system libexec/"bin/pip", "install", "."
    bin.install_symlink libexec/"bin/forge"
  end

  def caveats
    <<~EOS
      Forge drives a local Ollama and its own tuned model. After installing, run:
        forge start     # brings Ollama up and pulls/builds the local models
        forge doctor    # verifies the setup
    EOS
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/forge --version")
  end
end
