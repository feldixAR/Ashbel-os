"""Repository for import run reports."""
from typing import List

from services.storage.db import get_session
from services.storage.models.import_run import ImportRunModel
from services.storage.models.base import new_uuid
from .base_repo import BaseRepository, utcnow_iso


class ImportRunRepository(BaseRepository[ImportRunModel]):
    model_class = ImportRunModel

    def create_preview(self, source_file: str, source_format: str, raw_count: int,
                       approved_count: int, skipped_count: int,
                       duplicate_count: int, report: dict,
                       operator: str = "operator") -> ImportRunModel:
        run = ImportRunModel(
            id=new_uuid(), source_file=source_file, source_format=source_format,
            status="preview", operator=operator, raw_count=raw_count,
            approved_count=approved_count, skipped_count=skipped_count,
            duplicate_count=duplicate_count, report=report,
            lead_ids=[], errors=[],
        )
        with get_session() as s:
            s.add(run)
        return run

    def mark_pending_approval(self, import_run_id: str, approval_id: str) -> None:
        with get_session() as s:
            run = s.get(ImportRunModel, import_run_id)
            if run:
                run.status = "pending_approval"
                run.approval_id = approval_id

    def mark_committed(self, import_run_id: str, approval_id: str, created_count: int,
                       skipped_count: int, error_count: int, lead_ids: list[str],
                       errors: list[str], report: dict) -> None:
        with get_session() as s:
            run = s.get(ImportRunModel, import_run_id)
            if run:
                run.status = "committed"
                run.approval_id = approval_id
                run.created_count = created_count
                run.skipped_count = skipped_count
                run.error_count = error_count
                run.lead_ids = lead_ids
                run.errors = errors
                run.report = report
                run.committed_at = utcnow_iso()

    def latest(self, limit: int = 10) -> List[ImportRunModel]:
        with get_session() as s:
            return (s.query(ImportRunModel)
                    .order_by(ImportRunModel.created_at.desc())
                    .limit(limit)
                    .all())
