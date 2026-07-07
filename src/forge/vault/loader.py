"""Load a repo's Tolvi vault (tolvi-format-v1) into a token-budgeted CAG block.

This is the only coupling between Forge and Tolvi, and it is one-way and
format-only: Forge reads decisions/patterns a repo already keeps under
<repo>/vault/. No Tolvi code is imported. Absent vault -> returns None.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from forge.chunker.chunk import count_tokens

_EXCLUDED_STATUS = {"superseded", "deprecated", "draft"}
_HEADER = "# Project decisions & patterns (from the Tolvi vault)\n"


@dataclass
class VaultDoc:
    """A single parsed vault decision/pattern: its filename stem and the summary
    that goes into context. Recency is encoded by position in the read order."""
    name: str
    summary: str


def entry_text(doc: VaultDoc) -> str:
    """The context block entry for one doc. Shared with the selector so budget
    accounting and rendering stay in lockstep."""
    return f"\n## {doc.name}\n{doc.summary}\n"


def _split_frontmatter(text: str) -> tuple[str, str]:
    text = text.lstrip("﻿\r\n")  # tolerate a BOM / leading blank lines
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm = text[3:end]
            body = text[end + 4:].lstrip("\n")
            return fm, body
    return "", text


def _frontmatter_value(fm: str, key: str) -> str | None:
    for line in fm.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{key}:"):
            return stripped[len(key) + 1:].strip()
    return None


def _extract_tldr(body: str) -> str | None:
    out: list[str] = []
    capturing = False
    for line in body.splitlines():
        if line.strip().lower().startswith("## tl;dr"):
            capturing = True
            continue
        if capturing and line.startswith("## "):
            break
        if capturing:
            out.append(line)
    text = "\n".join(out).strip()
    return text or None


def _read_doc(path: Path) -> VaultDoc | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = _split_frontmatter(text)
    # Normalize before comparing: strip inline `# comment`, surrounding space, and
    # case, so `status: Superseded` / `status: superseded # legacy` are still excluded.
    raw_status = _frontmatter_value(fm, "status") or "active"
    status = raw_status.split("#")[0].strip().lower()
    if status in _EXCLUDED_STATUS:
        return None
    tldr = _extract_tldr(body)
    summary = tldr if tldr else body.strip()
    if not summary:  # frontmatter-only doc — nothing worth spending tokens on
        return None
    return VaultDoc(name=path.stem, summary=summary)


def read_docs(vault: Path) -> list[VaultDoc]:
    """Parse a vault's decisions (newest-first by filename) then patterns. No
    budgeting or selection — that lives in the selector."""
    docs: list[VaultDoc] = []
    decisions_dir = vault / "decisions"
    if decisions_dir.is_dir():
        for f in sorted(decisions_dir.glob("*.md"), reverse=True):
            doc = _read_doc(f)
            if doc:
                docs.append(doc)
    patterns_dir = vault / "patterns"
    if patterns_dir.is_dir():
        for f in sorted(patterns_dir.glob("*.md")):
            doc = _read_doc(f)
            if doc:
                docs.append(doc)
    return docs


def load_vault(
    repo_root: str | Path, *, max_tokens: int = 6000,
    query: str | None = None, embed_fn=None, core_recent_n: int = 3,
) -> str | None:
    """Build the vault CAG block. With a query + embed_fn, decisions are selected
    by relevance beyond a recency-based always-on core; without, by recency
    (backward-compatible)."""
    from forge.vault.selector import select_docs  # function-level: avoids import cycle

    env_override = os.environ.get("FORGE_VAULT")
    vault = Path(env_override) if env_override else Path(repo_root) / "vault"
    if not vault.is_dir():
        return None

    docs = read_docs(vault)
    if not docs:
        return None

    entry_budget = max(0, max_tokens - count_tokens(_HEADER))
    chosen = select_docs(
        docs, query=query, embed_fn=embed_fn,
        max_tokens=entry_budget, core_recent_n=core_recent_n,
    )
    if not chosen:
        return None
    return _HEADER + "".join(entry_text(d) for d in chosen)
