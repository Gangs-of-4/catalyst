# MCP Integrations

This directory documents Model Context Protocol (MCP) server integrations used by this project.

## Purpose

MCP servers extend Claude Code with additional tools/data sources. This directory is where that integration knowledge lives so future sessions understand what's connected and why — it is documentation, not a place to vendor entire external MCP server codebases.

## Current state

No MCP servers are configured in this project yet.

## Where MCP documentation belongs

- `mcp/servers/<server-name>/<server-name>.md` — one doc per MCP server actually used by this project.
- `mcp/config/` — notes on how MCP servers are configured for this project (non-secret configuration references only).

## Adding a new MCP server

1. Create `mcp/servers/<server-name>/<server-name>.md` using the template below.
2. Document any non-secret configuration under `mcp/config/`.
3. Never commit actual secrets (API keys, tokens) — reference the required environment variable names only, and document where the real values are stored (e.g. a local `.env`, a secrets manager).

### Server doc template

```markdown
# MCP Server

## Purpose

## Capabilities

## Why This Project Uses It

## Installation

## Configuration

## Environment Variables

## Tools Available

## Usage Guidelines

## Security Considerations

## Version

## Official Source
```

## Security Requirements

- No API keys, tokens, or credentials in any file under `mcp/`.
- Document required environment variable names, never their values.
- Note the scope/permissions an MCP server is granted, so reviewers can assess blast radius.
