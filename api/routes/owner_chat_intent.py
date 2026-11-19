"""Recognize explicit Hebrew work-queue questions without a model call."""

import re
from typing import Literal


_TASK = re.compile(r"\b(?:ה?משימ(?:ה|ות)|ה?מטל(?:ה|ות)|ה?פעול(?:ה|ות))\b")
_TASK_ASK = re.compile(
    r"^(?:אבל )?(?:ו?(?:יש|מה|אילו|איזו|איזה|עוד)|ה?משימ(?:ה|ות)|ה?מטל(?:ה|ות)|"
    r"תראה|תציג|תן|תזכיר|תפרט|תפרוס|תוציא|רשימ[הת]|תור|סדר)(?: |$)"
)
_MORE = re.compile(r"\b(?:ו?עוד|ו?נוספ(?:ת|ות)|יתר|שאר|מה נשאר)\b")
_TASK_OTHER_ACTION = re.compile(r"\b(?:לנסח|לכתוב|סיכום|להוסיף|למחוק|להעביר|לשייך)\b")
_REPORT = re.compile(
    r"^(?:עדכון|דיברתי|אמרתי|אמרנו|הסברתי|עדכנתי|שלחתי|קיבלתי|נפגשתי|הלקוח אישר)(?: |$)"
)
_NOT_A_CALL = re.compile(
    r"\b(?:אין לחדש|אין לפנות|אין להתקשר|אין לחייג|לא לפנות|לא להתקשר|לא לחייג|"
    r"לא לחזור|לא לחדש|אסור לפנות|תיאום בלבד|ללא פנייה|ללא שיחה|ללא חיוג|"
    r"בהשהיה|בהקפאה|בהמתנה|ממתינ(?:ה|ים|ות)|ממתין|טרם אושר|לא אושר|שיתוף פעולה)\b"
)
_CALL_STEP = re.compile(
    r"(?:^|[.;:!\n])\s*(?:[•*\-–—]\s*)?(?:(?:יש|נא|צריך|עמית)\s+)?"
    r"(?:לתת לו שיחה|להתקשר|לחייג|לחזור(?: אלי(?:ו|הם|ה)| ללקוח)? טלפונית|"
    r"שיחת (?:המשך|מעקב|היכרות|מכירה)|שיחה (?:טלפונית|ללקוח))\b"
)
_CALL_CONDITION = re.compile(r"\b(?:אם|אחרי|לאחר|בכפוף|בתנאי|כשיתקבל|כשיסתיים|כשיגיע)\b")
_CALL_ORDER = re.compile(
    r"^(?:ו?(?:מי|מה|מתי|איזו|אילו) (?:ה?שיח(?:ה|ות)|ה?חיוג(?:ים)?) (?:שלי )?"
    r"(?:הבא(?:ה|ים|ות)?|הקרוב(?:ה|ים|ות)?|ל?היום)|"
    r"(?:תראה|תציג|תן|תזכיר) (?:לי )?(?:את )?(?:רשימת|תור|סדר) (?:ה?שיחות|ה?חיוג(?:ים)?)|"
    r"(?:רשימת|תור|סדר) (?:ה?שיחות|ה?חיוג(?:ים)?))(?: |$)"
)
_CALL_WHO = re.compile(
    r"^(?:(?:תזכיר|תראה|תציג) לי )?(?:ו?למי|ו?מי|עם מי|אילו לקוחות|לאיזה לקוחות)\b.*"
    r"\b(?:להתקשר|לחייג|לחזור|לדבר|בשיחה טלפונית)(?: |$)"
)
_NEXT_PERSON = re.compile(r"^(?:ו?מי|ו?למי) (?:הלקוח הבא|האדם הבא|הבא בתור|הלקוחות הבאים)(?: |$)")
_SINGULAR_CALL = re.compile(r"\b(?:הלקוח הבא|האדם הבא|השיחה הבאה|הבא בתור|הראשון)\b")


def queue_intent(words: str) -> Literal["tasks", "more", "calls"] | None:
    """Return a queue intent only when the phrasing has a recognizable queue signal."""
    if _REPORT.match(words):
        return None
    if _CALL_ORDER.match(words) or _CALL_WHO.match(words) or _NEXT_PERSON.match(words):
        return "calls"
    if _TASK_ASK.match(words) and _TASK.search(words) and not _TASK_OTHER_ACTION.search(words):
        return "more" if _MORE.search(words) else "tasks"
    if re.fullmatch(r"(?:ו?מה עוד(?: נשאר לי לעשות)?|יש עוד|תמשיך(?: עם הרשימה)?|תן לי עוד|עוד)", words):
        return "more"
    return None


def call_limit(words: str) -> int:
    return 1 if _SINGULAR_CALL.search(words) else 3


def is_call_candidate(item: dict) -> bool:
    """Require an actual outbound-call step on an eligible customer action."""
    if item.get("kind") != "customer" or item.get("disposition") != "actionable" or item.get("blocked_reasons"):
        return False
    action = item.get("action") or ""
    combined = f"{action} {item.get('status') or ''} {item.get('subject') or ''}"
    if _NOT_A_CALL.search(combined) or _CALL_CONDITION.search(action):
        return False
    return bool(_CALL_STEP.search(action))
