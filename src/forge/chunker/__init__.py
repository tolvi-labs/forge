"""Chunking entrypoint: detect language, then Tree-sitter with a line fallback."""
from __future__ import annotations

from pathlib import Path

from forge.chunker.chunk import Chunk
from forge.chunker.fallback import chunk_lines
from forge.chunker.treesitter import chunk_source

_EXT_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript", ".cjs": "javascript", ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx", ".jsx": "tsx",
    ".java": "java",
    ".css": "css",
    ".html": "html", ".htm": "html",
    ".json": "json",
    ".sh": "bash", ".bash": "bash",
}

__all__ = ["chunk_file", "detect_language", "Chunk"]


def detect_language(path: str | Path) -> str | None:
    return _EXT_LANG.get(Path(path).suffix.lower())


def chunk_file(path: str | Path) -> list[Chunk]:
    path = Path(path)
    source = path.read_text(encoding="utf-8", errors="replace")
    file_path = str(path)
    language = detect_language(path)
    if language is None:
        return chunk_lines(source, language="text", file_path=file_path)
    try:
        return chunk_source(source, language=language, file_path=file_path)
    except Exception:
        return chunk_lines(source, language=language, file_path=file_path)
