"""Line-based fallback chunker used when Tree-sitter parsing fails."""
from __future__ import annotations

from forge.chunker.chunk import Chunk

_MAX_LINES = 60
_OVERLAP = 10


def chunk_lines(source: str, *, language: str, file_path: str) -> list[Chunk]:
    lines = source.splitlines()
    chunks: list[Chunk] = []
    block_start = 0  # 0-based index of the first line of the current block
    i = 0
    n = len(lines)

    def emit(start0: int, end0: int) -> None:
        if start0 > end0:
            return
        content = "\n".join(lines[start0:end0 + 1])
        if not content.strip():
            return
        chunks.append(Chunk.make(
            file_path=file_path, language=language, chunk_type="block",
            symbol_name=f"{file_path}:{start0 + 1}", start_line=start0 + 1,
            end_line=end0 + 1, content=content,
        ))

    while i < n:
        if lines[i].strip() == "":
            emit(block_start, i - 1)
            i += 1
            block_start = i
            continue
        if i - block_start + 1 >= _MAX_LINES:
            emit(block_start, i)
            block_start = i - _OVERLAP + 1
        i += 1

    emit(block_start, n - 1)
    return chunks
