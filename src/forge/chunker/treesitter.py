"""Tree-sitter AST chunking across the supported grammars.

Written against the modern py-tree-sitter API (>= 0.23, as pinned in pyproject):
Parser.parse() takes bytes; Tree.root_node, Node.type, Node.named_children,
Node.start_byte/end_byte, and Node.start_point/end_point are all attributes
(properties). Node.child_by_field_name() is a method.
"""
from __future__ import annotations

from tree_sitter_language_pack import get_parser

from forge.chunker.chunk import Chunk

# Chunking granularity is class/function-level: `_collect` emits a target node and
# does not descend into it, so a class is one chunk (its methods are not split out).
# Method-level chunking (descending into class bodies, with overlap handling) is a
# deferred refinement — see vault/decisions. Node-type maps below therefore omit
# `method_definition`/`method_declaration`, which would be unreachable inside a class.
_CHUNK_NODES: dict[str, dict[str, str]] = {
    "python": {"function_definition": "function", "class_definition": "class"},
    "javascript": {"function_declaration": "function", "class_declaration": "class"},
    "typescript": {"function_declaration": "function", "class_declaration": "class",
                   "interface_declaration": "interface"},
    "tsx": {"function_declaration": "component", "class_declaration": "class"},
    "java": {"class_declaration": "class", "interface_declaration": "interface"},
    "css": {"rule_set": "rule-set"},
    "html": {"element": "element"},
    "json": {"pair": "pair"},
    "bash": {"function_definition": "function"},
}


def _collect(node, targets: dict[str, str], out: list) -> None:
    for child in node.named_children:
        if child.type in targets:
            out.append(child)
        else:
            _collect(child, targets, out)


def _symbol(node, data: bytes) -> str:
    name = node.child_by_field_name("name")
    if name is not None:
        return data[name.start_byte:name.end_byte].decode("utf-8", "replace")
    kids = node.named_children
    if kids:
        first = kids[0]
        text = data[first.start_byte:first.end_byte].decode("utf-8", "replace").strip()
        if text:
            return text.splitlines()[0][:60]
    return "<anonymous>"


def chunk_source(source: str, *, language: str, file_path: str) -> list[Chunk]:
    targets = _CHUNK_NODES.get(language, {})
    data = source.encode("utf-8")
    tree = get_parser(language).parse(data)
    root = tree.root_node

    nodes: list = []
    _collect(root, targets, nodes)

    chunks: list[Chunk] = []
    for node in nodes:
        content = data[node.start_byte:node.end_byte].decode("utf-8", "replace")
        chunks.append(Chunk.make(
            file_path=file_path, language=language,
            chunk_type=targets[node.type], symbol_name=_symbol(node, data),
            start_line=node.start_point.row + 1,
            end_line=node.end_point.row + 1, content=content,
        ))

    if not chunks:
        text = source.rstrip("\n")
        chunks.append(Chunk.make(
            file_path=file_path, language=language, chunk_type="file",
            symbol_name=file_path, start_line=1,
            end_line=max(1, len(source.splitlines())), content=text,
        ))
    return chunks
