"""Render the Forge Ollama Modelfile from a template."""
from __future__ import annotations


def render_modelfile(template: str, *, recommended_model: str, max_context: int) -> str:
    return (
        template
        .replace("{{RECOMMENDED_MODEL}}", recommended_model)
        .replace("{{MAX_CONTEXT}}", str(max_context))
    )
