# Forge

A local-first AI development environment. A tuned local model does the high-volume implementation work; Claude plans and verifies. Zero token cost and full privacy during execution.

> **Status:** Pre-1.0 — Phase 1 (skeleton + installer). See [`ROADMAP.md`](./ROADMAP.md).

## The workflow

```
Claude (plan → tasks.json) → Forge (execute, local, $0) → Claude (verify diff)
```

Claude is better at *thinking*; the local model is better at *doing at scale*. Forge is the execution layer between them.

## Tolvi is the substrate

Forge runs standalone. But it runs **best** with [Tolvi](https://github.com/tolvi-labs/tolvi), the per-repo engineering-knowledge vault — Tolvi is the engine oil. A local model that knows *what* the code is makes plausible changes; a model that also knows *why* the codebase is the way it is — the decisions and rejected alternatives captured in a Tolvi vault — makes changes that respect intent. When a `vault/` exists in your repo, Forge feeds it into the model's always-on context.

**You may not need it.** A solo dev on a greenfield repo, or a team without a decision vault, gets full value from Forge's code retrieval alone. Tolvi is the multiplier, not the dependency.

## Install

```bash
git clone https://github.com/tolvi-labs/forge && cd forge
bash setup/bootstrap.sh
```

Then `forge status` to confirm.

## License

[Apache 2.0](./LICENSE).
