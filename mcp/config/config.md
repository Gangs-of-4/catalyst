# MCP Configuration Notes

This directory documents how MCP servers are configured for this project (e.g. which servers are enabled, at what scope) — non-secret information only.

## Configured servers

| Server | Transport | URL | Auth | Scope |
|---|---|---|---|---|
| `21st` | HTTP | `https://21st.dev/api/mcp` | header `x-api-key` (personal key) | **local** (`~/.claude.json`), each member adds their own |

Nothing is configured at project scope: there is no `.mcp.json` in the repo, because the repo is public. Install steps: `mcp/servers/21st/21st.md`.

## Adding another server

- Document its configuration here (referencing environment variable *names*, never values/secrets).
- Cross-link to the corresponding `mcp/servers/<server-name>/<server-name>.md`.
