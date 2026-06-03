# Roadmap

## Phases

| Phase | Ships | Status |
|---|---|---|
| **P1 — Skeleton + installer** | Repo skeleton, `bootstrap.sh`, `detect-hardware.sh`, `Modelfile.tmpl`, `config.py`, `forge doctor/status` | ✅ |
| **P2 — Index** | Tree-sitter chunker (+ fallback), embedder, ChromaDB store, `forge index [--watch]` | ✅ |
| **P3A — Context engine** | Retriever, CAG/RAG assembler, Tolvi vault bridge, `forge search`, `forge chat` | ✅ |
| **P3B — Plan workflow** | `forge plan load/status/next/complete`, `forge verify`, tasks.json schema | ✅ |
| **P4 — MCP + editors** | `mcp/servers.json` (npm-verified), Continue + Cursor configs | 📅 |
| **P5 — Profiles + multi-agent** | Stack profiles, LangGraph multi-agent | 📅 |
