"""
agent_factory.py — Dynamic Agent Factory (Batch 3)

Creates, updates, retires, and registers agents at runtime.
CEO can call this to expand the system on demand.

Capabilities:
    create_agent(spec)     → AgentModel + registers in memory
    update_agent(id, spec) → adds new version + activates
    retire_agent(id)       → marks inactive + unregisters
    list_capabilities()    → all known capability types
    generate_system_prompt(spec) → builds prompt from spec
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

log = logging.getLogger(__name__)


# ── Agent Spec ────────────────────────────────────────────────────────────────

@dataclass
class AgentSpec:
    name:             str
    role:             str
    department:       str
    capabilities:     List[str]
    task_types:       List[str]        # which (task_type, action) pairs to handle
    actions:          List[str]
    model_preference: str  = "claude_haiku"
    risk_tolerance:   int  = 2
    system_prompt:    str  = ""
    context:          str  = ""        # extra business context


# ── Known capability library ──────────────────────────────────────────────────

CAPABILITY_LIBRARY = {
    "lead_followup":      "מעקב אחרי לידים, יצירת קשר ראשוני, תזכורות",
    "lead_qualification": "דירוג וסיווג לידים לפי פרמטרים עסקיים",
    "whatsapp_messaging": "שליחת הודעות WhatsApp, ניהול שיחות",
    "calendar_booking":   "קביעת פגישות, ניהול יומן",
    "opportunity_detect": "זיהוי הזדמנויות עסקיות מנתוני CRM",
    "content_creation":   "יצירת תוכן שיווקי, הצעות מחיר",
    "reporting":          "דוחות, ניתוח נתונים, KPIs",
    "market_research":    "מחקר שוק, ניתוח מתחרים",
    "customer_support":   "מענה ללקוחות, טיפול בפניות",
    "architect_outreach": "פנייה לאדריכלים ומעצבים",
    "contractor_outreach":"פנייה לקבלנים",
    "price_quoting":      "הכנת הצעות מחיר לעבודות אלומיניום",
    "scheduling":         "תיאום עבודות ולוחות זמנים",
    "complaint_handling": "טיפול בתלונות לקוחות",
}

DEPARTMENT_DEFAULTS = {
    "sales":      {"model": "claude_haiku", "risk": 2},
    "executive":  {"model": "claude_sonnet", "risk": 3},
    "operations": {"model": "claude_haiku", "risk": 2},
    "marketing":  {"model": "claude_haiku", "risk": 2},
    "support":    {"model": "claude_haiku", "risk": 1},
}


# ── Dynamic Agent class ───────────────────────────────────────────────────────

class DynamicAgent:
    """
    Runtime-generated agent loaded from DB spec.
    Wraps an AgentModel and executes tasks via its system prompt + model router.
    """

    def __init__(self, model: "AgentModel", system_prompt: str):
        self._model        = model
        self._prompt       = system_prompt
        self.agent_id      = f"dynamic_{model.id}"
        self.name          = model.name
        self.department    = model.department
        self.version       = model.active_version
        self._task_types   = set(model.capabilities or [])

    def can_handle(self, task_type: str, action: str) -> bool:
        key = f"{task_type}:{action}"
        return key in self._task_types

    def execute(self, task) -> "ExecutionResult":
        from services.execution.executor import ExecutionResult
        try:
            return self._run(task)
        except Exception as e:
            log.error(f"[DynamicAgent:{self.name}] error: {e}", exc_info=True)
            return ExecutionResult(success=False, message=str(e), output={"error": str(e)})

    def _run(self, task) -> "ExecutionResult":
        from services.execution.executor import ExecutionResult
        from services.storage.repositories.agent_repo import AgentRepository

        params  = (task.input_data or {}).get("params", {})
        command = (task.input_data or {}).get("command", "")

        # Try AI execution via model_router if available
        try:
            from routing.model_router import model_router
            user_msg = f"פקודה: {command}\nפרמטרים: {params}"
            response = model_router.call(
                task_type=task.type,
                system_prompt=self._prompt,
                user_prompt=user_msg,
                max_tokens=500,
            )
            AgentRepository().increment_tasks(self._model.id)
            return ExecutionResult(
                success=True,
                message=response,
                output={"agent": self.name, "response": response, "ai_powered": True},
            )
        except Exception as e:
            log.warning(f"[DynamicAgent:{self.name}] model_router unavailable: {e}")

        # Fallback: structured response
        AgentRepository().increment_tasks(self._model.id)
        return ExecutionResult(
            success=True,
            message=f"סוכן {self.name} ביצע את הפעולה",
            output={
                "agent":      self.name,
                "department": self.department,
                "action":     task.action,
                "params":     params,
                "note":       "AI execution יופעל כשמפתח API מחובר",
            },
        )

    def __repr__(self):
        return f"<DynamicAgent name={self.name!r} dept={self.department!r}>"


# ── Factory ───────────────────────────────────────────────────────────────────

class AgentFactory:

    def create_agent(self, spec: AgentSpec) -> Dict[str, Any]:
        """
        Creates agent in DB + registers in memory registry.
        Returns dict with agent info.
        """
        from services.storage.repositories.agent_repo import AgentRepository
        from agents.base.agent_registry import agent_registry

        # Build system prompt if not provided
        if not spec.system_prompt:
            spec.system_prompt = self._generate_prompt(spec)

        # Build capabilities list as "task_type:action" pairs
        capabilities = [f"{t}:{a}" for t, a in zip(spec.task_types, spec.actions)]
        # Also store raw capability names
        capabilities += spec.capabilities

        try:
            agent_model = AgentRepository().create(
                name=spec.name,
                role=spec.role,
                department=spec.department,
                capabilities=capabilities,
                model_preference=spec.model_preference,
                risk_tolerance=spec.risk_tolerance,
                system_prompt=spec.system_prompt,
            )
        except Exception as e:
            log.error(f"[Factory] DB create failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

        # Register in memory
        dynamic = DynamicAgent(agent_model, spec.system_prompt)
        agent_registry.register(dynamic)

        log.info(f"[Factory] created agent {spec.name!r} id={agent_model.id}")
        return {
            "success":    True,
            "agent_id":   agent_model.id,
            "name":       agent_model.name,
            "department": agent_model.department,
            "version":    1,
            "capabilities": capabilities,
        }

    def update_agent(self, agent_id: str, new_prompt: str = "",
                     new_model: str = "") -> Dict[str, Any]:
        """Adds a new version to an existing agent and activates it."""
        from services.storage.repositories.agent_repo import AgentRepository
        from agents.base.agent_registry import agent_registry

        repo = AgentRepository()

        with __import__("services.storage.db", fromlist=["get_session"]).get_session() as s:
            from services.storage.models.agent import AgentModel
            agent = s.get(AgentModel, agent_id)
            if not agent:
                return {"success": False, "error": f"agent {agent_id} not found"}
            model_pref = new_model or agent.model_preference
            name       = agent.name

        version = repo.add_version(agent_id, new_prompt, model_pref)
        repo.activate_version(agent_id, version.version)

        # Re-register updated dynamic agent
        from services.storage.models.agent import AgentModel as AM
        with __import__("services.storage.db", fromlist=["get_session"]).get_session() as s:
            agent_model = s.get(AM, agent_id)
            if agent_model:
                dynamic = DynamicAgent(agent_model, new_prompt)
                agent_registry.register(dynamic)

        return {
            "success":     True,
            "agent_id":    agent_id,
            "new_version": version.version,
            "name":        name,
        }

    def retire_agent(self, agent_id: str) -> Dict[str, Any]:
        """Marks agent as inactive and removes from registry."""
        from services.storage.repositories.agent_repo import AgentRepository
        from agents.base.agent_registry import agent_registry

        AgentRepository().retire(agent_id)
        agent_registry.unregister(f"dynamic_{agent_id}")

        log.info(f"[Factory] retired agent {agent_id}")
        return {"success": True, "agent_id": agent_id, "status": "retired"}

    def load_agents_from_db(self) -> int:
        """Loads all active DB agents into memory registry. Called on bootstrap."""
        from services.storage.repositories.agent_repo import AgentRepository
        from agents.base.agent_registry import agent_registry

        agents  = AgentRepository().get_active()
        loaded  = 0
        for agent_model in agents:
            try:
                version = AgentRepository().get_active_version(agent_model.id)
                prompt  = version.system_prompt if version else ""
                dynamic = DynamicAgent(agent_model, prompt)
                agent_registry.register(dynamic)
                loaded += 1
            except Exception as e:
                log.error(f"[Factory] load failed for {agent_model.id}: {e}")

        log.info(f"[Factory] loaded {loaded} agents from DB")
        return loaded

    def _generate_prompt(self, spec: AgentSpec) -> str:
        """Auto-generates a system prompt from spec."""
        from config.settings import COMPANY_NAME, COMPANY_PROFILE, TARGET_CLIENTS
        caps = ", ".join(spec.capabilities) if spec.capabilities else spec.role
        return (
            f"אתה {spec.name}, סוכן AI של {COMPANY_NAME}.\n"
            f"תפקידך: {spec.role}\n"
            f"מחלקה: {spec.department}\n"
            f"יכולות: {caps}\n\n"
            f"הקשר עסקי: {COMPANY_PROFILE}\n"
            f"לקוחות יעד: {TARGET_CLIENTS}\n\n"
            f"{spec.context}\n\n"
            f"עקרונות עבודה:\n"
            f"- ענה תמיד בעברית\n"
            f"- היה תמציתי ומקצועי\n"
            f"- המלץ על פעולה ברורה\n"
            f"- אל תמציא פרטים שלא ניתנו לך\n"
        ).strip()

    def parse_create_request(self, command: str) -> Optional[AgentSpec]:
        """
        Parses natural language agent creation request into AgentSpec.
        e.g. "צור סוכן follow-up לאדריכלים"
        """
        import re
        tl = command.lower()

        # Detect department
        dept = "sales"
        if any(w in tl for w in ["אדריכל", "מעצב", "architect"]):
            dept = "sales"
        elif any(w in tl for w in ["תמיכה", "support", "שירות"]):
            dept = "support"
        elif any(w in tl for w in ["שיווק", "marketing", "תוכן"]):
            dept = "marketing"
        elif any(w in tl for w in ["ניהול", "executive", "מנהל"]):
            dept = "executive"

        # Detect capabilities
        caps = []
        if any(w in tl for w in ["follow", "מעקב", "חזרה"]):
            caps.append("lead_followup")
        if any(w in tl for w in ["אדריכל", "architect"]):
            caps.append("architect_outreach")
        if any(w in tl for w in ["קבלן", "contractor"]):
            caps.append("contractor_outreach")
        if any(w in tl for w in ["הצעת מחיר", "מחיר", "quote"]):
            caps.append("price_quoting")
        if any(w in tl for w in ["הודעה", "whatsapp", "וואטסאפ"]):
            caps.append("whatsapp_messaging")
        if any(w in tl for w in ["דוח", "report", "נתונים"]):
            caps.append("reporting")
        if not caps:
            caps = ["lead_followup"]

        # Extract name
        m = re.search(r"(?:סוכן|agent)\s+([^\s]+(?:\s+[^\s]+)?)", command)
        raw_name = m.group(1).strip() if m else "סוכן חדש"

        name = f"סוכן {raw_name}" if not raw_name.startswith("סוכן") else raw_name

        defs = DEPARTMENT_DEFAULTS.get(dept, {"model": "claude_haiku", "risk": 2})

        return AgentSpec(
            name=name,
            role=f"סוכן {', '.join(caps)}",
            department=dept,
            capabilities=caps,
            task_types=[dept] * len(caps),
            actions=caps,
            model_preference=defs["model"],
            risk_tolerance=defs["risk"],
            context=command,
        )


agent_factory = AgentFactory()
