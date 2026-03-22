from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any


class Intent(str, Enum):
    CREATE_AGENT = "create_agent"
    BUILD_AGENT_CODE = "build_agent_code"
    APPLY_BUILD = "apply_build"

    ASSISTANT_MESSAGE = "assistant_message"
    ASSISTANT_MEETING = "assistant_meeting"
    ASSISTANT_DASHBOARD = "assistant_dashboard"
    ASSISTANT_PLAN = "assistant_plan"

    DEVELOPMENT_ROADMAP = "development_roadmap"
    DEVELOPMENT_GAP = "development_gap"
    DEVELOPMENT_BATCH_STATUS = "development_batch_status"

    STATUS = "status"

    SALES = "sales"
    CREATE_LEAD = "create_lead"

    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class IntentResult:
    intent: Intent
    confidence: float
    params: Dict[str, Any]

    def is_confident(self, threshold: float = 0.5) -> bool:
        return self.confidence >= threshold


class IntentParser:
    def parse(self, text: str) -> IntentResult:
        text_lower = text.lower()

        # SALES / LEADS
        if any(word in text_lower for word in ["ליד", "lead"]):
            return IntentResult(
                intent=Intent.CREATE_LEAD,
                confidence=0.9,
                params={}
            )

        if any(word in text_lower for word in ["לקוח", "מכירה", "sale"]):
            return IntentResult(
                intent=Intent.SALES,
                confidence=0.8,
                params={}
            )

        # ASSISTANT MESSAGE
        if any(word in text_lower for word in ["שלח", "הודעה", "וואטסאפ", "whatsapp"]):
            return IntentResult(
                intent=Intent.ASSISTANT_MESSAGE,
                confidence=0.8,
                params={}
            )

        # MEETING
        if any(word in text_lower for word in ["פגישה", "meeting", "schedule"]):
            return IntentResult(
                intent=Intent.ASSISTANT_MEETING,
                confidence=0.8,
                params={}
            )

        # STATUS
        if "סטטוס" in text_lower or "status" in text_lower:
            return IntentResult(
                intent=Intent.STATUS,
                confidence=0.9,
                params={}
            )

        # HELP
        if "עזרה" in text_lower or "help" in text_lower:
            return IntentResult(
                intent=Intent.HELP,
                confidence=0.9,
                params={}
            )

        # DEFAULT
        return IntentResult(
            intent=Intent.UNKNOWN,
            confidence=0.0,
            params={}
        )


intent_parser = IntentParser()
