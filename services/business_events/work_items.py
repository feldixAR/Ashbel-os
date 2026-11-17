"""Persistent follow-up work and artifacts on the existing TaskModel.

This is an internal execution ledger referencing the authoritative CRM, not a new
customer database. Analysis produces open work; an owner report is recorded as a
report, never as independently verified external delivery, payment or completion.
"""
import copy
import datetime as dt
import hashlib
import json
import uuid
from sqlalchemy import select, update
from services.storage.db import get_session
from services.storage.models.task import TaskModel
from services.storage.models.base import new_uuid

TYPE = "business_work_item"


def _tenant():
    from services.business_events.runtime import tenant
    return tenant()


def _stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _serialize(row):
    data, out = row.input_data or {}, row.output_data or {}
    return {"id": row.id, "department": row.action, "code": data.get("code"),
            "subject": data.get("subject"), "business_id": data.get("business_id"),
            "status": row.status, "version": out.get("version", 1),
            "source_ref": data.get("source_ref"), "event_id": data.get("event_id"),
            "artifact": out.get("artifact"), "missing": out.get("missing", []),
            "requires_owner_approval": out.get("requires_owner_approval", False),
            "completion_evidence": out.get("completion_evidence"),
            "independently_verified": False,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "source_writeback": "not_attempted"}


def list_work_items(limit=50):
    with get_session() as session:
        rows = session.query(TaskModel).filter(
            TaskModel.type == TYPE,
            TaskModel.input_data["business_id"].as_string() == _tenant(),
        ).order_by(TaskModel.priority, TaskModel.updated_at.desc()).limit(min(max(int(limit), 1), 100)).all()
        return [_serialize(row) for row in rows]


def persist_work_items(session, event, output):
    """Called only inside the winning event-finalization transaction."""
    identity = event.get("facts", {})
    entity = str(identity.get("crm_record_id") or identity.get("project_id") or identity.get("supplier_id") or event["source_ref"])
    subject = str(identity.get("name") or identity.get("project_name") or entity)[:300]
    ids = []
    for role, department in output["departments"].items():
        artifact = department.get("artifact")
        if not artifact:
            continue
        code = next((a["code"] for a in department.get("actions", []) if a.get("code")), "review_" + role)
        key = json.dumps([event["business_id"], entity, role, code], ensure_ascii=False)
        item_id = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
        digest = hashlib.sha256(json.dumps(artifact, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        missing = list(dict.fromkeys(department.get("missing", []) + artifact.get("missing", [])))
        needs_approval = role == "sales"
        status = "blocked" if missing else "approval_pending" if needs_approval else "created"
        incoming = {"business_id": event["business_id"], "entity_ref": entity, "source_ref": event["source_ref"],
                    "event_id": event["id"], "code": code, "subject": subject,
                    "observed_at": event["occurred_at"]}
        result = {"version": 1, "artifact": artifact, "artifact_sha256": digest,
                  "missing": missing, "requires_owner_approval": needs_approval,
                  "business_execution": False, "completion_evidence": None}
        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        session.execute(insert(TaskModel).values(
            id=item_id, type=TYPE, action=role, priority={"procurement": 1, "engineering": 2, "sales": 3}.get(role, 5),
            status=status, input_data=incoming, output_data=result, risk_level=1,
            model_used="native_deterministic",
        ).on_conflict_do_nothing(index_elements=["id"]))
        row = session.execute(select(TaskModel).where(TaskModel.id == item_id).with_for_update()).scalar_one()
        existing = row.output_data or {}
        if ((row.input_data or {}).get("observed_at", "") <= event["occurred_at"]
                and existing.get("artifact_sha256") != digest):
            result["version"] = existing.get("version", 1) + 1
            result["prior_owner_report"] = existing.get("completion_evidence")
            row.input_data, row.output_data = incoming, result
            row.status = status  # new facts require new review; never auto-close
        elif (row.input_data or {}).get("observed_at", "") < event["occurred_at"]:
            # Identical artifacts still advance the source watermark. Otherwise
            # t1=A, t3=A, t2=B could replace a newer observation with stale B.
            # Preserve review/version because no business artifact changed.
            row.input_data = {**(row.input_data or {}), **incoming}
        ids.append(item_id)
    return ids


def review_work_item(item_id, action, expected_version, note, evidence_ref=""):
    if action not in {"report_complete", "reopen", "cancel"}:
        raise ValueError("invalid_review_action")
    if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 1:
        raise ValueError("expected_version_required")
    if not isinstance(note, str) or not note.strip() or len(note) > 2000:
        raise ValueError("review_note_required")
    if not isinstance(evidence_ref, str) or len(evidence_ref) > 2000:
        raise ValueError("invalid_evidence_ref")
    if action == "report_complete" and not evidence_ref.strip():
        raise ValueError("completion_evidence_ref_required")
    with get_session() as session:
        row = session.query(TaskModel).filter(
            TaskModel.id == item_id, TaskModel.type == TYPE,
            TaskModel.input_data["business_id"].as_string() == _tenant()).one_or_none()
        if row is None:
            raise LookupError("work_item_not_found")
        out = copy.deepcopy(row.output_data or {})
        if out.get("version", 1) != expected_version:
            raise ValueError("work_item_version_conflict")
        next_status = {"report_complete": "reported_complete", "reopen": "created", "cancel": "cancelled"}[action]
        record = {"action": action, "note": note.strip(), "evidence_ref": evidence_ref.strip(),
                  "recorded_at": _stamp(), "reported_by": "authenticated_owner",
                  "independently_verified": False, "external_action_executed": False}
        out.update(version=expected_version + 1, last_review=record)
        if action == "report_complete":
            out["completion_evidence"] = {**record, "kind": "owner_reported"}
        count = session.execute(update(TaskModel).where(
            TaskModel.id == item_id, TaskModel.type == TYPE,
            TaskModel.input_data["business_id"].as_string() == _tenant(),
            TaskModel.output_data["version"].as_integer() == expected_version,
        ).values(status=next_status, output_data=out), execution_options={"synchronize_session": False}).rowcount
        if count != 1:
            raise ValueError("work_item_version_conflict")
        # Immutable review trace in the same existing task ledger transaction.
        session.add(TaskModel(id=new_uuid(), type="business_work_item_review", action=action,
                              status="done", parent_task_id=item_id,
                              input_data={"business_id": _tenant(), "expected_version": expected_version},
                              output_data=record, model_used="authenticated_owner_report"))
        session.expire(row)
        return _serialize(row)
