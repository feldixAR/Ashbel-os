"""
entity_extractor.py — Hebrew NLP entity extraction.

Extracts structured entities from free Hebrew/English business text:
    names, phones, cities, dates, WhatsApp contacts, lead sources, etc.

No external dependencies — pure Python regex + lookup tables.
"""

import re
import datetime
from typing import Dict, Any, Optional


CITIES_HE = {
    "תל אביב", "ירושלים", "חיפה", "באר שבע", "ראשון לציון",
    "פתח תקווה", "אשדוד", "נתניה", "בני ברק", "חולון",
    "רמת גן", "אשקלון", "רחובות", "בת ים", "הרצליה",
    "כפר סבא", "מודיעין", "לוד", "רמלה", "נהריה",
    "עפולה", "חדרה", "כרמיאל", "טבריה", "צפת",
    "דימונה", "אילת", "קריית גת", "קריית שמונה", "עכו",
    "נצרת", "יבנה", "קריית אתא", "קריית ביאליק",
    "אור יהודה", "אלעד", "רעננה", "הוד השרון", "גבעתיים",
    "גבעת שמואל", "פרדס חנה", "זכרון יעקב", "עומר",
    "מגדל העמק", "שפרעם", "יוקנעם", "טמרה",
}

DAY_NAMES_HE = {
    "ראשון": 0, "שני": 1, "שלישי": 2, "רביעי": 3,
    "חמישי": 4, "שישי": 5, "שבת": 6,
}

SOURCE_KEYWORDS = {
    "אינסטגרם": "instagram", "instagram": "instagram",
    "פייסבוק":  "facebook",  "facebook":  "facebook",
    "אתר":      "website",   "website":   "website",
    "וואטסאפ": "whatsapp",  "whatsapp":  "whatsapp",
    "המלצה":    "referral",  "חבר":       "referral",
    "גוגל":     "google",    "google":    "google",
    "ידני":     "manual",
}

STATUS_KEYWORDS = {
    "חם": "מתעניין", "חמה": "מתעניין",
    "מתעניין": "מתעניין", "מעוניין": "מתעניין",
    "לא מעוניין": "סגור_הפסיד",
    "סגור": "סגור_זכה", "סגרנו": "סגור_זכה",
    "חדש": "חדש",
    "ניסיון": "ניסיון קשר", "התקשרתי": "ניסיון קשר", "לא ענה": "ניסיון קשר",
}

# Hebrew "stop words" that are NOT names
_STOP_WORDS = {
    "ליד", "לידים", "הוסף", "תוסיף", "צור", "חדש", "חדשה",
    "לקוח", "לקוחה", "הודעה", "פגישה", "שלח", "שלחי",
    "תשלח", "תשלחי", "תזכיר", "תזכירי", "יומן",
    "מלון", "בית", "חנות", "משרד",
}


class EntityExtractor:

    def extract(self, text: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        phone = self._extract_phone(text)
        if phone:
            result["phone"] = phone

        city = self._extract_city(text, phone)
        if city:
            result["city"] = city

        name = self._extract_name(text, city, phone)
        if name:
            result["name"] = name

        contact = self._extract_contact_name(text)
        if contact and contact != name:
            result["contact_name"] = contact

        date_str = self._extract_date(text)
        if date_str:
            result["date"] = date_str

        source = self._extract_source(text)
        if source:
            result["source"] = source

        status = self._extract_status(text)
        if status:
            result["status"] = status

        notes = self._extract_notes(text)
        if notes:
            result["notes"] = notes

        return result

    # ── Phone ─────────────────────────────────────────────────────────────────

    def _extract_phone(self, text: str) -> Optional[str]:
        patterns = [
            r"0\d{1,2}[-\s]?\d{3}[-\s]?\d{4}",
            r"0\d{8,9}",
            r"\+972[-\s]?\d{1,2}[-\s]?\d{7,8}",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return re.sub(r"[\s\-]", "", m.group())
        return None

    # ── City ──────────────────────────────────────────────────────────────────

    def _extract_city(self, text: str, phone: Optional[str] = None) -> Optional[str]:
        # Remove phone from text before city search
        clean = text
        if phone:
            clean = clean.replace(phone, "")

        # Explicit keyword
        m = re.search(r"(?:עיר|מעיר)[=:\s]+([^\s,\d]+(?:\s+[^\s,\d]+)?)", clean)
        if m:
            return m.group(1).strip()

        # Longest match from known list
        for city in sorted(CITIES_HE, key=len, reverse=True):
            if city in clean:
                return city
        return None

    # ── Name ──────────────────────────────────────────────────────────────────

    def _extract_name(self, text: str, city: Optional[str],
                      phone: Optional[str]) -> Optional[str]:
        # Remove phone and city from text for cleaner name extraction
        clean = text
        if phone:
            clean = clean.replace(phone, "")
        if city:
            clean = clean.replace(city, "")

        # Explicit: שם=יוסי כהן
        m = re.search(r"שם[=:\s]+([^\d,/\n]{2,30}?)(?:\s*(?:עיר|טלפון|מקור|,|$))", clean)
        if m:
            candidate = m.group(1).strip()
            return self._clean_name(candidate)

        # After lead trigger word: הוסף ליד X / צור ליד X
        m = re.search(
            r"(?:הוסף|תוסיף|צור)\s+ליד\s+([א-תa-zA-Z]+(?:\s+[א-תa-zA-Z]+)?)",
            clean
        )
        if m:
            return self._clean_name(m.group(1).strip())

        # After: ליד X (standalone)
        m = re.search(r"^ליד\s+([א-תa-zA-Z]+(?:\s+[א-תa-zA-Z]+)?)", clean.strip())
        if m:
            return self._clean_name(m.group(1).strip())

        return None

    def _clean_name(self, candidate: str) -> Optional[str]:
        """Remove stop words and validate name candidate."""
        parts = candidate.strip().split()
        parts = [p for p in parts if p not in _STOP_WORDS and len(p) > 1]
        if not parts:
            return None
        result = " ".join(parts[:3])  # max 3 words for a name
        return result if len(result) >= 2 else None

    # ── Contact name (messaging/meeting) ──────────────────────────────────────

    def _extract_contact_name(self, text: str) -> Optional[str]:
        patterns = [
            r"(?:הודעה|message)\s+ל(?:ל)?([א-תa-zA-Z]{2,15})",
            r"(?:פגישה|meeting)\s+עם\s+([א-תa-zA-Z]{2,15})",
            r"(?:שלח|תשלח|שלחי|תשלחי)\s+(?:הודעה\s+)?ל([א-תa-zA-Z]{2,15})",
            r"(?:לחזור|להתקשר)\s+(?:ל|אל)\s*([א-תa-zA-Z]{2,15})",
            r"(?:קבע|תקבע|קבעי|תקבעי)\s+פגישה\s+עם\s+([א-תa-zA-Z]{2,15})",
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                name = m.group(1).strip()
                if name not in _STOP_WORDS and len(name) >= 2:
                    return name
        return None

    # ── Date ──────────────────────────────────────────────────────────────────

    def _extract_date(self, text: str) -> Optional[str]:
        today = datetime.date.today()

        if "מחר" in text or "tomorrow" in text.lower():
            return (today + datetime.timedelta(days=1)).isoformat()
        if re.search(r"\bהיום\b", text) or "today" in text.lower():
            return today.isoformat()
        if "מחרתיים" in text:
            return (today + datetime.timedelta(days=2)).isoformat()

        # ביום חמישי
        day_pattern = "(" + "|".join(DAY_NAMES_HE.keys()) + ")"
        m = re.search(r"(?:ביום\s+|יום\s+)" + day_pattern, text)
        if m:
            target_dow  = DAY_NAMES_HE[m.group(1)]
            current_dow = today.weekday()
            days_ahead  = (target_dow - current_dow) % 7
            if days_ahead == 0:
                days_ahead = 7
            return (today + datetime.timedelta(days=days_ahead)).isoformat()

        # DD/MM or DD.MM
        m = re.search(r"(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?", text)
        if m:
            day, month = int(m.group(1)), int(m.group(2))
            year = int(m.group(3)) if m.group(3) else today.year
            if year < 100:
                year += 2000
            try:
                return datetime.date(year, month, day).isoformat()
            except ValueError:
                pass

        return None

    # ── Source ────────────────────────────────────────────────────────────────

    def _extract_source(self, text: str) -> Optional[str]:
        tl = text.lower()
        for keyword, source in SOURCE_KEYWORDS.items():
            if keyword in tl or keyword in text:
                return source
        return None

    # ── Status ────────────────────────────────────────────────────────────────

    def _extract_status(self, text: str) -> Optional[str]:
        for keyword, status in STATUS_KEYWORDS.items():
            if keyword in text:
                return status
        return None

    # ── Notes ─────────────────────────────────────────────────────────────────

    def _extract_notes(self, text: str) -> Optional[str]:
        patterns = [
            r"(?:הערה|הערות|note)[=:\s]+(.+?)(?:$|\n)",
            r"(?:אמר\s+ש|הוא\s+אמר\s+ש)(.+?)(?:$|\n|\.)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                note = m.group(1).strip()
                if len(note) > 3:
                    return note
        return None


entity_extractor = EntityExtractor()
