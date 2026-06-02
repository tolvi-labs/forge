"""Pure CAG+RAG context assembly under a token budget.

Window order: static CAG blocks (always-relevant: manifests, README, the Tolvi
vault, open file) -> dynamic RAG code chunks (hard-capped) -> conversation
history -> the current query. The caller gathers the inputs; this function only
packs and budgets them, so it is pure and trivially testable.
"""
from __future__ import annotations

from forge.chunker.chunk import count_tokens

_RAG_CAP_DEFAULT = 25000


def format_hit(hit: dict) -> str:
    loc = f"{hit.get('file_path', '?')}:{hit.get('start_line', '?')}-{hit.get('end_line', '?')}"
    symbol = hit.get("symbol_name", "")
    return f"// {loc}  ({symbol})\n{hit.get('content', '')}\n"


def assemble(query: str, *, cag_blocks: list[str], rag_hits: list[dict],
             history: str = "", max_context: int = 65536,
             rag_cap_tokens: int = _RAG_CAP_DEFAULT) -> str:
    cag = [b.strip() for b in cag_blocks if b and b.strip()]

    rendered: list[str] = []
    used = 0
    for hit in rag_hits:
        piece = format_hit(hit)
        cost = count_tokens(piece)
        if used + cost > rag_cap_tokens:
            break
        rendered.append(piece)
        used += cost

    def build(rag_pieces: list[str]) -> str:
        sections = list(cag)
        if rag_pieces:
            sections.append("# Relevant code\n" + "\n".join(rag_pieces))
        if history and history.strip():
            sections.append("# Conversation so far\n" + history.strip())
        sections.append("# Question\n" + query.strip())
        return "\n\n".join(sections)

    prompt = build(rendered)
    while count_tokens(prompt) > max_context and rendered:
        rendered.pop()
        prompt = build(rendered)
    return prompt
