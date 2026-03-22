"""
AgentRegistry — in-memory registry of active agent instances.
"""

import logging
import threading

log = logging.getLogger(__name__)


class AgentRegistry:

    def __init__(self):
        self._agents: list = []
        self._fallback = None
        self._lock = threading.Lock()

    def register(self, agent) -> None:
        with self._lock:
            self._agents = [a for a in self._agents if a.agent_id != agent.agent_id]
            self._agents.append(agent)
        log.info(f"[Registry] registered {agent!r}")

    def unregister(self, agent_id: str) -> None:
        with self._lock:
            self._agents = [a for a in self._agents if a.agent_id != agent_id]
        log.info(f"[Registry] unregistered agent_id={agent_id}")

    def clear(self) -> None:
        with self._lock:
            self._agents.clear()
        log.info("[Registry] cleared")

    def find(self, task_type: str, action: str):
        with self._lock:
            snapshot = list(self._agents)

        for agent in snapshot:
            try:
                if agent.can_handle(task_type, action):
                    log.debug(f"[Registry] ({task_type},{action}) → {agent.name!r}")
                    return agent
            except Exception as e:
                log.error(f"[Registry] can_handle raised on {agent!r}: {e}")

        if self._fallback is not None:
            log.debug(f"[Registry] fallback for ({task_type},{action})")
            return self._fallback

        log.warning(f"[Registry] no agent for ({task_type},{action})")
        return None

    def list_agents(self) -> list:
        with self._lock:
            return list(self._agents)

    def count(self) -> int:
        with self._lock:
            return len(self._agents)

    def bootstrap(self) -> None:
        from agents.departments.sales.lead_qualifier import LeadQualifierAgent
        from agents.departments.sales.messaging_agent import MessagingAgent
        from agents.departments.executive.ceo_agent import CEOAgent
        from agents.departments.executive.build_manager_agent import BuildManagerAgent
        from agents.departments.executive.code_builder_agent import CodeBuilderAgent
        from agents.departments.generic.task_agent import GenericTaskAgent

        for agent in [
            LeadQualifierAgent(),
            MessagingAgent(),
            CEOAgent(),
            BuildManagerAgent(),
            CodeBuilderAgent(),
        ]:
            self.register(agent)

        self._fallback = GenericTaskAgent()
        log.info("[Registry] fallback = GenericTaskAgent")

        self._load_from_db()
        log.info(f"[Registry] bootstrap complete — {self.count()} agents")

    def _load_from_db(self) -> None:
        try:
            from services.storage.repositories.agent_repo import AgentRepository

            db_agents = AgentRepository().get_active()
            log.info(f"[Registry] {len(db_agents)} active agents in DB")
        except Exception as e:
            log.error(f"[Registry] _load_from_db failed: {e}", exc_info=True)


agent_registry = AgentRegistry()
