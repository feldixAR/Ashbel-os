# AshbelOS — Telegram Integration

> Wave One approved channel. No other execution channels are active.
> Governance source: `docs/ashbelos-governance.md` §Wave One External Channels

---

## Overview

Telegram is the sole approved external execution channel for AshbelOS (Wave One).

Flows handled:
1. **Inbound text command** → orchestrator dispatch → reply
2. **Inline button callback** → approval resolution → execute outreach
3. **Hot-lead alert** → outbound card when a new lead scores ≥70 (Phase 15)
4. **Inbound approval card** → outbound card when a new inbound lead arrives (Phase 15)
5. **Multi-modal intake** → document/voice/contact routing via normalizer (Phase 16)

---

## Webhook Endpoint

```
POST /api/telegram/webhook
Header: X-Telegram-Token: <WEBHOOK_VERIFY_TOKEN>
```

Authentication is header-based. If `WEBHOOK_VERIFY_TOKEN` is set and the header does not match, the request is rejected with HTTP 401.

All inbound payloads are routed through `services/intake/normalizer.py:normalize_telegram()` which produces a typed `IntakePayload` before dispatch.

---

## Flow 1: Inbound Text Command

```
Telegram message → POST /api/telegram/webhook
→ normalize_telegram(update) → IntakePayload(type="text")
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
→ ActivityModel log entry + LEAD_OUTREACH_SENT event
→ telegram_service.answer_callback(cbq_id, "✅ בוצע" | "❌ נדחה")
```

`_resolve_approval()` is shared between the Telegram webhook and the REST API (`POST /api/approvals/<id>`), ensuring identical audit behavior from both surfaces.

---

## Flow 3: Hot-Lead Alerts (Phase 15)

When a new lead is scored ≥70, `telegram_service` sends an alert card:

```
Lead scored ≥70
→ events/handlers/lead_acquisition_handlers.py: handle LEAD_DISCOVERED
→ telegram_service.send(hot_lead_card)
```

Card content: lead name, city, score, recommended action, timing.

---

## Flow 4: Inbound Approval Cards (Phase 15)

When a new inbound lead is received via any channel:

```
INBOUND_LEAD_RECEIVED event
→ lead_acquisition_handlers: build approval card
→ telegram_service.send_approval_request(inbound_card)
→ operator approves/denies via inline keyboard
```

---

## Flow 5: Multi-Modal Intake (Phase 16)

`services/intake/normalizer.py:normalize_telegram(update)` handles all Telegram payload types:

| Payload Type | Routing |
|-------------|---------|
| `text` | orchestrator.handle_command() |
| `document` | download → base64 → `_handle_parse_document` → process_inbound per record |
| `voice` | fallback response (voice processing not yet active) |
| `contact` | `lead_acquisition_engine.process_inbound(contact_data)` |
| `video` | metadata logged, fallback response |
| `poll` | metadata logged |
| `reply_to` | context attached to text routing |
| `forward` | forward metadata attached, routed as text |

Document parsing supports: CSV, Excel, Word, PDF, TXT — with Hebrew + English column detection.

---

## Outbound Notifications

`telegram_service.send(text)` is called for:
- Replies to inbound commands
- Hot-lead alerts (score ≥70)
- Inbound lead approval cards
- System-change preview cards (approval required before execution)
- New lead notifications (from GmailListener, LeadScraper)
- ERROR/CRITICAL log events (via StructuredLogger)
- Weekly health report (from MaintenanceAgent, Sunday 07:00 IL)

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

- WhatsApp execution: route exists, not expanded (Wave One policy)
- Email: not approved
- Calendar: not approved
