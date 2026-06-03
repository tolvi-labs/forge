# tests/unit/test_mcp_config.py
import json
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
SERVERS = REPO / "mcp" / "servers.json"

# Packages verified to exist on npm on 2026-06-02. The chunker/index never invoke
# these — this guard just prevents shipping a name that npx can't resolve.
VERIFIED_PACKAGES = {
    "@cyanheads/git-mcp-server",
    "@modelcontextprotocol/server-github",
    "@modelcontextprotocol/server-filesystem",
    "mcp-atlassian",
    "@upstash/context7-mcp",
    "@modelcontextprotocol/server-sequential-thinking",
    "google-cloud-mcp",
    "firebase-tools",
    "@playwright/mcp",
}


def _servers() -> dict:
    return json.loads(SERVERS.read_text())["mcpServers"]


def test_servers_json_is_valid_and_nonempty():
    servers = _servers()
    assert len(servers) == 9


def test_every_server_has_command_args_description():
    for name, cfg in _servers().items():
        assert cfg["command"] == "npx", name
        assert isinstance(cfg["args"], list) and cfg["args"], name
        assert cfg.get("description"), name


def test_every_package_is_npm_verified():
    for name, cfg in _servers().items():
        # the package id is the first arg that isn't an npx flag
        pkg = next(a for a in cfg["args"] if not a.startswith("-"))
        assert pkg in VERIFIED_PACKAGES, f"{name}: unverified package {pkg}"


def test_expected_servers_present():
    assert set(_servers()) == {
        "git", "github", "filesystem", "jira", "context7",
        "sequential-thinking", "gcloud", "firebase", "playwright",
    }
