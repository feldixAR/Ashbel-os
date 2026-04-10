# AshbelOS

Autonomous Business Operating System for אשבל אלומיניום (Ashbal Aluminum).

**Production:** https://ashbel-os-production.up.railway.app

## Documentation

| Doc | Purpose |
|-----|---------|
| [`CLAUDE.md`](CLAUDE.md) | Agent context — architecture, governance adapter, session log |
| [`docs/ashbelos-governance.md`](docs/ashbelos-governance.md) | **Governance source of truth** — product layers, sensitive flow, Wave One, fallback |
| [`docs/ashbelos-token-efficiency-policy.md`](docs/ashbelos-token-efficiency-policy.md) | **Token policy source of truth** |
| [`docs/AGENT.md`](docs/AGENT.md) | Agent contracts — registration, routing, local-first |
| [`docs/TELEGRAM.md`](docs/TELEGRAM.md) | Telegram integration — webhook, approval flow |
| [`docs/FALLBACK.md`](docs/FALLBACK.md) | Fallback and failure mode behavior |
| [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md) | Connector inventory — status, credentials, scheduler |
| [`docs/DEPLOY.md`](docs/DEPLOY.md) | Deploy runbook — Railway, env vars, rollback |
| [`docs/API.md`](docs/API.md) | API reference |
| [`.env.example`](.env.example) | Environment variables reference |

## Stack

- Python 3.11, Flask + Gunicorn
- PostgreSQL (Railway add-on)
- Deployed on Railway — auto-deploy from `master`

## Quick Start

```bash
cp .env.example .env  # fill in values
PYTHONPATH=. venv/Scripts/pytest tests/ -q  # must be green
git push origin master  # Railway auto-deploys
```

## Health Check

```bash
curl https://ashbel-os-production.up.railway.app/api/health
# {"data":{"db":true,"status":"ok"},"success":true}
```
