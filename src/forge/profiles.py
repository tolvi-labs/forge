"""Stack profiles: the per-stack static-file + retrieval config for the window."""
from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources

_DATA_PKG = "forge.profiles_data"


class ProfileError(ValueError):
    """Raised for an unknown or malformed profile."""


@dataclass(frozen=True)
class Profile:
    name: str
    static_files: list[str]
    static_gcp_files: list[str]
    vault_enabled: bool
    vault_max_tokens: int
    rag_top_k: int
    rerank: bool
    max_context_tokens: int


def list_profiles() -> list[str]:
    out: list[str] = []
    for entry in resources.files(_DATA_PKG).iterdir():
        if entry.name.endswith(".json"):
            out.append(entry.name[: -len(".json")])
    return sorted(out)


def load_profile(name: str) -> Profile:
    res = resources.files(_DATA_PKG) / f"{name}.json"
    if not res.is_file():
        raise ProfileError(f"Unknown profile: {name}. Available: {', '.join(list_profiles())}")
    data = json.loads(res.read_text(encoding="utf-8"))
    vault = data.get("vault", {})
    return Profile(
        name=name,
        static_files=list(data.get("static_files", [])),
        static_gcp_files=list(data.get("static_gcp_files", [])),
        vault_enabled=bool(vault.get("enabled", True)),
        vault_max_tokens=int(vault.get("max_tokens", 6000)),
        rag_top_k=int(data.get("rag_top_k", 6)),
        rerank=bool(data.get("rerank", True)),
        max_context_tokens=int(data.get("max_context_tokens", 65536)),
    )
