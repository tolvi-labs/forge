"""ChromaDB-backed vector store with file-level incremental indexing."""
from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings

from forge.chunker.chunk import Chunk


class ChromaStore:
    def __init__(self, persist_dir: str | Path, collection: str = "code") -> None:
        self._client = chromadb.PersistentClient(
            path=str(persist_dir), settings=Settings(anonymized_telemetry=False),
        )
        self._col = self._client.get_or_create_collection(collection)

    def indexed_files(self) -> dict[str, str]:
        got = self._col.get(include=["metadatas"])
        out: dict[str, str] = {}
        for md in got["metadatas"] or []:
            out[md["file_path"]] = md["file_checksum"]
        return out

    def count(self) -> int:
        return self._col.count()

    def delete_file(self, file_path: str) -> None:
        self._col.delete(where={"file_path": file_path})

    def replace_file(
        self, file_path: str, file_checksum: str, chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        self.delete_file(file_path)
        if not chunks:
            return
        self._col.add(
            ids=[c.chunk_id for c in chunks],
            embeddings=embeddings,
            documents=[c.content for c in chunks],
            metadatas=[{
                "file_path": c.file_path, "file_checksum": file_checksum,
                "language": c.language, "chunk_type": c.chunk_type,
                "symbol_name": c.symbol_name, "start_line": c.start_line,
                "end_line": c.end_line,
            } for c in chunks],
        )

    def query(self, embedding: list[float], top_k: int = 6) -> list[dict]:
        res = self._col.query(query_embeddings=[embedding], n_results=top_k,
                              include=["metadatas", "documents", "distances"])
        hits: list[dict] = []
        metas = res["metadatas"][0] if res["metadatas"] else []
        docs = res["documents"][0] if res["documents"] else []
        dists = res["distances"][0] if res["distances"] else []
        for md, doc, dist in zip(metas, docs, dists):
            hits.append({**md, "content": doc, "distance": dist})
        return hits
