"""
services/intake/normalizer.py — Unified channel-agnostic intake normalization.
Phase 2: Full channel-native intake layer.

Accepts raw payloads from any connected interface (Telegram-first) and
normalizes them into a single IntakePayload for routing through the
existing pipeline: classify → preview → approval → execute → audit.

Modalities handled:
  text       — free text / commands
  voice      — audio file (download + transcription attempt)
  document   — Word, Excel, CSV, PDF → document_intelligence
  image      — photo/sticker (description only for now)
  contact    — shared Telegram contact → inbound lead signal
  location   — shared location → geo context
  link       — URL in text → website_analysis candidate
  reaction   — emoji reaction (logged, no action)
  unknown    — passthrough with raw dump

AshbelOS remains source of truth. This layer is pure normalization —
no DB writes, no AI calls (except transcription fallback), no side effects.
"""

from __future__ import annotations
import logging
import os
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class IntakePayload:
    source:            str          # "telegram" | "whatsapp" | "api"
    sender:            str          # username / phone / agent_id
    modality:          str          # "text" | "voice" | "document" | "image" | "contact" | "location" | "link" | "reaction" | "unknown"
    raw_content:       str          # original text or fallback description
    extracted_content: str          # cleaned text after transcription / extraction
    structured_fields: dict         # extracted entities {name, phone, city, company, ...}
    business_meaning:  str          # "business_action" | "inbound_lead" | "document_upload" | "website_task" | "system_change" | "unknown"
    urgency:           str          # "high" | "normal" | "low"
    sensitivity:       str          # "sensitive" | "normal"
    required_action:   str          # "execute_command" | "process_lead" | "parse_document" | "preview_system_change" | "log_only"
    attachments:       list         = field(default_factory=list)   # [{type, file_id, mime_type, file_name, size}]
    metadata:          dict         = field(default_factory=dict)   # raw message metadata (chat_id, message_id, date, ...)


# ── Telegram normalizer ───────────────────────────────────────────────────────

def normalize_telegram(message: dict, source: str = "telegram") -> IntakePayload:
    """
    Accept a raw Telegram message dict and return a normalized IntakePayload.
    Handles all native Telegram payload types.
    """
    sender = _tg_sender(message)
    meta   = _tg_meta(message)

    # ── text ─────────────────────────────────────────────────────────────────
    text = (message.get("text") or "").strip()
    if text:
        return _classify_text(text, sender, source, meta)

    # ── voice ─────────────────────────────────────────────────────────────────
    voice = message.get("voice") or message.get("audio")
    if voice:
        return _handle_voice(voice, sender, source, meta)

    # ── document (Word, Excel, PDF, CSV, any file) ────────────────────────────
    doc = message.get("document")
    if doc:
        return _handle_document(doc, sender, source, meta)

    # ── photo / sticker ───────────────────────────────────────────────────────
    photo = message.get("photo") or message.get("sticker")
    if photo:
        return _handle_photo(photo, sender, source, meta)

    # ── contact ───────────────────────────────────────────────────────────────
    contact = message.get("contact")
    if contact:
        return _handle_contact(contact, sender, source, meta)

    # ── location ──────────────────────────────────────────────────────────────
    location = message.get("location")
    if location:
        return _handle_location(location, sender, source, meta)

    # ── reaction (message_reaction) ───────────────────────────────────────────
    if message.get("reactions") or message.get("new_reaction"):
        return IntakePayload(
            source=source, sender=sender, modality="reaction",
            raw_content="reaction", extracted_content="",
            structured_fields={}, business_meaning="unknown",
            urgency="low", sensitivity="normal",
            required_action="log_only", metadata=meta,
        )

    # ── caption (image with text) ─────────────────────────────────────────────
    caption = (message.get("caption") or "").strip()
    if caption:
        return _classify_text(caption, sender, source, meta)

    return IntakePayload(
        source=source, sender=sender, modality="unknown",
        raw_content=str(message)[:200], extracted_content="",
        structured_fields={}, business_meaning="unknown",
        urgency="low", sensitivity="normal",
        required_action="log_only", metadata=meta,
    )


# ── Internal handlers ─────────────────────────────────────────────────────────

def _classify_text(text: str, sender: str, source: str, meta: dict) -> IntakePayload:
    """Classify a text payload into business_meaning and required_action."""
    tl = text.lower()

    # System change detection
    system_triggers = [
        "הוסף ווידג'ט", "שנה ui", "צור מודול", "צור טאב", "הוסף טאב",
        "הוסף עמוד", "שנה עיצוב", "עדכן ui", "הוסף פאנל", "צור פאנל",
        "add widget", "add module", "add tab", "change ui", "modify ui",
        "create module", "add page", "שנה מראה", "עדכן מראה",
    ]
    if any(t in tl for t in system_triggers):
        return IntakePayload(
            source=source, sender=sender, modality="text",
            raw_content=text, extracted_content=text,
            structured_fields={"request": text},
            business_meaning="system_change",
            urgency="normal", sensitivity="sensitive",
            required_action="preview_system_change", metadata=meta,
        )

    # Inbound lead detection (someone asking about a product/service)
    lead_triggers = [
        "מחיר", "עלות", "כמה עולה", "מתעניין", "מעוניין", "רוצה להזמין",
        "חלון", "דלת", "פרגולה", "אלומיניום", "תריס", "price", "interested",
        "צור קשר", "פנה אלי", "התקשר", "ליד נכנס",
    ]
    if any(t in tl for t in lead_triggers):
        fields = _extract_lead_fields_from_text(text, sender)
        return IntakePayload(
            source=source, sender=sender, modality="text",
            raw_content=text, extracted_content=text,
            structured_fields=fields,
            business_meaning="inbound_lead",
            urgency="high", sensitivity="normal",
            required_action="process_lead", metadata=meta,
        )

    # Website task
    if any(t in tl for t in ["http", "www.", "אתר", "site audit", "ניתוח אתר"]):
        url = _extract_url(text)
        return IntakePayload(
            source=source, sender=sender, modality="link" if url else "text",
            raw_content=text, extracted_content=url or text,
            structured_fields={"url": url} if url else {},
            business_meaning="website_task",
            urgency="normal", sensitivity="normal",
            required_action="execute_command", metadata=meta,
        )

    # Default: business action / command
    return IntakePayload(
        source=source, sender=sender, modality="text",
        raw_content=text, extracted_content=text,
        structured_fields={}, business_meaning="business_action",
        urgency="normal", sensitivity="normal",
        required_action="execute_command", metadata=meta,
    )


def _handle_voice(voice: Any, sender: str, source: str, meta: dict) -> IntakePayload:
    """
    Handle voice message. Downloads and attempts transcription.
    Falls back gracefully — never blocks the pipeline.
    """
    file_id   = voice.get("file_id") if isinstance(voice, dict) else ""
    duration  = voice.get("duration", 0) if isinstance(voice, dict) else 0
    mime_type = voice.get("mime_type", "audio/ogg") if isinstance(voice, dict) else "audio/ogg"

    transcript = _attempt_transcription(file_id, mime_type)

    attachments = [{"type": "voice", "file_id": file_id,
                    "mime_type": mime_type, "duration": duration}]

    if transcript:
        # Re-classify now that we have text
        payload = _classify_text(transcript, sender, source, meta)
        payload.modality = "voice"
        payload.raw_content = f"[voice {duration}s] {transcript}"
        payload.attachments = attachments
        return payload

    # No transcript — ask user to type
    return IntakePayload(
        source=source, sender=sender, modality="voice",
        raw_content=f"[voice message {duration}s]",
        extracted_content="",
        structured_fields={"file_id": file_id, "duration": duration},
        business_meaning="unknown",
        urgency="normal", sensitivity="normal",
        required_action="request_text_fallback",
        attachments=attachments, metadata=meta,
    )


def _handle_document(doc: dict, sender: str, source: str, meta: dict) -> IntakePayload:
    """Handle document upload. Routes to document intelligence pipeline."""
    file_id   = doc.get("file_id", "")
    file_name = doc.get("file_name", "")
    mime_type = doc.get("mime_type", "")
    file_size = doc.get("file_size", 0)

    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    parseable = ext in ("csv", "xlsx", "xls", "docx", "doc", "txt", "pdf")

    attachments = [{"type": "document", "file_id": file_id,
                    "mime_type": mime_type, "file_name": file_name,
                    "file_size": file_size, "ext": ext}]

    return IntakePayload(
        source=source, sender=sender, modality="document",
        raw_content=f"[document: {file_name}]",
        extracted_content="",
        structured_fields={"file_id": file_id, "file_name": file_name,
                           "mime_type": mime_type, "ext": ext,
                           "parseable": parseable},
        business_meaning="document_upload",
        urgency="normal", sensitivity="normal",
        required_action="parse_document" if parseable else "log_only",
        attachments=attachments, metadata=meta,
    )


def _handle_photo(photo: Any, sender: str, source: str, meta: dict) -> IntakePayload:
    """Handle photo — log only for now, no OCR."""
    if isinstance(photo, list):
        best = max(photo, key=lambda p: p.get("file_size", 0))
    elif isinstance(photo, dict):
        best = photo
    else:
        best = {}
    file_id = best.get("file_id", "")
    return IntakePayload(
        source=source, sender=sender, modality="image",
        raw_content="[image received]", extracted_content="",
        structured_fields={"file_id": file_id},
        business_meaning="unknown",
        urgency="low", sensitivity="normal",
        required_action="log_only",
        attachments=[{"type": "image", "file_id": file_id}], metadata=meta,
    )


def _handle_contact(contact: dict, sender: str, source: str, meta: dict) -> IntakePayload:
    """Handle shared Telegram contact — treat as inbound lead signal."""
    name  = f"{contact.get('first_name','')} {contact.get('last_name','')}".strip()
    phone = contact.get("phone_number", "")
    return IntakePayload(
        source=source, sender=sender, modality="contact",
        raw_content=f"[contact: {name} {phone}]",
        extracted_content=f"ליד נכנס: {name}, {phone}",
        structured_fields={"name": name, "phone": phone,
                           "source_type": "telegram_contact"},
        business_meaning="inbound_lead",
        urgency="high", sensitivity="normal",
        required_action="process_lead", metadata=meta,
    )


def _handle_location(location: dict, sender: str, source: str, meta: dict) -> IntakePayload:
    """Handle shared location — extract geo context."""
    lat = location.get("latitude", 0)
    lon = location.get("longitude", 0)
    return IntakePayload(
        source=source, sender=sender, modality="location",
        raw_content=f"[location: {lat},{lon}]",
        extracted_content=f"מיקום: {lat},{lon}",
        structured_fields={"latitude": lat, "longitude": lon},
        business_meaning="unknown",
        urgency="low", sensitivity="normal",
        required_action="log_only", metadata=meta,
    )


# ── Transcription ─────────────────────────────────────────────────────────────

def _attempt_transcription(file_id: str, mime_type: str) -> str:
    """
    Attempt voice transcription. Uses Telegram file download + Anthropic API.
    Returns empty string on any failure — caller must handle gracefully.
    """
    if not file_id:
        return ""
    try:
        import os, requests, tempfile, base64
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not token or not api_key:
            return ""

        # 1. Get file path from Telegram
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getFile",
            params={"file_id": file_id}, timeout=10,
        )
        resp.raise_for_status()
        file_path = resp.json().get("result", {}).get("file_path", "")
        if not file_path:
            return ""

        # 2. Download file
        file_resp = requests.get(
            f"https://api.telegram.org/file/bot{token}/{file_path}",
            timeout=30,
        )
        file_resp.raise_for_status()
        audio_bytes = file_resp.content
        if len(audio_bytes) > 5 * 1024 * 1024:   # 5 MB limit
            return ""

        # 3. Send to Anthropic with audio support (requires beta header)
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        b64 = base64.standard_b64encode(audio_bytes).decode()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system="Transcribe the following audio to Hebrew text. Return only the transcription.",
            messages=[{
                "role": "user",
                "content": [{
                    "type": "document",
                    "source": {"type": "base64", "media_type": mime_type or "audio/ogg", "data": b64},
                }],
            }],
        )
        transcript = response.content[0].text.strip() if response.content else ""
        log.info(f"[Intake] voice transcribed: {len(transcript)} chars")
        return transcript

    except Exception as e:
        log.debug(f"[Intake] transcription failed (non-critical): {e}")
        return ""


# ── Field extraction helpers ──────────────────────────────────────────────────

def _extract_lead_fields_from_text(text: str, sender: str) -> dict:
    """Extract name/phone/city from raw text heuristically."""
    import re
    phone_match = re.search(r"(\+?[0-9]{9,13})", text)
    phone = phone_match.group(1) if phone_match else ""
    city_candidates = ["תל אביב", "ירושלים", "חיפה", "ראשון לציון",
                       "רחובות", "נס ציונה", "באר שבע", "נתניה", "פתח תקווה"]
    city = next((c for c in city_candidates if c in text), "")
    return {
        "name":        sender or "",
        "phone":       phone,
        "city":        city,
        "message":     text,
        "source_type": "telegram",
    }


def _extract_url(text: str) -> str:
    import re
    m = re.search(r"https?://[^\s]+", text)
    return m.group(0) if m else ""


def _tg_sender(message: dict) -> str:
    frm = message.get("from") or {}
    return frm.get("username") or frm.get("first_name") or str(frm.get("id", "telegram_user"))


def _tg_meta(message: dict) -> dict:
    return {
        "message_id": message.get("message_id"),
        "chat_id":    (message.get("chat") or {}).get("id"),
        "date":       message.get("date"),
        "from_id":    (message.get("from") or {}).get("id"),
    }
