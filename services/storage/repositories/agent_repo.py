"""Agent repository."""
import datetime
from typing import List, Optional
from sqlalchemy import select
from services.storage.db import get_session
from services.storage.models.agent import AgentModel, AgentVersionModel
from .base_repo import BaseRepository, utcnow_iso


class AgentRepository(BaseRepository[AgentModel]):
    model_class = AgentModel

    def get_active(self, department: Optional[str] = None) -> List[AgentModel]:
        with get_session() as s:
            q = s.query(AgentModel).filter(AgentModel.active == True)
            if department:
                q = q.filter(AgentModel.department == department)
            return q.order_by(AgentModel.created_at).all()

    def create(self, name: str, role: str, department: str,
                capabilities: list, model_preference: str,
                risk_tolerance: int, system_prompt: str) -> AgentModel:
        from services.storage.models.base import new_uuid
        agent_id = new_uuid()
        agent = AgentModel(
            id=agent_id, name=name, role=role, department=department,
            capabilities=capabilities, model_preference=model_preference,
            risk_tolerance=risk_tolerance, active=True,
            active_version=1,
        )
        version = AgentVersionModel(
            agent_id=agent_id, version=1,
            system_prompt=system_prompt,
            model_preference=model_preference,
            is_active=True,
            active_from=utcnow_iso(),
        )
        with get_session() as s:
            s.add(agent)
            s.add(version)
        return agent

    def get_active_version(self, agent_id: str) -> Optional[AgentVersionModel]:
        with get_session() as s:
            return (s.query(AgentVersionModel)
                    .filter_by(agent_id=agent_id, is_active=True)
                    .first())

    def add_version(self, agent_id: str, system_prompt: str,
                     model_preference: str) -> AgentVersionModel:
        with get_session() as s:
            current = (s.query(AgentVersionModel)
                       .filter_by(agent_id=agent_id)
                       .order_by(AgentVersionModel.version.desc())
                       .first())
            next_v = (current.version + 1) if current else 1
            v = AgentVersionModel(
                agent_id=agent_id, version=next_v,
                system_prompt=system_prompt,
                model_preference=model_preference,
                is_active=False,
            )
            s.add(v)
        return v

    def activate_version(self, agent_id: str, version: int) -> bool:
        with get_session() as s:
            # deactivate all
            s.query(AgentVersionModel).filter_by(agent_id=agent_id).update(
                {"is_active": False, "active_until": utcnow_iso()}
            )
            # activate target
            target = (s.query(AgentVersionModel)
                       .filter_by(agent_id=agent_id, version=version)
                       .first())
            if not target:
                return False
            target.is_active    = True
            target.active_from  = utcnow_iso()
            target.active_until = None
            # update agent
            agent = s.get(AgentModel, agent_id)
            if agent:
                agent.active_version = version
        return True

    def increment_tasks(self, agent_id: str) -> None:
        with get_session() as s:
            agent = s.get(AgentModel, agent_id)
            if agent:
                agent.tasks_done    = (agent.tasks_done or 0) + 1
                agent.last_active_at = utcnow_iso()

    def retire(self, agent_id: str) -> None:
        with get_session() as s:
            agent = s.get(AgentModel, agent_id)
            if agent:
                agent.active = False
