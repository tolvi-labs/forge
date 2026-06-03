---
tags: [decision, forge]
status: active
date: 2026-06-02
repo: forge
ticket: none
---

## TL;DR

Ship `mcp/servers.json` with packages verified to exist on npm; the TRD's `server-git`, `server-atlassian`, `@google-cloud/mcp-server`, `@invertase/mcp-firebase` don't exist and were replaced. A test allowlist guards against drift. Rejected: shipping the TRD names as-is (npx would fail to resolve them at runtime).

## Why

A pre-wired MCP config is only useful if every server actually launches. Several package names in the original TRD were speculative and do not resolve on npm, so a user copying the config would hit `npx` errors on those servers.

## How

- Verified all candidate packages on npm (2026-06-02). Confirmed real: `@modelcontextprotocol/server-github`, `@modelcontextprotocol/server-sequential-thinking`, `@modelcontextprotocol/server-filesystem`, `@upstash/context7-mcp`, `@playwright/mcp`.
- Substitutions for the four broken TRD names:
  - `@modelcontextprotocol/server-git` (missing) → `@cyanheads/git-mcp-server`
  - `@modelcontextprotocol/server-atlassian` (missing) → `mcp-atlassian`
  - `@google-cloud/mcp-server` (missing) → `google-cloud-mcp`
  - `@invertase/mcp-firebase` (missing) → `firebase-tools experimental:mcp` (the Firebase CLI's built-in MCP server)
- `mcp/servers.json` uses the standard `mcpServers` object so it's directly reusable by Cursor (`.cursor/mcp.json`, shipped as a verbatim copy) and Claude Desktop. Continue.dev carries its own inline `mcpServers` list with only the no-credential servers; credentialed ones (github/jira/gcloud/firebase) carry clearly-marked `<placeholder>` env values.
- `tests/unit/test_mcp_config.py` encodes the verified-package allowlist, so a future edit that reintroduces an unresolvable package name fails CI.

## Outcome

Every one of the 9 shipped MCP servers maps to a package that resolves on npm; the allowlist test prevents regressions.
