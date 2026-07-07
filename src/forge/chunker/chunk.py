"""Chunk data model + token/checksum helpers."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import tiktoken

_ENC = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_ENC.encode(text, disallowed_special=()))


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Trim text to at most max_tokens (cl100k). Used to keep embedder inputs
    under the embedding model's context window so a single oversized chunk (a
    lockfile, a minified bundle) can't 400 the whole index run."""
    toks = _ENC.encode(text, disallowed_special=())
    if len(toks) <= max_tokens:
        return text
    return _ENC.decode(toks[:max_tokens])


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Chunk:
    file_path: str
    language: str
    chunk_type: str
    symbol_name: str
    start_line: int
    end_line: int
    content: str
    token_count: int
    checksum: str

    @property
    def chunk_id(self) -> str:
        return f"{self.file_path}::{self.start_line}-{self.end_line}"

    @classmethod
    def make(cls, *, file_path: str, language: str, chunk_type: str,
             symbol_name: str, start_line: int, end_line: int, content: str) -> "Chunk":
        return cls(
            file_path=file_path, language=language, chunk_type=chunk_type,
            symbol_name=symbol_name, start_line=start_line, end_line=end_line,
            content=content, token_count=count_tokens(content), checksum=checksum(content),
        )
