"""Tree-sitter AST chunking across the supported grammars.

Written against the tree-sitter-language-pack binding: parse() takes str;
root_node(), kind(), named_child(), named_child_count(), child_by_field_name(),
start_byte()/end_byte(), start_position()/end_position() are all METHOD calls;
there is no node.text.
"""
from __future__ import annotations

from tree_sitter_language_pack import get_parser

from forge.chunker.chunk import Chunk

_CHUNK_NODES: dict[str, dict[str, str]] = {
    "python": {"function_definition": "function", "class_definition": "class"},
    "javascript": {"function_declaration": "function", "class_declaration": "class",
                   "method_definition": "method"},
    "typescript": {"function_declaration": "function", "class_declaration": "class",
                   "interface_declaration": "interface", "method_definition": "method"},
    "tsx": {"function_declaration": "component", "class_declaration": "class",
            "method_definition": "method"},
    "java": {"class_declaration": "class", "interface_declaration": "interface",
             "method_declaration": "method"},
    "css": {"rule_set": "rule-set"},
    "html": {"element": "element"},
    "json": {"pair": "pair"},
    "bash": {"function_definition": "function"},
}


def _collect(node, targets: dict[str, str], out: list) -> None:
    for i in range(node.named_child_count()):
        child = node.named_child(i)
        if child.kind() in targets:
            out.append(child)
        else:
            _collect(child, targets, out)


def _symbol(node, data: bytes) -> str:
    name = node.child_by_field_name("name")
    if name is not None:
        return data[name.start_byte():name.end_byte()].decode("utf-8", "replace")
    if node.named_child_count():
        first = node.named_child(0)
        text = data[first.start_byte():first.end_byte()].decode("utf-8", "replace").strip()
        if text:
            return text.splitlines()[0][:60]
    return "<anonymous>"


def chunk_source(source: str, *, language: str, file_path: str) -> list[Chunk]:
    targets = _CHUNK_NODES.get(language, {})
    data = source.encode("utf-8")
    tree = get_parser(language).parse(source)
    root = tree.root_node()

    nodes: list = []
    _collect(root, targets, nodes)

    chunks: list[Chunk] = []
    for node in nodes:
        content = data[node.start_byte():node.end_byte()].decode("utf-8", "replace")
        chunks.append(Chunk.make(
            file_path=file_path, language=language,
            chunk_type=targets[node.kind()], symbol_name=_symbol(node, data),
            start_line=node.start_position().row + 1,
            end_line=node.end_position().row + 1, content=content,
        ))

    if not chunks:
        text = source.rstrip("\n")
        chunks.append(Chunk.make(
            file_path=file_path, language=language, chunk_type="file",
            symbol_name=file_path, start_line=1,
            end_line=max(1, source.count("\n")), content=text,
        ))
    return chunks
