# Repository Decision

## Primary decision

`feldixAR/Ashbel-os` is the only primary system repository for the Ashbel Aluminum Revenue OS.

This repo contains the existing custom AshbelOS application, UI, routes, agents, skills, approvals, revenue logic, Telegram operator channel, GPT connector and MCP endpoint.

## Repositories

| Repository | Status | Use |
|---|---|---|
| `feldixAR/Ashbel-os` | Primary | Main system, main UI, source of truth for product code |
| `feldixAR/Ashbel_Aluminum_Revenue_OS` | Reference only | May be consulted for process discipline and previous planning ideas only |
| `feldixAR/Repository-name-ashbal-os` | Irrelevant unless proven otherwise | Do not use for active work |

## HubSpot decision

HubSpot is removed from the active project direction.

Do not use HubSpot as:

- Primary UI.
- CRM source of truth.
- Sync target.
- Export target.
- Backup path.
- Fallback implementation.
- Alternative operating model.

Any future reintroduction of HubSpot requires a new explicit approval and a change to this document.

## Development direction

All future development must extend, clean, and complete `feldixAR/Ashbel-os`.

Do not:

- Build a new CRM.
- Create a parallel system.
- Restart the lightweight HubSpot package direction.
- Move business logic out of AshbelOS.
- Treat external systems as source of truth.

## Prompt discipline

Every future Codex or Claude Code prompt must start by reading the project control documents. If a requested action conflicts with these decisions, the agent must stop and report the conflict instead of continuing.