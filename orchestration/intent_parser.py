"""
IntentParser — Hebrew natural language → structured IntentResult.

Two-stage parsing:
  Stage 1: regex/keyword fast-path (free, instant)
  Stage 2: AI fallback for ambiguous input (uses model_router — added Stage 2 Batch 2)

IntentResult contains:
  intent     — canonical intent name (string constant)
  params     — extracted parameters dict
  confidence — 0.0–1.0
  raw        — original command string
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


# ── Intent constants ──────────────────────────────────────────────────────────

class Intent:
    # Lead / CRM
    ADD_LEAD          = "add_lead"
    LIST_LEADS        = "list_leads"
    SCORE_LEADS       = "score_leads"
    UPDATE_LEAD       = "update_lead"

    # Messaging
    GENERATE_MESSAGE  = "generate_message"
    SEND_FOLLOWUP     = "send_followup"

    # Agents / Factory
    CREATE_AGENT      = "create_agent"
    BUILD_AGENT_CODE  = "build_agent_code"
    CREATE_DEPARTMENT = "create_department"
    LIST_AGENTS       = "list_agents"

    # Content / Marketing
    GENERATE_CONTENT  = "generate_content"
    SEO               = "seo"

    # Intelligence
    MARKET_ANALYSIS   = "market_analysis"
    COMPETITOR        = "competitor_analysis"

    # Collaboration
    BRAINSTORM        = "brainstorm"

    # System
    STATUS            = "status"
    REPORT            = "report"
    APPROVE           = "approve"
    HELP              = "help"

    # Fallback
    UNKNOWN           = "unknown"


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class IntentResult:
    intent:     str
    params:     dict          = field(default_factory=dict)
    confidence: float         = 1.0
    raw:        str           = ""
    parse_path: str           = "keyword"   # "keyword" | "ai"

    def is_confident(self, threshold: float = 0.5) -> bool:
        return self.confidence >= threshold

    def __repr__(self) -> str:
        return (
            f"IntentResult(intent={self.intent!r}, "
            f"params={self.params}, "
            f"confidence={self.confidence:.2f}, "
            f"path={self.parse_path!r})"
        )


# ── Keyword rules ─────────────────────────────────────────────────────────────

_KEYWORD_RULES = [

    # ── Lead / CRM ─────────────────────────────────────────────────────────
    (Intent.SCORE_LEADS, 0.95, [
        r"דרג",
        r"דירוג\s+לידים",
        r"score\s+leads",
        r"(?<![א-ת])נקד(?![א-ת])",
    ]),
    (Intent.ADD_LEAD, 0.95, [
        r"הוסף\s+ליד",
        r"ליד\s+חדש",
        r"add\s+lead",
        r"צור\s+ליד",
    ]),
    (Intent.LIST_LEADS, 0.95, [
        r"הצג\s+לידים",
        r"רשימת\s+לידים",
        r"כל\s+הלידים",
        r"list\s+leads",
        r"^לידים$",
    ]),

    # ── Messaging ──────────────────────────────────────────────────────────
    (Intent.GENERATE_MESSAGE, 0.95, [
        r"כתוב\s+הודעה",
        r"צור\s+הודעה",
        r"הודעת\s+פנייה",
        r"הודעה\s+ל",
        r"generate\s+message",
    ]),
    (Intent.SEND_FOLLOWUP, 0.95, [
        r"פולואפ",
        r"follow.?up",
        r"מעקב\s+אחר",
        r"חזור\s+אל",
        r"שלח\s+תזכורת",
    ]),

    # ── Agents / Factory ───────────────────────────────────────────────────
    (Intent.BUILD_AGENT_CODE, 0.95, [
        r"בנ[יה]\s+קוד\s+לסוכן",
        r"בנה\s+קוד\s+לסוכן",
        r"build\s+agent\s+code",
        r"צור\s+קוד\s+לסוכן",
        r"קוד\s+לסוכן",
    ]),
    (Intent.CREATE_DEPARTMENT, 0.95, [
        r"צור\s+מחלקת?\s+\w",
        r"הקם\s+מחלקת?\s+\w",
        r"create\s+department",
        r"מחלקה\s+חדשה",
    ]),
    (Intent.CREATE_AGENT, 0.95, [
        r"צור\s+סוכן",
        r"הוסף\s+סוכן",
        r"create\s+agent",
        r"סוכן\s+חדש",
    ]),
    (Intent.LIST_AGENTS, 0.90, [
        r"הצג\s+סוכנים",
        r"רשימת\s+סוכנים",
        r"כל\s+הסוכנים",
        r"list\s+agents",
        r"סוכנים\s+פעילים",
    ]),

    # ── Content / Marketing ────────────────────────────────────────────────
    (Intent.SEO, 0.95, [
        r"\bseo\b",
        r"קידום\s+אורגני",
        r"מילות\s+מפתח",
        r"כתוב.*?מאמר",
        r"תוכן\s+לאתר",
    ]),
    (Intent.GENERATE_CONTENT, 0.90, [
        r"פוסט\s+ל",
        r"כתוב\s+פוסט",
        r"תוכן\s+שיווקי",
        r"כתוב\s+עבור",
        r"generate\s+content",
        r"תיאור\s+מוצר",
    ]),

    # ── Intelligence ───────────────────────────────────────────────────────
    (Intent.COMPETITOR, 0.95, [
        r"ניתוח\s+מתחר",
        r"מתחר\w*\s+\w",
        r"competitor",
        r"בדוק\s+את\s+\w+\s+(?:בתחום|בשוק)",
    ]),
    (Intent.MARKET_ANALYSIS, 0.90, [
        r"ניתוח\s+שוק",
        r"מחקר\s+שוק",
        r"market\s+anal",
        r"בדוק\s+את\s+השוק",
        r"מגמות\s+ב",
    ]),

    # ── Collaboration ──────────────────────────────────────────────────────
    (Intent.BRAINSTORM, 0.95, [
        r"סיעור\s+מוחות",
        r"brainstorm",
        r"חשבו\s+על",
        r"רעיונות\s+ל",
        r"דונו\s+ב",
    ]),

    # ── System ──────────────────────────────────────────────────────────────
    (Intent.REPORT, 0.95, [
        r"דוח\b",
        r"דו\"ח",
        r"\breport\b",
        r"סיכום\s+יומי",
        r"מה\s+קרה\s+היום",
    ]),
    (Intent.STATUS, 0.95, [
        r"סטטוס",
        r"\bstatus\b",
        r"מה\s+המצב",
        r"מה\s+רץ",
        r"כמה\s+סוכנים",
    ]),
    (Intent.APPROVE, 0.95, [
        r"אשר\b",
        r"approve\b",
        r"תאשר\b",
        r"אישור\b",
    ]),
    (Intent.HELP, 0.95, [
        r"עזרה",
        r"\bhelp\b",
        r"מה\s+אפשר",
        r"פקודות",
    ]),
]


# ── Parameter extractors ──────────────────────────────────────────────────────

def _extract_lead_params(cmd: str) -> dict:
    params = {}

    m = re.search(r"שם\s*[=:]\s*((?:(?!עיר=|טלפון=|מקור=|הערות=)[^\s,])+(?:\s+(?:(?!עיר=|טלפון=|מקור=|הערות=)[^\s,])+)*)", cmd)
    if m:
        params["name"] = m.group(1).strip()
    m = re.search(r"עיר\s*[=:]\s*([^\s,]+)", cmd)
    if m:
        params["city"] = m.group(1).strip()
    m = re.search(r"טלפון\s*[=:]\s*([\d\-+]+)", cmd)
    if m:
        params["phone"] = m.group(1).strip()
    m = re.search(r"מקור\s*[=:]\s*([^\s,]+)", cmd)
    if m:
        params["source"] = m.group(1).strip()
    m = re.search(r"הערות?\s*[=:]\s*(.+?)(?:,|$)", cmd)
    if m:
        params["notes"] = m.group(1).strip()

    if "name" not in params:
        m = re.search(r"(?:תרשום|הוסף|צור)\s+ליד\s+(?:חדש\s+)?([\u05d0-\u05ea]+(?:\s+[\u05d0-\u05ea]+)?)\s+מ", cmd)
        if not m:
            m = re.search(r"ליד\s+חדש\s+([\u05d0-\u05ea]+(?:\s+[\u05d0-\u05ea]+)?)\s+מ", cmd)
        if m:
            params["name"] = m.group(1).strip()
    if "city" not in params:
        m = re.search(r"מ([\u05d0-\u05ea]+(?:\s[\u05d0-\u05ea]+)?)(?:\s+\d|\s*$)", cmd)
        if m:
            params["city"] = m.group(1).strip()
    if "phone" not in params:
        m = re.search(r"(0\d[\d\-]{7,10})", cmd)
        if m:
            params["phone"] = m.group(1).strip()

    return params


def _extract_agent_params(cmd: str) -> dict:
    params = {}

    m = re.search(r"מחלקת?\s+([^\s,]+)", cmd)
    if m:
        params["department"] = m.group(1).strip()

    m = re.search(r"סוכן\s+([^\s,]+(?:\s+[^\s,]+)?)", cmd)
    if m:
        params["role"] = m.group(1).strip()
        params["agent_name"] = m.group(1).strip()

    m = re.search(r"agent\s+([^\s,]+(?:\s+[^\s,]+)?)", cmd, re.IGNORECASE)
    if m:
        params["role"] = m.group(1).strip()
        params["agent_name"] = m.group(1).strip()

    return params


def _extract_content_params(cmd: str) -> dict:
    params = {}
    m = re.search(r"(?:על|about|בנושא)\s+(.+?)(?:\s+ל[^\s]|\s+עבור|$)", cmd)
    if m:
        params["topic"] = m.group(1).strip()

    for ctype in ["linkedin", "אינסטגרם", "instagram", "בלוג", "blog", "מאמר", "article", "פוסט", "post", "ניוזלטר", "newsletter"]:
        if ctype in cmd:
            params["type"] = ctype
            break

    return params


def _extract_topic(cmd: str) -> dict:
    cleaned = re.sub(
        r"^(?:ניתוח\s+שוק|ניתוח\s+מתחרים?|סיעור\s+מוחות|brainstorm|"
        r"דוח|report|בדוק\s+את|מחקר\s+שוק)\s*:?\s*",
        "",
        cmd,
        flags=re.IGNORECASE,
    ).strip()
    return {"topic": cleaned} if cleaned else {}


def _extract_competitor(cmd: str) -> dict:
    m = re.search(r"(?:מתחר\w*|competitor)\s+([^\s,]+(?:\s+[^\s,]+)?)", cmd, re.IGNORECASE)
    if m:
        return {"competitor": m.group(1).strip()}
    return {}


def _extract_status_filter(cmd: str) -> dict:
    for status in ["חדש", "חם", "מתעניין", "ניסיון קשר", "סגור"]:
        if status in cmd:
            return {"status": status}
    return {}


def _extract_approval_id(cmd: str) -> dict:
    m = re.search(r"(?:id|מזהה)\s*[=:]?\s*([a-f0-9\-]{6,36})", cmd, re.IGNORECASE)
    if m:
        return {"approval_id": m.group(1).strip()}
    return {}


_PARAM_EXTRACTORS = {
    Intent.ADD_LEAD: _extract_lead_params,
    Intent.UPDATE_LEAD: _extract_lead_params,
    Intent.LIST_LEADS: _extract_status_filter,
    Intent.CREATE_AGENT: _extract_agent_params,
    Intent.BUILD_AGENT_CODE: _extract_agent_params,
    Intent.CREATE_DEPARTMENT: _extract_agent_params,
    Intent.GENERATE_CONTENT: _extract_content_params,
    Intent.SEO: _extract_content_params,
    Intent.MARKET_ANALYSIS: _extract_topic,
    Intent.COMPETITOR: _extract_competitor,
    Intent.BRAINSTORM: _extract_topic,
    Intent.REPORT: _extract_topic,
    Intent.APPROVE: _extract_approval_id,
}


# ── Parser ────────────────────────────────────────────────────────────────────

class IntentParser:

    def parse(self, command: str) -> IntentResult:
        if not command or not command.strip():
            return IntentResult(intent=Intent.UNKNOWN, raw=command, confidence=0.0)

        raw = command.strip()
        lowered = raw.lower()

        result = self._keyword_parse(raw, lowered)
        if result:
            log.debug(f"[IntentParser] keyword match: {result}")
            return result

        log.debug(f"[IntentParser] no keyword match for: {raw!r} — returning UNKNOWN")
        return IntentResult(
            intent=Intent.UNKNOWN,
            params={"raw_command": raw},
            confidence=0.0,
            raw=raw,
            parse_path="keyword",
        )

    def _keyword_parse(self, raw: str, lowered: str) -> Optional[IntentResult]:
        for intent_name, confidence, patterns in _KEYWORD_RULES:
            for pattern in patterns:
                if re.search(pattern, lowered):
                    params = {}
                    extractor = _PARAM_EXTRACTORS.get(intent_name)
                    if extractor:
                        params = extractor(lowered)
                    return IntentResult(
                        intent=intent_name,
                        params=params,
                        confidence=confidence,
                        raw=raw,
                        parse_path="keyword",
                    )
        return None


intent_parser = IntentParser()
