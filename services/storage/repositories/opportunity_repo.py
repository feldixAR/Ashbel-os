"""OpportunityRepository — Batch 6."""
from typing import List
from services.storage.db import get_session
from services.storage.models.opportunity import OpportunityModel
from services.storage.models.base import new_uuid
from .base_repo import BaseRepository


class OpportunityRepository(BaseRepository[OpportunityModel]):
    model_class = OpportunityModel

    def create(self, goal_id: str, track_id: str, title: str,
               audience: str, channel: str, potential: str,
               effort: str, next_action: str) -> OpportunityModel:
        opp = OpportunityModel(
            id=new_uuid(),
            goal_id=goal_id, track_id=track_id, title=title,
            audience=audience, channel=channel,
            potential=potential, effort=effort, next_action=next_action,
        )
        with get_session() as s:
            s.add(opp)
        return opp

    def list_by_goal(self, goal_id: str) -> List[OpportunityModel]:
        with get_session() as s:
            return (s.query(OpportunityModel)
                    .filter_by(goal_id=goal_id)
                    .order_by(OpportunityModel.created_at)
                    .all())
