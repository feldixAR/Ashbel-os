"""
AgentRegistry — in-memory registry of active agent instances.
Batch 3: loads dynamic agents from DB on bootstrap.
"""

import logging
import threading

log = logging.getLogger(__name__)


class AgentRegistry:

    def __init__(self):
        self._agents   = []
        self._fallback = None
        self._lock     = threading.Lock()

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
                    return agent
            except Exception as e:
                log.error(f"[Registry] can_handle raised on {agent!r}: {e}")
        if self._fallback is not None:
            return self._fallback
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
        from agents.departments.executive.executive_assistant_agent import ExecutiveAssistantAgent
        from agents.departments.executive.github_writer_agent import GitHubWriterAgent
        from agents.departments.generic.task_agent import GenericTaskAgent

        for agent in [
            LeadQualifierAgent(),
            MessagingAgent(),
            CEOAgent(),
            BuildManagerAgent(),
            CodeBuilderAgent(),
            ExecutiveAssistantAgent(),
            GitHubWriterAgent(),
        ]:
            self.register(agent)

        self._fallback = GenericTaskAgent()

        # Batch 3: load dynamic agents from DB
        self._load_dynamic_agents()

    def _load_dynamic_agents(self) -> None:
        """Load all active DB-persisted dynamic agents into memory."""
        try:
            from agents.factory.agent_factory import agent_factory
            count = agent_factory.load_agents_from_db()
            log.info(f"[Registry] loaded {count} dynamic agents from DB")
        except Exception as e:
            log.error(f"[Registry] _load_dynamic_agents failed: {e}", exc_info=True)


agent_registry = AgentRegistry()
