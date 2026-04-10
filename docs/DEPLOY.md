# AshbelOS — Deploy Runbook

---

## Deploy Target

Railway — auto-deploys from `master` branch on GitHub push.

- **Production URL:** https://ashbel-os-production.up.railway.app
- **Health endpoint:** `GET /api/health`
- **Start command:** `gunicorn 'api.app:create_app()' --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
- **Builder:** Nixpacks (see `railway.json`)

---

## Pre-Deploy Checklist

```
[ ] PYTHONPATH=. venv/Scripts/pytest tests/ -q  →  all green
[ ] GET /api/health  →  200 {"db": true}
[ ] POST /api/command {"command":"הצג לידים"}  →  200
[ ] git diff origin/master HEAD  →  only intended changes
[ ] No secrets in staged files
[ ] git push origin master
```

---

## Required Environment Variables (Railway)

See `.env.example` for the full list. Minimum required for production:

| Variable | Required | Notes |
|----------|----------|-------|
| `DATABASE_URL` | Yes | Auto-injected by Railway PostgreSQL add-on |
| `OS_API_KEY` | Yes | Auth for all API routes — set to `Ashbel2026` |
| `SECRET_KEY` | Yes | Flask session key |
| `ANTHROPIC_API_KEY` | Yes | AI agents (agents fall back gracefully if missing) |
| `BUSINESS_ID` | No | Defaults to `ashbel` if unset |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram outbound notifications |
| `TELEGRAM_CHAT_ID` | Yes | Target chat ID |
| `WEBHOOK_VERIFY_TOKEN` | Yes | Inbound webhook auth |

Optional (stub mode if missing):
- `GMAIL_CREDENTIALS_JSON` — Gmail listener
- `GOOGLE_MAPS_API_KEY` — Lead scraper
- `WHATSAPP_ACCESS_TOKEN` — WhatsApp (blocked, do not expand)
- `WHATSAPP_PHONE_NUMBER_ID` — WhatsApp (blocked)

---

## Post-Deploy Verification

```bash
# Health
curl https://ashbel-os-production.up.railway.app/api/health

# Commit hash
curl https://ashbel-os-production.up.railway.app/api/version

# Authenticated command
curl -X POST https://ashbel-os-production.up.railway.app/api/command \
  -H "X-API-Key: Ashbel2026" \
  -H "Content-Type: application/json" \
  -d '{"command":"הצג לידים"}'
```

Expected: `{"data":{"db":true,"status":"ok"},"success":true}`

---

## Rollback

Railway keeps the previous deployment available. To roll back:
1. Go to Railway dashboard → Deployments
2. Select the previous successful deployment
3. Click "Redeploy"

Or via git:
```bash
git revert HEAD
git push origin master
```

---

## Branch Model

| Branch | Purpose |
|--------|---------|
| `master` | Production-ready — auto-deploys to Railway |
| `fix/*` | Hotfix branches — merge to master after tests pass |

Never force-push to `master`.

---

## DB Schema Migrations

Schema migrations run automatically on startup via `db.py:_run_column_migrations()`.
Uses `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` — safe to run repeatedly.
No manual migration steps required.
