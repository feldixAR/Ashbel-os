"""
gmail_listener.py — Poll alumashbel@gmail.com for inbound leads.

Uses Gmail API via GMAIL_CREDENTIALS_JSON env var (service account or OAuth).
Falls back to logged/stub mode when credentials not configured.

Keywords detected: אלומיניום, חלון, דלת, הצעת מחיר, קבלן, אדריכל,
                   מעקה, פרגולה, שיפוץ, בנייה, פרויקט
"""

import logging
import os
import re
import datetime

log = logging.getLogger(__name__)

_KEYWORDS = [
    "אלומיניום", "חלון", "דלת", "הצעת מחיר", "קבלן",
    "אדריכל", "מעקה", "פרגולה", "שיפוץ", "בנייה", "פרויקט",
]
_PHONE_RE = re.compile(r'0[5-9]\d[-\s]?\d{3}[-\s]?\d{4}')


def _extract_phone(text: str) -> str:
    m = _PHONE_RE.search(text)
    if m:
        return re.sub(r'[-\s]', '', m.group())
    return ""


def _has_keyword(subject: str, body: str) -> bool:
    combined = (subject + " " + body).lower()
    return any(kw in combined for kw in _KEYWORDS)


def _create_lead_from_email(name: str, email: str, phone: str,
                             subject: str, body: str) -> dict:
    """Dedup by email/phone then create lead. Returns lead dict or None."""
    try:
        from services.storage.repositories.lead_repo import LeadRepository
        from engines.lead_engine import compute_score

        repo = LeadRepository()

        # Dedup by phone
        if phone:
            existing = repo.find_by_phone(phone)
            if existing:
                log.info(f"[GmailListener] dedup — phone {phone} already exists lead={existing.id}")
                return None

        # Dedup by email (name match fallback)
        all_leads = repo.list_all()
        for lead in all_leads:
            if email and getattr(lead, "email", None) == email:
                log.info(f"[GmailListener] dedup — email {email} already exists")
                return None

        lead = repo.create(
            name=name or email.split("@")[0],
            phone=phone or "",
            source="gmail",
            notes=f"נושא: {subject[:100]}",
            status="חדש",
        )
        if not lead:
            return None

        # Auto-score
        try:
            score = compute_score(lead)
            repo.update_score(lead.id, score)
        except Exception:
            pass

        lead_dict = {
            "id":     lead.id,
            "name":   lead.name,
            "phone":  phone,
            "source": "gmail",
            "subject": subject[:100],
        }

        # Telegram notification
        try:
            from services.telegram_service import telegram_service
            telegram_service.send(
                f"📧 *ליד חדש מ-Gmail*\n"
                f"שם: `{lead.name}`\n"
                f"טלפון: `{phone or '—'}`\n"
                f"נושא: {subject[:80]}\n"
                f"מקור: gmail"
            )
        except Exception:
            pass

        return lead_dict

    except Exception as e:
        log.error(f"[GmailListener] _create_lead_from_email error: {e}", exc_info=True)
        return None


def scan_inbox(max_results: int = 20) -> dict:
    """
    Scan Gmail inbox for aluminum-related emails.
    Returns {scanned, leads_created, leads_skipped}.
    Falls back to stub mode when GMAIL_CREDENTIALS_JSON not set.
    """
    creds_json = os.getenv("GMAIL_CREDENTIALS_JSON", "")
    if not creds_json:
        log.info("[GmailListener] GMAIL_CREDENTIALS_JSON not set — stub mode")
        return {"scanned": 0, "leads_created": 0, "leads_skipped": 0, "mode": "stub"}

    try:
        import json, base64
        from googleapiclient.discovery import build
        from google.oauth2.service_account import Credentials

        creds = Credentials.from_service_account_info(
            json.loads(creds_json),
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        )
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)

        results = service.users().messages().list(
            userId="me", maxResults=max_results, q="is:unread"
        ).execute()
        messages = results.get("messages", [])

        created = 0
        skipped = 0

        for msg_ref in messages:
            try:
                msg = service.users().messages().get(
                    userId="me", id=msg_ref["id"], format="full"
                ).execute()

                headers = {h["name"]: h["value"]
                           for h in msg.get("payload", {}).get("headers", [])}
                subject  = headers.get("Subject", "")
                from_hdr = headers.get("From", "")
                # Extract email
                em = re.search(r'<(.+?)>', from_hdr)
                email = em.group(1) if em else from_hdr
                name  = re.sub(r'<.+?>', '', from_hdr).strip().strip('"')

                # Get body snippet
                snippet = msg.get("snippet", "")

                if not _has_keyword(subject, snippet):
                    skipped += 1
                    continue

                phone = _extract_phone(snippet)
                result = _create_lead_from_email(name, email, phone, subject, snippet)
                if result:
                    created += 1
                else:
                    skipped += 1

            except Exception as e:
                log.debug(f"[GmailListener] msg error: {e}")
                skipped += 1

        _log_session(created, skipped)
        return {"scanned": len(messages), "leads_created": created,
                "leads_skipped": skipped, "mode": "live"}

    except Exception as e:
        log.error(f"[GmailListener] scan_inbox error: {e}", exc_info=True)
        return {"scanned": 0, "leads_created": 0, "leads_skipped": 0,
                "mode": "error", "error": str(e)}


def _log_session(created: int, skipped: int) -> None:
    try:
        import pathlib
        sessions_dir = pathlib.Path(__file__).parent.parent.parent / "memory" / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.date.today().isoformat()
        ts    = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
        entry = (f"\n## {ts} UTC — GmailListener\n"
                 f"- leads_created={created} leads_skipped={skipped}\n")
        with open(sessions_dir / f"{today}.md", "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass
