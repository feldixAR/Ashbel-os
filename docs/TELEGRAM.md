# AshbelOS — Telegram Integration

> Wave One approved channel. No other execution channels are active.
> Governance source: `docs/ashbelos-governance.md` §Wave One External Channels

---

## Overview

Telegram is the sole approved external execution channel for AshbelOS (Wave One).

Two flows are handled:
1. **Inbound text command** → orchestrator dispatch → reply
2. **Inline button callback** → approval resolution → execute outreach

---

## Webhook Endpoint

```
POST /api/telegram/webhook
Header: X-Telegram-Token: <WEBHOOK_VERIFY_TOKEN>
```

Authentication is header-based. If `WEBHOOK_VERIFY_TOKEN` is set and the header does not match, the request is rejected with HTTP 401.

---

## Flow 1: Inbound Text Command

```
Telegram message → POST /api/telegram/webhook
→ orchestrator.handle_command(text, source="telegram")
→ result.message sent back via telegram_service.send()
```

Any Hebrew or English command accepted by the intent parser can be sent via Telegram.

---

## Flow 2: Approval via Inline Keyboard

When the system generates an outreach task pending approval, `telegram_service.send_approval_request()` sends a message with three inline buttons:

| Button | `callback_data` | Action |
|--------|----------------|--------|
| ✅ אשר | `approve:{approval_id}` | Approves and executes outreach |
| ❌ דחה | `deny:{approval_id}` | Denies, no outreach sent |
| ✏️ ערוך | `edit:{approval_id}` | Prompts operator for revised text |

### Callback Resolution

```
callback_query → _handle_callback()
→ action, approval_id = data.split(":", 1)
→ _resolve_approval(approval_id, action, source="telegram")
→ execute_outreach() if approved
→ telegram_service.answer_callback(cbq_id, "✅ בוצע" | "❌ נדחה")
```

`_resolve_approval()` is shared between the Telegram webhook and the REST API (`POST /api/approvals/{id}`), ensuring identical behavior from both surfaces.

---

## Outbound Notifications

`telegram_service.send(text)` is called for:
- Replies to inbound commands
- New lead notifications (from GmailListener, LeadScraper)
- ERROR/CRITICAL log events (via StructuredLogger)
- Weekly health report (from MaintenanceAgent, Sunday 07:00)

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot API token from @BotFather |
| `TELEGRAM_CHAT_ID` | Target chat/channel for outbound messages |
| `WEBHOOK_VERIFY_TOKEN` | Authenticates inbound webhook requests |

---

## Failure Behavior

See `docs/FALLBACK.md` §Telegram Service Unavailable.

---

## Excluded

- WhatsApp execution: route exists, not expanded
- Email: not approved
- Calendar: not approved
