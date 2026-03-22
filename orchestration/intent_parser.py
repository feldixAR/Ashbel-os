"""
IntentParser — Hebrew natural language → structured IntentResult.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


class Intent:
    ADD_LEAD = "add_lead"
    LIST_LEADS = "list_leads"
    SCORE_LEADS = "score_leads"
    UPDATE_LEAD = "update_lead"

    GENERATE_MESSAGE = "generate_message"
    SEND_FOLLOWUP = "send_followup"

    CREATE_AGENT = "create_agent"
    BUILD_AGENT_CODE = "build_agent_code"
    CREATE_DEPARTMENT = "create_department"
    LIST_AGENTS = "list_agents"

    ASSISTANT_MESSAGE = "assistant_message"
    ASSISTANT_MEETING = "assistant_meeting"
    ASSISTANT_DASHBOARD = "assistant_dashboard"
    ASSISTANT_PLAN = "assistant_plan"

    GENERATE_CONTENT = "generate_content"
    SEO = "seo"

    MARKET_ANALYSIS = "market_analysis"
    COMPETITOR = "competitor_analysis"

    BRAINSTORM = "brainstorm"

    STATUS = "status"
    REPORT = "report"
    APPROVE = "approve"
    HELP = "help"

    UNKNOWN = "unknown"


@dataclass
class IntentResult:
    intent: str
    params: dict = field(default_factory=dict)
    confidence: float = 1.0
    raw: str = ""
    parse_path: str = "keyword"

    def is_confident(self, threshold: float = 0.5) -> bool:
        return self.confidence >= threshold


_KEYWORD_RULES = [
    (Intent.ASSISTANT_MESSAGE, 0.95, [
        r"תשלח",
        r"תשלחי",
        r"כתוב.*הודעה",
        r"נסח.*הודעה",
        r"טיוטת.*הודעה",
    ]),
    (Intent.ASSISTANT_MEETING, 0.95, [
        r"תקבע",
        r"תקבעי",
        r"פגישה",
        r"יומן",
        r"קלנדר",
        r"calendar",
    ]),
    (Intent.ASSISTANT_DASHBOARD, 0.95, [
        r"מסך הבית",
        r"דשבורד",
        r"dashboard",
        r"תוסיף.*למסך",
        r"תציג.*במסך",
    ]),
    (Intent.ASSISTANT_PLAN, 0.90, [
        r"תעדכן",
        r"תעדכני",
        r"דיברתי עם",
        r"יש לי רעיון",
        r"תכנן",
        r"תכנני",
    ]),

    (Intent.BUILD_AGENT_CODE, 0.95, [
        r"בנ[יה]\s+קוד\s+לסוכן",
        r"בנה\s+קוד\s+לסוכן",
        r"build\s+agent\s+code",
        r"צור\s+קוד\s+לסוכן",
        r"קוד\s+לסוכן",
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

    (Intent.STATUS, 0.95, [
        r"סטטוס",
        r"\bstatus\b",
        r"מה\s+המצב",
        r"מה\s+רץ",
        r"כמה\s+סוכנים",
    ]),
    (Intent.HELP, 0.95, [
        r"עזרה",
        r"\bhelp\b",
        r"מה\s+אפשר",
        r"פקודות",
    ]),
]


def _extract_agent_params(cmd: str) -> dict:
    params = {}

    m = re.search(r"סוכן\s+([^\s,]+(?:\s+[^\s,]+)?)", cmd)
    if m:
        params["agent_name"] = m.group(1).strip()

    return params


def _extract_assistant_params(cmd: str) -> dict:
    params = {}

    m = re.search(r"ל([א-תA-Za-z][^,\n]*)", cmd)
    if m:
        params["name"] = m.group(1).strip()

    if "שרי" in cmd:
        params["name"] = "שרי"
    if "יוסי" in cmd:
        params["name"] = "יוסי"

    if "למחר" in cmd:
        params["date"] = "מחר"
    if "חמישי" in cmd:
        params["date"] = "יום חמישי"
    if "רביעי" in cmd:
        params["date"] = "יום רביעי"

    if "בעשר" in cmd:
        params["time"] = "10:00"
    if "באחת" in cmd:
        params["time"] = "13:00"

    if "לידים חמים" in cmd:
        params["widget"] = "לידים חמים"

    return params


_PARAM_EXTRACTORS = {
    Intent.CREATE_AGENT: _extract_agent_params,
    Intent.BUILD_AGENT_CODE: _extract_agent_params,
    Intent.ASSISTANT_MESSAGE: _extract_assistant_params,
    Intent.ASSISTANT_MEETING: _extract_assistant_params,
    Intent.ASSISTANT_DASHBOARD: _extract_assistant_params,
    Intent.ASSISTANT_PLAN: _extract_assistant_params,
}


class IntentParser:

    def parse(self, command: str) -> IntentResult:
        if not command or not command.strip():
            return IntentResult(intent=Intent.UNKNOWN, raw=command, confidence=0.0)

        raw = command.strip()
        lowered = raw.lower()

        for intent_name, confidence, patterns in _KEYWORD_RULES:
            for pattern in patterns:
                if re.search(pattern, lowered):
                    extractor = _PARAM_EXTRACTORS.get(intent_name)
                    params = extractor(raw) if extractor else {}
                    return IntentResult(
                        intent=intent_name,
                        params=params,
                        confidence=confidence,
                        raw=raw,
                        parse_path="keyword",
                    )

        return IntentResult(
            intent=Intent.UNKNOWN,
            params={"raw_command": raw},
            confidence=0.0,
            raw=raw,
            parse_path="keyword",
        )


intent_parser = IntentParser()
