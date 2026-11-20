"""Queue projections and fallback routing for the owner conversation."""

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
    r"בהשהיה|בהקפאה|בהמתנה|ממתינ(?:ה|ים|ות)|ממתין|טרם אושר|לא אושר)\b"
)
# These expressions describe recorded work, never the owner's incoming phrasing.
_CALL_STEP = re.compile(
    r"\b(?:לחייג|להתקשר|לשוחח|לחזור [^.;]{0,25}טלפונית)\b|"
    r"(?:^|[.;:\n])\s*(?:שתי |שלוש )?(?:שיחות|שיחת|שיחה)\s+"
)
_CALL_PREP = re.compile(r"\b(?:להכין|להיערך|לתכנן|הכנת)\b[^.!?;\n]{0,60}\b(?:שיח[הת]|שיחות)\b")
_CALL_APPROVAL = re.compile(r"(?:נדרש|צריך|דרוש|לקבל|בכפוף ל)\s*אישור|רק (?:לאחר|עם|באמצעות) (?:קבלת )?אישור")
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


def call_limit(words: str) -> int | None:
    return 1 if _SINGULAR_CALL.search(words) else None


def _call_stage(item: dict) -> str | None:
    action = item.get("action") or ""
    status = item.get("status") or ""
    if item.get("disposition") == "completed" or not (_CALL_STEP.search(action) or _CALL_PREP.search(action)):
        return None
    # A history entry or an instruction forbidding a call is never a call task.
    if _NOT_A_CALL.search(action):
        return None
    if item.get("disposition") != "actionable" or item.get("blocked_reasons") or _NOT_A_CALL.search(status):
        return "לבירור לפני חיוג"
    if _CALL_APPROVAL.search(f"{action} {status}"):
        return "נדרש אישור לפני פנייה"
    if _CALL_PREP.search(action):
        return "הכנת שיחה"
    if _CALL_CONDITION.search(action):
        return "מותנה בבדיקה"
    return "למעקב טלפוני"


def call_queue_reply(context, *, limit=None, exclude=None, offset=0):
    """Show sourced call work across customers, suppliers and partners, without dialing."""
    groups = {}
    for item in [*context.get("actions", []), *context.get("lead_followups", [])]:
        stage = _call_stage(item)
        if stage and item["subject"] != exclude:
            groups.setdefault(stage, []).append(item)
    if not groups:
        return "לא נמצאו משימות חיוג או הכנת שיחה ברשומות שנבדקו בתור העבודה ובמעקבי הלידים.", 0

    stages = ("למעקב טלפוני", "הכנת שיחה", "נדרש אישור לפני פנייה", "לבירור לפני חיוג", "מותנה בבדיקה")
    total = sum(map(len, groups.values()))
    counts = " · ".join(f"{stage} {len(groups[stage])}" for stage in stages if stage in groups)
    header = f"שיחות בתור העבודה ובמעקבי הלידים ({total})\n{counts}"
    ordered = [(stage, item) for stage in stages
               for item in sorted(groups.get(stage, []), key=lambda row: row.get("due_date") or "9999")]
    lines = []
    offset = max(0, offset)
    if offset >= total:
        return f"כל {total} משימות השיחה ברשימה הוצגו.", 0
    # Telegram counts UTF-16 code units. Reserve room for the page indicator.
    budget = 3970 - len(header.encode("utf-16-le")) // 2
    for stage, item in ordered[offset:]:
        subject = item["subject"].splitlines()[0][:160]
        action = item["action"].split(";", 1)[0].strip()
        action = action[:180].rsplit(" ", 1)[0] + "…" if len(action) > 180 else action
        due = item.get("due_date")
        detail = f"{action} · מועד רשום {due}" if due else action
        if stage == "לבירור לפני חיוג" and item.get("source_type") == "lead_followup":
            detail += " · לבדוק אם כבר בוצע מעקב ומה הסטטוס העדכני."
        phone = item.get("phone") or ""
        if re.fullmatch(r"[+0-9() \-]{8,20}", phone):
            detail += f"\n{phone}"
        line = f"{subject} · {stage}\n{detail}"
        units = len(line.encode("utf-16-le")) // 2 + 2
        if units > budget or (limit is not None and len(lines) >= limit):
            break
        budget -= units
        lines.append(line)
    remaining = total - offset - len(lines)
    footer = [f"עוד {remaining} משימות שיחה בהמשך הרשימה."] if remaining else []
    return "\n\n".join([header, *lines, *footer]), len(lines)


def previous_contacts(context, state):
    """Resolve only phones that appeared in the last answer and still match their CRM row."""
    previous = state.get("last_answer") or ""
    positions = []
    for row in [*context.get("actions", []), *context.get("lead_followups", [])]:
        name = row["subject"].splitlines()[0]
        phone = row.get("phone") or ""
        if not re.fullmatch(r"(?:0|\+972[- ]?)\d{1,2}[- ]?\d{7}", phone):
            continue
        for block in previous.split("\n\n"):
            if block.splitlines() and block.splitlines()[0] in (name, name + " · " + (_call_stage(row) or "")) and phone in block.splitlines()[1:]:
                positions.append((previous.index(block), row))
                break
    positions.sort(key=lambda entry: entry[0])
    return {f"c{i}": row for i, (_, row) in enumerate(positions, 1)}
