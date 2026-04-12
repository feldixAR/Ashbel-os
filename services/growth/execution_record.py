"""
services/growth/execution_record.py — Batch 7: Execution Record persistence.

Saves generated assets to the OutreachModel immediately after the committee
selects a winner. One record is written per asset type (whatsapp / email /
outreach_brief), giving a full audit trail.

Status lifecycle:
    ready     — asset generated, not yet sent
    pending   — queued for sending (future batch)
    sent      — delivered (future batch)
    replied   — contact responded (future batch)
"""

from __future__ import annotations

import datetime
import logging
import uuid
from dataclasses import dataclass
from typing import List

try:
    import pytz as _pytz
except ImportError:
    _pytz = None

from services.growth.asset_factory import AssetBundle, GeneratedAsset

log = logging.getLogger(__name__)
_IL_TZ = (_pytz.timezone("Asia/Jerusalem") if _pytz else __import__("datetime").timezone(__import__("datetime").timedelta(hours=3)))


# ── In-memory contract ─────────────────────────────────────────────────────────

@dataclass
class ExecutionRecord:
    record_id:      str
    goal_id:        str
    opportunity_id: str
    channel:        str
    audience:       str
    asset_type:     str
    asset_content:  str
    subject:        str
    status:         str          # ready | pending | sent | replied
    created_at_il:  str          # ISO-8601, Asia/Jerusalem

    def to_dict(self) -> dict:
        return {
            "record_id":      self.record_id,
            "goal_id":        self.goal_id,
            "opportunity_id": self.opportunity_id,
            "channel":        self.channel,
            "audience":       self.audience,
            "asset_type":     self.asset_type,
            "asset_content":  self.asset_content,
            "subject":        self.subject,
            "status":         self.status,
            "created_at_il":  self.created_at_il,
        }


# ── Persistence ────────────────────────────────────────────────────────────────

def persist(
    goal_id:     str,
    opportunity,         # ScoredOpportunity
    asset_bundle: AssetBundle,
) -> List[ExecutionRecord]:
    """
    Persist one OutreachModel row per generated asset.
    Returns a list of ExecutionRecord (in-memory) reflecting what was saved.
    Errors are logged, not raised.
    """
    now_il    = datetime.datetime.now(_IL_TZ).isoformat()
    records: List[ExecutionRecord] = []

    try:
        from services.storage.db import get_session
        from services.storage.models.outreach import OutreachModel

        from services.growth.policy import compute_next_action_at

        with get_session() as session:
            for asset in asset_bundle.assets:
                record_id     = str(uuid.uuid4())
                next_action   = compute_next_action_at(asset.channel)
                session.add(OutreachModel(
                    id=record_id,
                    goal_id=goal_id,
                    opp_id=opportunity.opp_id,
                    contact_name=f"[{asset.asset_type}] {asset_bundle.opportunity_title}",
                    contact_phone="",
                    channel=asset.channel,
                    message_body=asset.content,
                    status="ready",
                    lifecycle_status="sent",        # set to 'sent' after dispatch
                    next_action_at=next_action,
                    notes=asset.subject or "",
                ))
                records.append(ExecutionRecord(
                    record_id=record_id,
                    goal_id=goal_id,
                    opportunity_id=opportunity.opp_id,
                    channel=asset.channel,
                    audience=asset.audience,
                    asset_type=asset.asset_type,
                    asset_content=asset.content,
                    subject=asset.subject or "",
                    status="ready",
                    created_at_il=now_il,
                ))

        log.info(
            f"[ExecutionRecord] Persisted {len(records)} records "
            f"goal_id={goal_id} opp_id={opportunity.opp_id}"
        )

    except Exception as e:
        log.error(
            f"[ExecutionRecord] persist failed goal_id={goal_id}: {e}",
            exc_info=True,
        )

    return records


def get_primary_record(records: List[ExecutionRecord], channel: str) -> ExecutionRecord | None:
    """Return the record matching the opportunity's native channel, else first."""
    for r in records:
        if r.channel == channel:
            return r
    return records[0] if records else None
