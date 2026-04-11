"""
All event type constants.
Every event published in the system must use a constant from this file.
"""

# ── Lead events ───────────────────────────────────────────────────────────────
LEAD_CREATED             = "lead.created"
LEAD_SCORED              = "lead.scored"
LEAD_STATUS_CHANGED      = "lead.status_changed"
LEAD_RESPONDED           = "lead.responded"
LEAD_CONVERTED           = "lead.converted"
LEAD_DEAD                = "lead.dead"
# Lead Acquisition (Phase 12)
LEAD_DISCOVERED          = "lead.discovered"          # web signal found a candidate
INBOUND_LEAD_RECEIVED    = "lead.inbound_received"    # inbound via Telegram/form
LEAD_OUTREACH_SENT       = "lead.outreach_sent"       # after approved outreach execution
LEAD_FOLLOWUP_PROPOSED   = "lead.followup_proposed"   # follow-up surfaced
WEBSITE_ANALYSIS_REQUESTED = "website.analysis_requested"  # website growth analysis

# ── Task events ───────────────────────────────────────────────────────────────
TASK_CREATED          = "task.created"
TASK_STARTED          = "task.started"
TASK_COMPLETED        = "task.completed"
TASK_FAILED           = "task.failed"
TASK_RETRYING         = "task.retrying"
TASK_DEAD_LETTERED    = "task.dead_lettered"
TASK_APPROVAL_NEEDED  = "task.approval_needed"
TASK_APPROVED         = "task.approved"
TASK_REJECTED         = "task.rejected"

# ── Agent events ──────────────────────────────────────────────────────────────
AGENT_CREATED                = "agent.created"
AGENT_UPDATED                = "agent.updated"
AGENT_RETIRED                = "agent.retired"
AGENT_FAILED                 = "agent.failed"
AGENT_VERSION_PROMOTED       = "agent.version_promoted"
AGENT_VERSION_ROLLED_BACK    = "agent.version_rolled_back"
AGENT_VERSION_DISCARDED      = "agent.version_discarded"

# ── Message events ────────────────────────────────────────────────────────────
MESSAGE_GENERATED       = "message.generated"
MESSAGE_SENT            = "message.sent"
MESSAGE_DELIVERY_FAILED = "message.delivery_failed"

# ── Model events ──────────────────────────────────────────────────────────────
MODEL_CALLED              = "model.called"
MODEL_FAILED              = "model.failed"
MODEL_FALLBACK_TRIGGERED  = "model.fallback_triggered"

# ── Learning events ───────────────────────────────────────────────────────────
PATTERN_DETECTED      = "learning.pattern_detected"
PROMPT_OPTIMIZED      = "learning.prompt_optimized"
ROUTING_MAP_UPDATED   = "learning.routing_map_updated"

# ── Approval events ───────────────────────────────────────────────────────────
APPROVAL_REQUESTED    = "approval.requested"
APPROVAL_GRANTED      = "approval.granted"
APPROVAL_DENIED       = "approval.denied"

# ── System events ─────────────────────────────────────────────────────────────
SYSTEM_STARTED        = "system.started"
SYSTEM_HEALTH_CHECK   = "system.health_check"
DLQ_ITEM_ADDED        = "system.dlq_item_added"
SCHEDULER_JOB_RAN     = "system.scheduler_job_ran"
