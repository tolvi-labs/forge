"""Index a repository into a vector store, incrementally and .gitignore-aware."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pathspec

from forge.chunker import chunk_file, detect_language

log = logging.getLogger(__name__)

EmbedFn = Callable[[list[str]], list[list[float]]]

_ALWAYS_IGNORE = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
                  ".ruff_cache", "dist", "build"}


@dataclass
class IndexStats:
    files_indexed: int = 0
    files_skipped: int = 0
    files_pruned: int = 0
    files_failed: int = 0
    chunks_written: int = 0


def _load_gitignore(root: Path) -> pathspec.GitIgnoreSpec:
    lines: list[str] = []
    gi = root / ".gitignore"
    if gi.exists():
        lines = gi.read_text(encoding="utf-8", errors="replace").splitlines()
    return pathspec.GitIgnoreSpec.from_lines(lines)


def _file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _iter_files(root: Path, spec: pathspec.GitIgnoreSpec):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in _ALWAYS_IGNORE for part in rel.parts):
            continue
        if spec.match_file(str(rel)):
            continue
        if detect_language(path) is None and path.suffix.lower() not in {".md", ".txt"}:
            continue
        yield path


def index_repo(root: str | Path, store, embed_fn: EmbedFn) -> IndexStats:
    root = Path(root)
    spec = _load_gitignore(root)
    stats = IndexStats()

    prior = store.indexed_files()
    seen: set[str] = set()

    for path in _iter_files(root, spec):
        fp = str(path)
        seen.add(fp)
        checksum = _file_checksum(path)
        if prior.get(fp) == checksum:
            stats.files_skipped += 1
            continue
        chunks = chunk_file(path)
        try:
            embeddings = embed_fn([c.content for c in chunks]) if chunks else []
            store.replace_file(fp, checksum, chunks, embeddings)
        except Exception as e:
            # One unindexable file (embed failure, transient store error) must not
            # abort the whole run — record it and move on so re-index can retry it.
            stats.files_failed += 1
            log.warning("skipping %s: %s", fp, e)
            continue
        stats.files_indexed += 1
        stats.chunks_written += len(chunks)

    for gone in set(prior) - seen:
        store.delete_file(gone)
        stats.files_pruned += 1

    return stats
