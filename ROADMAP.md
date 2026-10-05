# Roadmap

## Phases

| Phase | Ships | Status |
|---|---|---|
| **P1: Skeleton + installer** | Repo skeleton, `bootstrap.sh`, `Modelfile.tmpl`, `config.py`, `forge doctor/status` | ✅ |
| **P2: Index** | Tree-sitter chunker (+ fallback), embedder, ChromaDB store, `forge index [--watch]` | ✅ |
| **P3A: Context engine** | Retriever, CAG/RAG assembler, Tolvi vault bridge, `forge search`, `forge chat` | ✅ |
| **P3B: Plan workflow** | `forge plan load/status/next/complete`, `forge verify`, tasks.json schema | ✅ |
| **P4: MCP + editors** | `mcp/servers.json` (npm-verified), Continue + Cursor configs | ✅ |
| **P5: Profiles + multi-agent** | Stack profiles, plain-Python code/review orchestrator (LangGraph deferred) | ✅ |

## Releases

| Version | Ships |
|---|---|
| **0.1** | First PyPI release (`pipx install tolvi-forge`), including `forge outcome` / `forge report` metrics: acceptance, rework, local tokens, trust |
| **0.2** | `forge detect-hardware` in Python (replaces `setup/detect-hardware.sh`), so a `pipx` install writes its own hardware profile; `forge status --json` / `forge doctor --json` |
| **0.3** | `forge agents run --apply`: the local model edits each task's files with the plan's Magellan context and RAG from `forge index`, and reviewed tasks are committed on a `forge/<feature>` branch; `forge outcome` measures rework from the model's last commit and records rejected tasks automatically |

## Next

- Calibrate the `--apply` context budget (reply reserve and tokenizer margin) from real use.
- Use `forge outcome` / `forge report` data from sustained real work to decide whether the local model clears the bar.
- Homebrew stays off until Homebrew offers a compliant way to package Forge's dependency tree (see [`RELEASE.md`](./RELEASE.md)).
