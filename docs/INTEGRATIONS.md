# AshbelOS — Integration and Connector Inventory

> Governance source: `docs/ashbelos-governance.md` §Wave One, §Excluded from Active Approved Scope

---

## Status Key

| Status | Meaning |
|--------|---------|
| ✅ Active | Integrated, in production, approved for use |
| 🟡 Stub | Code exists, returns empty if credentials missing |
| 🔴 Blocked | Route/code exists, must not be expanded or triggered |
| ❌ Not built | No code exists |

---

## Connector Inventory

### Telegram
- **Status:** ✅ Active (Wave One approved)
- **File:** `api/routes/telegram.py`, `services/telegram_service.py`
- **Purpose:** Inbound commands, outbound notifications, approval keyboard
- **Auth:** `WEBHOOK_VERIFY_TOKEN` header
- **Docs:** `docs/TELEGRAM.md`

### Gmail Listener
- **Status:** 🟡 Stub (active when `GMAIL_CREDENTIALS_JSON` is set)
- **File:** `services/integrations/gmail_listener.py`
- **Purpose:** Scans inbox for inbound lead emails, extracts phone/email, creates leads
- **Schedule:** Every 30 minutes via APScheduler
- **Credentials:** `GMAIL_CREDENTIALS_JSON` (Google service account JSON)
- **Dedup:** By phone and email before creating leads

### Google Maps Lead Scraper
- **Status:** 🟡 Stub (active when `GOOGLE_MAPS_API_KEY` is set)
- **File:** `services/integrations/lead_scraper.py`
- **Purpose:** Scrapes contractor/architect leads from Google Maps Places API
- **Schedule:** Daily 06:00 via APScheduler
- **Rate limit:** 1 req/sec, max 50 leads/run
- **Credentials:** `GOOGLE_MAPS_API_KEY`
- **Categories:** קבלנים, אדריכלים, מעצבי פנים, יזמי נדלן

### WhatsApp (Meta Business API)
- **Status:** 🔴 Blocked — route exists, must not be expanded
- **File:** `api/routes/whatsapp.py`, partial logic in `engines/outreach_engine.py`
- **Purpose:** Historical scaffold. WhatsApp send logic exists in outreach engine but active automation must not be added.
- **Credentials:** `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`
- **Rule:** Do not add new automation targeting this channel.

### Claude Bridge (Anthropic)
- **Status:** ✅ Active — orchestration interface only
- **Files:** `api/routes/claude_dispatch.py`, `engines/claude_dispatch.py`
- **Routes:** `POST /api/claude/preview`, `/api/claude/dispatch`, `/api/claude/tasks/<id>`
- **Purpose:** Sensitive action preview+approval flow via Claude
- **Note:** Not business core. If removed, AshbelOS continues via `POST /api/command`.

### GPT Connector (OpenAI)
- **Status:** ✅ Active — read/redispatch only
- **File:** `api/routes/gpt_connector.py`
- **Routes:** `/api/gpt/*`
- **Purpose:** GPT review of tasks, redispatch, OpenAPI schema exposure
- **Note:** Additive only. Core CRM unaffected if unavailable.

### MCP Endpoint
- **Status:** ✅ Active — read-only
- **File:** `api/routes/mcp.py`
- **Route:** `POST /api/mcp`
- **Purpose:** ChatGPT-compatible endpoint, `get_latest_claude_task`, no-auth
- **Note:** Read-only. Core unaffected if unavailable.

### OpenClaw
- **Status:** ✅ Active — detachable orchestration layer
- **File:** `api/routes/openclaw.py`
- **Purpose:** External orchestration of AshbelOS tasks
- **Note:** AshbelOS is independent. OpenClaw failure does not block core.

### Email
- **Status:** ❌ Not approved for execution
- **Note:** Email send logic may exist in `outreach_engine.py` as scaffold. Must not be triggered.

### Calendar
- **Status:** ❌ Not approved

---

## Scheduler Jobs

| Job | Schedule | Service |
|-----|----------|---------|
| Gmail scan | Every 30 min | `gmail_listener.scan_inbox()` |
| Maps scrape | Daily 06:00 | `lead_scraper.scrape(city, category)` — 4 cities × 2 categories |
| Maintenance report | Sunday 07:00 | `maintenance_agent` weekly health |

Scheduler: APScheduler in `scheduler/revenue_scheduler.py`.
