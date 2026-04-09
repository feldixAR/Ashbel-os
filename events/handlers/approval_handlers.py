"""
Approval event handlers.

Triggered by: APPROVAL_REQUESTED, APPROVAL_GRANTED, APPROVAL_DENIED

Responsibilities:
  - Maintain accurate pending approval count in memory (for dashboard badge)
  - Log all approval decisions with full audit trail
  - Trigger task continuation after approval is granted
  - Track denial patterns for risk policy tuning
"""

import logging
from memory.memory_store import MemoryStore

log = logging.getLogger(__name__)


def on_approval_requested(event_type: str, payload: dict, meta: dict) -> None:
    """
    An action was gated and is waiting for human approval.
    Updates the pending count in memory so the dashboard badge is accurate.
    """
    approval_id = payload.get("approval_id")
    action      = payload.get("action", "unknown")
    risk_level  = payload.get("risk_level", 3)
    task_id     = payload.get("task_id")

    log.info(
        f"[ApprovalHandler] requested: id={approval_id} "
        f"action={action} risk={risk_level} task={task_id}"
    )

    # Increment pending count
    pending = MemoryStore.read("global", "pending_approvals_count", 0)
    MemoryStore.write("global", "pending_approvals_count", max(0, pending) + 1)

    # Track which actions most frequently need approval (for policy tuning)
    key = f"approval_requests_{action}"
    count = MemoryStore.read("global", key, 0)
    MemoryStore.write("global", key, count + 1)


def on_approval_granted(event_type: str, payload: dict, meta: dict) -> None:
    """
    A pending action was approved by the owner.
    Decrements pending count and logs the grant for audit.
    """
    approval_id  = payload.get("approval_id")
    action       = payload.get("action", "unknown")
    resolved_by  = payload.get("resolved_by", "owner")
    task_id      = payload.get("task_id")

    log.info(
        f"[ApprovalHandler] granted: id={approval_id} "
        f"action={action} by={resolved_by} task={task_id}"
    )

    _decrement_pending()

    # Track approval grant rate per action
    key = f"approval_grants_{action}"
    count = MemoryStore.read("global", key, 0)
    MemoryStore.write("global", key, count + 1)

    # Append to approval audit log
    _append_audit_log("granted", approval_id, action, resolved_by)


def on_approval_denied(event_type: str, payload: dict, meta: dict) -> None:
    """
    A pending action was denied by the owner.
    Decrements pending count, logs the denial, and tracks denial patterns.
    """
    approval_id = payload.get("approval_id")
    action      = payload.get("action", "unknown")
    resolved_by = payload.get("resolved_by", "owner")
    reason      = payload.get("reason", "")
    task_id     = payload.get("task_id")

    log.warning(
        f"[ApprovalHandler] denied: id={approval_id} "
        f"action={action} by={resolved_by} reason={reason}"
    )

    _decrement_pending()

    # Track denial rate per action — high denial rate → review risk policy
    key = f"approval_denials_{action}"
    count = MemoryStore.read("global", key, 0)
    MemoryStore.write("global", key, count + 1)

    _append_audit_log("denied", approval_id, action, resolved_by, reason)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _decrement_pending() -> None:
    pending = MemoryStore.read("global", "pending_approvals_count", 0)
    MemoryStore.write("global", "pending_approvals_count", max(0, pending - 1))


def _append_audit_log(
    decision:    str,
    approval_id: str,
    action:      str,
    resolved_by: str,
    reason:      str = "",
) -> None:
    import datetime
    audit = MemoryStore.read("global", "approval_audit_log", [])
    audit.append({
        "decision":    decision,
        "approval_id": approval_id,
        "action":      action,
        "resolved_by": resolved_by,
        "reason":      reason,
        "ts":          datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    # Keep last 500 audit entries
    if len(audit) > 500:
        audit = audit[-500:]
    MemoryStore.write("global", "approval_audit_log", audit)
