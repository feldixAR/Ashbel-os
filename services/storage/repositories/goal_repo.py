"""GoalRepository — Batch 6."""
from typing import List, Optional
from services.storage.db import get_session
from services.storage.models.goal import GoalModel
from services.storage.models.base import new_uuid
from .base_repo import BaseRepository


class GoalRepository(BaseRepository[GoalModel]):
    model_class = GoalModel

    def create(self, raw_goal: str, domain: str,
               primary_metric: str, tracks: list) -> GoalModel:
        goal = GoalModel(
            id=new_uuid(),
            raw_goal=raw_goal,
            domain=domain,
            primary_metric=primary_metric,
            tracks=tracks,
        )
        with get_session() as s:
            s.add(goal)
        return goal

    def list_active(self) -> List[GoalModel]:
        with get_session() as s:
            return (s.query(GoalModel)
                    .filter_by(status="active")
                    .order_by(GoalModel.created_at.desc())
                    .all())

    def update_status(self, goal_id: str, status: str) -> bool:
        with get_session() as s:
            goal = s.get(GoalModel, goal_id)
            if not goal:
                return False
            goal.status = status
        return True
