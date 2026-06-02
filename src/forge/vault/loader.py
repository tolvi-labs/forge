"""Load a repo's Tolvi vault (tolvi-format-v1) into a token-budgeted CAG block.

This is the only coupling between Forge and Tolvi, and it is one-way and
format-only: Forge reads decisions/patterns a repo already keeps under
<repo>/vault/. No Tolvi code is imported. Absent vault -> returns None.
"""
from __future__ import annotations

from pathlib import Path

from forge.chunker.chunk import count_tokens

_EXCLUDED_STATUS = {"superseded", "deprecated", "draft"}


def _split_frontmatter(text: str) -> tuple[str, str]:
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


def _read_doc(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = _split_frontmatter(text)
    status = (_frontmatter_value(fm, "status") or "active").strip()
    if status in _EXCLUDED_STATUS:
        return None
    tldr = _extract_tldr(body)
    summary = tldr if tldr else body.strip()
    return {"name": path.stem, "summary": summary}


def load_vault(repo_root: str | Path, *, max_tokens: int = 6000) -> str | None:
    vault = Path(repo_root) / "vault"
    if not vault.is_dir():
        return None

    docs: list[dict] = []
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

    if not docs:
        return None

    header = "# Project decisions & patterns (from the Tolvi vault)\n"
    parts: list[str] = [header]
    used = count_tokens(header)
    for doc in docs:
        entry = f"\n## {doc['name']}\n{doc['summary']}\n"
        cost = count_tokens(entry)
        if used + cost > max_tokens:
            break
        parts.append(entry)
        used += cost

    if len(parts) == 1:
        return None
    return "".join(parts)
