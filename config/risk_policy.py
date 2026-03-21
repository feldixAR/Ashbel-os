"""
Risk policy — maps every system action to a risk level (1–5).
Actions at or above AUTO_APPROVE_BELOW_RISK require human approval.
"""
from enum import IntEnum


class RiskLevel(IntEnum):
    TRIVIAL   = 1   # read-only, generate draft
    LOW       = 2   # write to internal DB
    MEDIUM    = 3   # external communication, create agent
    HIGH      = 4   # delete, structural change, bulk action
    CRITICAL  = 5   # financial, legal, irreversible


# action_name → RiskLevel
ACTION_RISK: dict[str, RiskLevel] = {
    # reads
    "read_data":                RiskLevel.TRIVIAL,
    "generate_content":         RiskLevel.TRIVIAL,
    "score_lead":               RiskLevel.TRIVIAL,
    "generate_report":          RiskLevel.TRIVIAL,
    "analyze_market":           RiskLevel.TRIVIAL,
    "benchmark_models":         RiskLevel.TRIVIAL,

    # internal writes
    "update_crm_status":        RiskLevel.LOW,
    "create_agent":             RiskLevel.LOW,
    "update_agent":             RiskLevel.LOW,
    "log_interaction":          RiskLevel.LOW,
    "store_memory":             RiskLevel.LOW,
    "create_workflow":          RiskLevel.LOW,

    # external / communication
    "send_whatsapp":            RiskLevel.MEDIUM,
    "send_email":               RiskLevel.MEDIUM,
    "send_sms":                 RiskLevel.MEDIUM,
    "external_api_call":        RiskLevel.MEDIUM,
    "publish_content":          RiskLevel.MEDIUM,

    # structural / bulk
    "delete_agent":             RiskLevel.HIGH,
    "retire_agent":             RiskLevel.HIGH,
    "bulk_send_messages":       RiskLevel.HIGH,
    "change_routing_map":       RiskLevel.HIGH,
    "rollback_agent_version":   RiskLevel.HIGH,
    "delete_leads_bulk":        RiskLevel.HIGH,

    # financial / legal
    "financial_decision":       RiskLevel.CRITICAL,
    "contract_action":          RiskLevel.CRITICAL,
    "pricing_change":           RiskLevel.CRITICAL,
    "system_config_change":     RiskLevel.CRITICAL,
}


def get_risk(action: str) -> RiskLevel:
    return ACTION_RISK.get(action, RiskLevel.LOW)


def requires_approval(action: str, threshold: int = 3) -> bool:
    return get_risk(action) >= threshold
