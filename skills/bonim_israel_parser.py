"""Parser helpers for Bonim Israel private construction lead files."""

from __future__ import annotations

import re

STAGE_WORDS = {"שלד", "טיח", "עבודות גמר", "יסודות"}


def looks_like_headers(headers: list[str]) -> bool:
    joined = " ".join(str(h or "") for h in headers)
    needles = ["שלב", "מיקום האתר", "בעלים", "איש קשר", "בקשות"]
    return sum(1 for needle in needles if needle in joined) >= 3


def looks_like_text(text: str) -> bool:
    if not text:
        return False
    return "מיקום האתר" in text and "בעלים" in text and ("בקשות" in text or "איש קשר" in text)


def normalize_rows(rows: list[list]) -> list[dict]:
    if not rows:
        return []
    idx = _column_map([str(h or "").strip() for h in rows[0]])
    records: list[dict] = []
    for row in rows[1:]:
        if not any(str(cell or "").strip() for cell in row):
            continue
        rec = _record(
            stage=_cell(row, idx.get("stage")),
            city=_cell(row, idx.get("city")),
            owner=_cell(row, idx.get("owner")),
            contact=_cell(row, idx.get("contact")),
            notes=_cell(row, idx.get("notes")),
        )
        if rec["name"] or rec["phone"] or rec["email"]:
            records.append(rec)
    return records


def normalize_text(text: str) -> list[dict]:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    records: list[dict] = []
    i = 0
    while i < len(lines):
        if lines[i] not in STAGE_WORDS:
            i += 1
            continue
        stage = lines[i]
        city = lines[i + 1] if i + 1 < len(lines) else ""
        owner = lines[i + 2] if i + 2 < len(lines) else ""
        block: list[str] = []
        j = i + 3
        while j < len(lines) and lines[j] not in STAGE_WORDS:
            block.append(lines[j])
            j += 1
        contact_parts: list[str] = []
        note_parts: list[str] = []
        for part in block:
            if _is_contact_line(part):
                contact_parts.append(part)
            else:
                note_parts.append(part)
        rec = _record(stage, city, owner, " ".join(contact_parts), " ".join(note_parts))
        if rec["name"] or rec["phone"] or rec["email"]:
            records.append(rec)
        i = j
    return records


def _column_map(headers: list[str]) -> dict:
    idx: dict[str, int] = {}
    for i, h in enumerate(headers):
        if "שלב" in h:
            idx["stage"] = i
        elif "מיקום" in h or "אתר" in h:
            idx["city"] = i
        elif "בעלים" in h:
            idx["owner"] = i
        elif "איש קשר" in h or "טל" in h:
            idx["contact"] = i
        elif "בקשות" in h or "שיחת" in h:
            idx["notes"] = i
    return idx


def _record(stage: str, city: str, owner: str, contact: str, notes: str) -> dict:
    merged = " ".join([contact or "", notes or ""]).strip()
    return {
        "name": (owner or "").strip(),
        "phone": _phone(merged),
        "email": _email(merged),
        "city": (city or "").strip(),
        "company": "",
        "role": "",
        "notes": (notes or merged[:300]).strip(),
        "work_type": "אלומיניום" if "אלומיניום" in merged else "",
        "project_stage": (stage or "").strip(),
        "estimated_value": 0,
        "address": (city or "").strip(),
        "decision_maker": _contact_name(contact) or (owner or "").strip(),
        "missing_photos": True,
        "missing_plans": True,
        "missing_measurements": True,
        "source_type": "bonim_import",
    }


def _is_contact_line(value: str) -> bool:
    return bool(value and (":" in value or "טל" in value or "פניות במייל בלבד" in value or _phone(value)))


def _contact_name(value: str) -> str:
    if not value or "פניות במייל בלבד" in value:
        return ""
    return value.split(":", 1)[0].strip() if ":" in value else ""


def _email(value: str) -> str:
    match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}", value or "")
    return match.group(0) if match else ""


def _phone(value: str) -> str:
    match = re.search(r"(?:\+?972[-\s]?)?0?5\d[-\s]?\d{3}[-\s]?\d{4}", value or "")
    if not match:
        return ""
    digits = re.sub(r"\D", "", match.group(0))
    if digits.startswith("972"):
        digits = "0" + digits[3:]
    if len(digits) == 9 and digits.startswith("5"):
        digits = "0" + digits
    return digits


def _cell(row: list, idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return str(row[idx] or "").strip()
