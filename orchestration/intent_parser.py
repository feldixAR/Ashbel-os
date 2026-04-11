"""
intent_parser.py — Hebrew/English intent detection with entity extraction.

Batch 1: Conversational Interface
- Free text intent classification (Enum-based)
- Entity extraction via EntityExtractor
- Confidence scoring
- Context detection: command vs question vs update
- Params populated from entities automatically
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any

from orchestration.entity_extractor import entity_extractor


class Intent(str, Enum):
    # Agent management
    CREATE_AGENT              = "create_agent"
    BUILD_AGENT_CODE          = "build_agent_code"
    APPLY_BUILD               = "apply_build"

    # Assistant actions
    ASSISTANT_MESSAGE         = "assistant_message"
    ASSISTANT_MEETING         = "assistant_meeting"
    ASSISTANT_DASHBOARD       = "assistant_dashboard"
    ASSISTANT_PLAN            = "assistant_plan"
    ASSISTANT_REMINDER        = "assistant_reminder"

    # Development
    DEVELOPMENT_ROADMAP       = "development_roadmap"
    DEVELOPMENT_GAP           = "development_gap"
    DEVELOPMENT_BATCH_STATUS  = "development_batch_status"

    # CRM / Sales
    STATUS                    = "status"
    SALES                     = "sales"
    CREATE_LEAD               = "create_lead"
    UPDATE_LEAD               = "update_lead"
    LIST_LEADS                = "list_leads"
    HOT_LEADS                 = "hot_leads"

    # Revenue intelligence
    REVENUE_INSIGHTS          = "revenue_insights"
    BOTTLENECK                = "bottleneck"
    NEXT_ACTION               = "next_action"

    # Reporting
    DAILY_REPORT              = "daily_report"

    # Meta
    HELP                      = "help"
    UNKNOWN                   = "unknown"

    # Agent Factory (Batch 3)
    UPDATE_AGENT              = "update_agent"
    RETIRE_AGENT              = "retire_agent"
    LIST_AGENTS               = "list_agents"

    # Revenue (Batch 4)
    REVENUE_REPORT            = "revenue_report"

    # Goal & Growth Engine (Batch 6)
    SET_GOAL                  = "set_goal"
    LIST_GOALS                = "list_goals"
    GROWTH_PLAN               = "growth_plan"

    # Research & Asset Engine (Batch 7)
    RESEARCH_AUDIENCE         = "research_audience"
    BUILD_PORTFOLIO           = "build_portfolio"
    BUILD_OUTREACH_COPY       = "build_outreach_copy"

    # Outreach & Execution Engine (Batch 8)
    SEND_OUTREACH             = "send_outreach"
    DAILY_PLAN                = "daily_plan"
    FOLLOWUP_QUEUE            = "followup_queue"

    # Revenue Learning (Batch 9)
    LEARNING_CYCLE            = "learning_cycle"
    PERFORMANCE_REPORT        = "performance_report"

    # Chief of Staff (Phase 3)
    CHIEF_OF_STAFF            = "chief_of_staff"

    # Lead Acquisition OS (Phase 12)
    DISCOVER_LEADS            = "discover_leads"
    PROCESS_INBOUND           = "process_inbound"
    WEBSITE_ANALYSIS          = "website_analysis"
    LEAD_OPS_QUEUE            = "lead_ops_queue"

    # Phase 16: Channel-native + self-evolution
    DOCUMENT_UPLOAD           = "document_upload"
    SYSTEM_CHANGE             = "system_change"


@dataclass
class IntentResult:
    intent:     Intent
    confidence: float
    params:     Dict[str, Any] = field(default_factory=dict)
    context:    str            = "command"   # command | question | update

    def is_confident(self, threshold: float = 0.5) -> bool:
        return self.confidence >= threshold


class IntentParser:
    """
    Parses free Hebrew/English text into structured IntentResult.
    Pipeline: text -> intent detection -> entity extraction -> params merge.
    """

    def parse(self, text: str) -> IntentResult:
        t = text.strip()
        tl = t.lower()

        context = self._detect_context(t)
        intent, confidence = self._detect_intent(t, tl)
        entities = entity_extractor.extract(t)
        params = dict(entities)

        return IntentResult(
            intent=intent,
            confidence=confidence,
            params=params,
            context=context,
        )

    def _detect_context(self, text: str) -> str:
        if any(q in text for q in ["?", "מה ", "איך ", "כמה ", "מתי ", "למה ", "האם "]):
            return "question"
        if any(u in text for u in ["עדכן", "שנה", "תעדכן", "עדכני", "שנה סטטוס"]):
            return "update"
        return "command"

    def _detect_intent(self, text: str, tl: str):
        # ── Batch 6 — Goal & Growth (check before generic revenue/sales) ──────
        if any(w in tl for w in [
            "הגדל מכירות", "רוצה להגדיל", "יעד עסקי", "הגדר יעד",
            "תגדיר מטרה", "מטרה עסקית", "set goal", "הגדל הכנסות",
            "להגדיל מכירות", "להגדיל הכנסות", "תגדיל",
        ]):
            return Intent.SET_GOAL, 0.95

        if any(w in tl for w in [
            "תוכנית צמיחה", "איך לצמוח", "growth plan", "תכנית שיווק",
        ]):
            return Intent.GROWTH_PLAN, 0.9

        if any(w in tl for w in [
            "יעדים", "מה היעדים", "הצג יעדים", "list goals", "יעדים פעילים",
        ]):
            return Intent.LIST_GOALS, 0.9

        # Revenue intelligence
        if any(w in tl for w in ["מה הכי יקדם", "מה יביא כסף", "revenue", "הכנסות"]):
            return Intent.REVENUE_INSIGHTS, 0.9
        if any(w in text for w in ["למה לא סוגרים", "מה תקוע", "bottleneck", "חסם"]):
            return Intent.BOTTLENECK, 0.9
        if any(w in text for w in ["מה כדאי לעשות", "next action", "מה לפעול", "מה הצעד הבא"]):
            return Intent.NEXT_ACTION, 0.9

        # Phase 16: System self-evolution — checked first (sensitive, highest priority)
        if any(w in tl for w in [
            "הוסף ווידג'ט", "שנה ui", "צור מודול", "צור טאב", "הוסף טאב",
            "הוסף עמוד", "שנה עיצוב", "עדכן ui", "הוסף פאנל", "צור פאנל",
            "add widget", "add module", "add tab", "change ui", "modify ui",
            "create module", "שנה מראה", "עדכן מראה", "system change",
            "הוסף לוח", "ערוך לוח", "הוסף תכונה", "add feature",
        ]):
            return Intent.SYSTEM_CHANGE, 0.95

        # Phase 16: Document upload / processing
        if any(w in tl for w in [
            "העלה קובץ", "עבד קובץ", "ייבא קובץ", "csv", "excel",
            "אקסל", "קובץ לידים", "רשימת לידים", "import leads",
            "upload", "parse document", "process file", "קובץ",
        ]):
            return Intent.DOCUMENT_UPLOAD, 0.9

        # Lead Acquisition OS (Phase 12) — checked before generic lead/sales
        if any(w in tl for w in [
            "מצא לידים", "גלה לידים", "חפש לידים", "discover leads",
            "acquisition", "רכישת לידים", "לידים מהרשת", "לידים חדשים מ",
            "חיפוש לידים", "discover", "find leads",
        ]):
            return Intent.DISCOVER_LEADS, 0.95

        if any(w in tl for w in [
            "ליד נכנס", "inbound lead", "פנייה נכנסת", "טופס נכנס",
            "process inbound", "ליד חדש נכנס",
        ]):
            return Intent.PROCESS_INBOUND, 0.95

        if any(w in tl for w in [
            "ניתוח אתר", "website analysis", "בדוק אתר", "אודיט אתר",
            "site audit", "שפר אתר", "כמה טוב האתר",
        ]):
            return Intent.WEBSITE_ANALYSIS, 0.95

        if any(w in tl for w in [
            "תור לידים", "lead ops", "lead queue", "פעולות לידים",
            "מה יש בתור", "מה הלידים ממתינים", "כל הלידים הממתינים",
        ]):
            return Intent.LEAD_OPS_QUEUE, 0.9

        # Leads
        if any(w in tl for w in ["לידים חמים", "hot leads"]):
            return Intent.HOT_LEADS, 0.95
        if any(w in tl for w in ["הצג לידים", "רשימת לידים", "list leads", "כל הלידים", "תראה לידים"]):
            return Intent.LIST_LEADS, 0.9
        if any(w in text for w in ["עדכן ליד", "עדכני ליד", "שנה סטטוס ליד", "update lead"]):
            return Intent.UPDATE_LEAD, 0.9
        if any(w in tl for w in ["ליד", "lead", "לקוח חדש"]):
            return Intent.CREATE_LEAD, 0.9

        # Assistant: message
        if any(w in text for w in ["שלח הודעה", "תשלח הודעה", "שלחי הודעה", "תשלחי הודעה",
                                    "שלח וואטסאפ", "תשלח וואטסאפ", "whatsapp", "וואטסאפ"]):
            return Intent.ASSISTANT_MESSAGE, 0.9

        # Assistant: reminder
        if any(w in text for w in ["תזכיר", "תזכירי", "תזכור", "reminder", "תזכורת",
                                    "לחזור אל", "לחזור ל"]):
            return Intent.ASSISTANT_REMINDER, 0.9

        # Assistant: meeting
        if any(w in text for w in ["פגישה", "meeting", "schedule", "קבע פגישה",
                                    "תקבע", "תקבעי", "יומן", "calendar"]):
            return Intent.ASSISTANT_MEETING, 0.9

        # Dashboard
        if any(w in text for w in ["מסך הבית", "dashboard", "עדכן מסך", "הוסף למסך"]):
            return Intent.ASSISTANT_DASHBOARD, 0.8

        # Daily report
        if any(w in tl for w in ["דוח יומי", "daily report", "דוח", "סיכום יום"]):
            return Intent.DAILY_REPORT, 0.9

        # Research & Asset Engine (Batch 7) — before SALES to avoid "לקוח" collision
        if any(w in tl for w in ["מחקר קהל", "פרופיל לקוח", "מי הלקוחות", "research audience",
                                   "ניתוח קהל", "תאר לי את הלקוח"]):
            return Intent.RESEARCH_AUDIENCE, 0.9
        if any(w in tl for w in ["תיק עבודות", "portfolio", "דוגמאות עבודה", "בנה תיק"]):
            return Intent.BUILD_PORTFOLIO, 0.9
        if any(w in tl for w in ["כתוב פנייה", "נוסח פנייה", "הכן הודעה שיווקית",
                                   "outreach copy", "מסר שיווקי", "בנה פנייה"]):
            return Intent.BUILD_OUTREACH_COPY, 0.9

        # Outreach & Execution Engine (Batch 8) — before SALES
        if any(w in tl for w in ["שלח פניות", "התחל outreach", "פתח קמפיין",
                                   "send outreach", "שלח לכולם"]):
            return Intent.SEND_OUTREACH, 0.9
        if any(w in tl for w in ["תוכנית יומית", "daily plan", "מה לעשות היום",
                                   "סדר יום", "תכנן לי את היום"]):
            return Intent.DAILY_PLAN, 0.9
        if any(w in tl for w in ["תור follow-up", "מי לא ענה", "followup queue",
                                   "מעקב פתוח", "מי מחכה לתגובה"]):
            return Intent.FOLLOWUP_QUEUE, 0.9

        # Revenue Learning (Batch 9) — before SALES
        if any(w in tl for w in ["מחזור למידה", "learning cycle", "שפר את עצמך",
                                   "נתח תוצאות", "מה עבד"]):
            return Intent.LEARNING_CYCLE, 0.9
        if any(w in tl for w in ["דוח ביצועים", "performance report", "שיעור מענה",
                                   "מה היה הכי טוב", "ניתוח קמפיין"]):
            return Intent.PERFORMANCE_REPORT, 0.9

        # Chief of Staff (Phase 3)
        if any(w in tl for w in ["מה לעשות", "תכנן", "הצע", "מה הצעד הבא",
                                   "תעזור לי להחליט", "מה כדאי", "chief of staff",
                                   "תכנן אסטרטגיה", "תכנן פעולות"]):
            return Intent.CHIEF_OF_STAFF, 0.9

        # Sales
        if any(w in tl for w in ["לקוח", "מכירה", "sale", "עסקה"]):
            return Intent.SALES, 0.8

        # Status
        if any(w in tl for w in ["סטטוס", "status", "מצב המערכת"]):
            return Intent.STATUS, 0.9

        # Build system
        if any(w in tl for w in ["בנה קוד", "build agent", "build_agent"]):
            return Intent.BUILD_AGENT_CODE, 0.9
        if any(w in tl for w in ["יישם", "apply", "תיישמי"]):
            return Intent.APPLY_BUILD, 0.9
        if any(w in tl for w in ["צור סוכן", "create agent", "סוכן חדש"]):
            return Intent.CREATE_AGENT, 0.9

        # Development
        if any(w in tl for w in ["roadmap", "תכנית", "פיתוח"]):
            return Intent.DEVELOPMENT_ROADMAP, 0.8
        if any(w in tl for w in ["מה חסר", "gap", "פערים"]):
            return Intent.DEVELOPMENT_GAP, 0.8
        if any(w in tl for w in ["batch", "סטטוס פיתוח"]):
            return Intent.DEVELOPMENT_BATCH_STATUS, 0.8

        # Agent management (Batch 3)
        if any(w in text for w in ["עדכן סוכן", "שנה סוכן", "update agent"]):
            return Intent.UPDATE_AGENT, 0.9
        if any(w in text for w in ["פרוש סוכן", "הסר סוכן", "retire agent"]):
            return Intent.RETIRE_AGENT, 0.9
        if any(w in tl for w in ["הצג סוכנים", "רשימת סוכנים", "list agents", "כל הסוכנים"]):
            return Intent.LIST_AGENTS, 0.9

        # Revenue report (Batch 4)
        if any(w in tl for w in ["דוח הכנסות", "revenue report", "דוח מכירות"]):
            return Intent.REVENUE_REPORT, 0.9

        # Help
        if any(w in tl for w in ["עזרה", "help", "פקודות", "מה אתה יכול"]):
            return Intent.HELP, 0.9

        return Intent.UNKNOWN, 0.0


intent_parser = IntentParser()
