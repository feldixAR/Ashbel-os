"""
Risk policy — maps every system action to a risk level (1-5).
Actions at or above AUTO_APPROVE_BELOW_RISK require human approval.
"""
from enum import IntEnum


class RiskLevel(IntEnum):
    TRIVIAL  = 1   # read-only, generate draft
    LOW      = 2   # write to internal DB
    MEDIUM   = 3   # external communication, create agent
    HIGH     = 4   # delete, structural change, bulk action
    CRITICAL = 5   # financial, legal, irreversible


ACTION_RISK: dict[str, RiskLevel] = {
    # reads / trivial
    "read_data":              RiskLevel.TRIVIAL,
    "generate_content":       RiskLevel.TRIVIAL,
    "score_lead":             RiskLevel.TRIVIAL,
    "generate_report":        RiskLevel.TRIVIAL,
    "analyze_market":         RiskLevel.TRIVIAL,
    "benchmark_models":       RiskLevel.TRIVIAL,
    "hot_leads":              RiskLevel.TRIVIAL,
    "revenue_insights":       RiskLevel.TRIVIAL,
    "bottleneck_analysis":    RiskLevel.TRIVIAL,
    "next_best_action":       RiskLevel.TRIVIAL,
    "plan_action":            RiskLevel.TRIVIAL,
    "gap_analysis":           RiskLevel.TRIVIAL,
    "batch_status":           RiskLevel.TRIVIAL,
    "roadmap":                RiskLevel.TRIVIAL,

    # internal writes — LOW (auto approved)
    "update_crm_status":      RiskLevel.LOW,
    "create_lead":            RiskLevel.LOW,
    "update_lead":            RiskLevel.LOW,
    "create_agent":           RiskLevel.LOW,
    "update_agent":           RiskLevel.LOW,
    "log_interaction":        RiskLevel.LOW,
    "store_memory":           RiskLevel.LOW,
    "create_workflow":        RiskLevel.LOW,
    "set_reminder":           RiskLevel.LOW,
    "update_dashboard":       RiskLevel.LOW,
    "build_agent_code":       RiskLevel.LOW,

    # drafts — LOW (draft only, not sent)
    "draft_message":          RiskLevel.LOW,
    "draft_meeting":          RiskLevel.LOW,

    # external / communication — MEDIUM (requires approval)
    "send_whatsapp":          RiskLevel.MEDIUM,
    "send_email":             RiskLevel.MEDIUM,
    "send_sms":               RiskLevel.MEDIUM,
    "external_api_call":      RiskLevel.MEDIUM,
    "publish_content":        RiskLevel.MEDIUM,
    "apply_files":            RiskLevel.MEDIUM,

    # structural / bulk — HIGH
    "delete_agent":           RiskLevel.HIGH,
    "retire_agent":           RiskLevel.HIGH,
    "bulk_send_messages":     RiskLevel.HIGH,
    "change_routing_map":     RiskLevel.HIGH,
    "rollback_agent_version": RiskLevel.HIGH,
    "delete_leads_bulk":      RiskLevel.HIGH,

    # Batch 6 — Goal & Growth Engine (internal writes = LOW, auto approved)
    "set_goal":            RiskLevel.LOW,
    "list_goals":          RiskLevel.TRIVIAL,
    "growth_plan":         RiskLevel.TRIVIAL,
    "outreach_plan":       RiskLevel.LOW,
}


def get_risk(action: str) -> RiskLevel:
    return ACTION_RISK.get(action, RiskLevel.LOW)


def requires_approval(action: str, threshold: int = 3) -> bool:
    return get_risk(action) >= threshold
