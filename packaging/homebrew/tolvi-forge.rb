# Homebrew formula for tolvi-forge: STAGED, NOT PUBLISHED. PyPI (pipx) is the
# distribution channel; see "Why there is no Homebrew formula yet" in RELEASE.md.
#
# Tested against Homebrew 7.0.8 on 2026-10-05 (forge 0.3.0):
# - A venv inside the keg builds, but `brew install` then fails: Homebrew rewrites the
#   install name of every Mach-O file in a keg, and prebuilt wheels (orjson first) have
#   no header room for it ("Failed to fix install linkage").
# - Vendoring a `resource` per dependency (~259) is not workable either: Homebrew's pip
#   helper builds from source with --no-binary=:all:, and onnxruntime has no sdist.
# - So this version builds the venv in post_install under var/, outside the keg. It
#   installs and passes `brew test`, but `post_install` is deprecated in favour of the
#   declarative `post_install_steps`, which cannot run pip, so `brew audit` fails and it
#   stops working once Homebrew removes `post_install`.
class TolviForge < Formula
  include Language::Python::Virtualenv

  desc "Local-first AI development: a tuned local model implements, fed by your vault"
  homepage "https://tolvilabs.com/forge"
  url "https://files.pythonhosted.org/packages/6e/88/4f812c4933d55fe5dfe3103fa2fbce7149258f3fa72d7dc4d6c3ec6bb81b/tolvi_forge-0.3.0.tar.gz"
  sha256 "31cf57844087fa1c130135ddb1a12f042fb0067abb6d30283bac32c9dc7ec9f3"
  license "Apache-2.0"

  depends_on "ollama" # forge drives a local Ollama; `forge start` pulls the models
  depends_on "python@3.12"

  def install
    # Only a launcher lives in the keg. The venv is built in post_install under var/:
    # Homebrew rewrites the install name of every Mach-O file in a keg, and prebuilt
    # wheels such as orjson leave no header room for that, so a venv inside the keg
    # fails `brew install` even though the package works.
    bin.write_exec_script var/"tolvi-forge/venv/bin/forge"
  end

  def post_install
    venv = var/"tolvi-forge/venv"
    rm_r(venv) if venv.exist?
    system formula_opt_bin("python@3.12")/"python3.12", "-m", "venv", venv
    system venv/"bin/python", "-m", "pip", "install", "--quiet", "tolvi-forge==#{version}"
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
