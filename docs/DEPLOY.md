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
| `OS_API_KEY` | Yes | Auth for all API routes — configured hosting secret |
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
  -H "X-API-Key: ${OS_API_KEY:?Set OS_API_KEY securely}" \
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


## Durable scheduler claims (2026-11-16)

All nine scheduled callbacks claim `(job_id, occurrence slot)` in the shared database before invoking their job. Daily/weekly jobs use the Asia/Jerusalem calendar date; interval jobs use fixed UTC buckets and epoch-anchored schedules, so worker startup times do not create separate occurrences. `create_all_tables()` creates the additive `scheduler_runs` table before scheduler startup. A database coordination failure blocks invocation.

Claims survive worker restarts. A process crash retains `claimed`; an uncaught exception records `failed`; normal callback return records `returned`, which is not proof of business success or delivery. Existing jobs may catch their own errors. Inspect `recent_claims` on `/api/system/scheduler` alongside application logs; existing `last_runs` alone does not prove success.

This provides at-most-once invocation per slot, not guaranteed completion. Do not automatically delete or retry an ambiguous claim: check for side effects first and recover the specific job under operator control. Manual run-now endpoints keep their existing explicit behavior and are outside scheduled claim enforcement. Retain claim history; no production rows are deleted by this change.
