# AshbelOS — API Reference

**Base URL:** `https://ashbel-os-production.up.railway.app`

**Authentication:** `X-API-Key: <OS_API_KEY>` header required on all routes except `/api/health`, `/api/telegram/webhook`, and `/api/mcp`.

---

## Health & System

| Method | Path | Auth | Response |
|--------|------|------|---------|
| GET | `/api/health` | No | `{"data":{"db":true,"status":"ok"},"success":true}` |
| GET | `/api/version` | No | `{"data":{"commit":"...","environment":"production"}}` |
| POST | `/api/command` | Yes | NLP command dispatcher → orchestrator |
| GET | `/api/system/metrics` | Yes | Agent call metrics snapshot |
| GET | `/api/system/traces/<trace_id>` | Yes | Trace chain for a trace ID |

### POST /api/command

```json
Request:  { "command": "הצג לידים" }
Response: { "data": { "message": "...", "intent": "..." }, "success": true }
```

---

## Lead Acquisition OS (Phase 12–14)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/lead_ops/discover` | Yes | Run acquisition pipeline: `{goal, signals[]}` → discovery plan + work queue |
| POST | `/api/lead_ops/inbound` | Yes | Process inbound lead: `{name, phone, city, message, …}` |
| POST | `/api/lead_ops/website` | Yes | Website growth analysis: `{url, html?}` |
| GET | `/api/lead_ops/queue` | Yes | Current work queue (discovered + inbound + pending actions) |
| GET/POST | `/api/lead_ops/discovery_plan` | Yes | Source strategy for a goal — no DB |
| POST | `/api/lead_ops/draft` | Yes | Draft outreach message: `{lead, action_type}` |
| GET | `/api/lead_ops/status` | Yes | Summary counts widget data |
| GET | `/api/lead_ops/brief/<id>` | Yes | AI briefing for a lead: recommended action, timing, tone, AI summary |
| POST | `/api/lead_ops/batch_score` | Yes | Batch score unscored leads: `{rescore_all?, limit?}` |
| POST | `/api/lead_ops/execute/<id>` | Yes | Execute approved outreach: `{action: approve\|deny, note?}` |

---

## Leads & CRM

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/leads` | Yes | List leads (supports `?status=`, `?limit=`) |
| POST | `/api/leads` | Yes | Create lead |
| PATCH | `/api/leads/<id>` | Yes | Update lead |
| GET | `/api/crm/deals` | Yes | List active deals |
| GET | `/api/crm/leads/<id>/full` | Yes | Lead with activities + timeline |
| GET | `/api/crm/leads/<id>/activities` | Yes | Activity log |
| POST | `/api/crm/leads/<id>/activities` | Yes | Log activity |
| GET | `/api/daily_revenue_queue` | Yes | Scored revenue priority queue |

---

## Dashboard

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/dashboard/summary` | Yes | Revenue snapshot, hot leads, stuck deals, bottlenecks, AI recs |

---

## Approvals

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/approvals` | Yes | List pending approvals |
| POST | `/api/approvals/<id>` | Yes | Resolve approval (`action=approve\|deny`) |

Sensitive flow: every approval follows Intent → Preview → Approval → Execute → Audit Log.

---

## Outreach

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/outreach/queue` | Yes | Pending outreach queue |
| POST | `/api/outreach/execute` | Yes | Execute outreach task |
| GET | `/api/outreach/summary` | Yes | Outreach summary |
| GET | `/api/outreach/pipeline` | Yes | Outreach pipeline |

---

## SEO Engine

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/seo/meta` | Yes | Meta descriptions (6 pages, ≤155 chars each) |
| GET | `/api/seo/cities` | Yes | City landing pages (4 cities) |
| GET | `/api/seo/blog` | Yes | Blog posts (3 posts, Hebrew) |
| GET | `/api/seo/images` | Yes | Adobe Firefly image prompts (8 prompts) |

All SEO responses are deterministic (no AI). Language: Hebrew.

---

## Admin

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/admin/status` | Yes | Business config + DB record counts |
| GET | `/api/admin/usage` | Yes | Today's activity counts by type |

---

## Telegram Webhook

```
POST /api/telegram/webhook
Header: X-Telegram-Token: <WEBHOOK_VERIFY_TOKEN>
```

Handles inbound text commands and inline keyboard callbacks (`approve:`, `deny:`, `edit:`).
See `docs/TELEGRAM.md` for full flow.

---

## External Bridges (Orchestration Only)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/claude/preview` | Yes | Preview sensitive action |
| POST | `/api/claude/dispatch` | Yes | Dispatch via Claude bridge |
| GET | `/api/claude/tasks/<id>` | Yes | Get task status |
| GET/POST | `/api/gpt/*` | Yes | GPT connector — review, redispatch |
| POST | `/api/mcp` | No | MCP endpoint — `get_latest_claude_task` |

These are orchestration interfaces. Core business logic is unaffected if they are unavailable.

---

## Response Envelope

All responses use this envelope:

```json
{
  "data":    { ... },
  "error":   null,
  "success": true,
  "ts":      "2026-04-10T13:42:09.542493+00:00"
}
```
