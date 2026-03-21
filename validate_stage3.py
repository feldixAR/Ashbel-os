"""
validate_stage3.py

Tests:
    1. AgentRegistry bootstraps with built-in agents
    2. Routing: all task types match expected agents
    3. Stage 2 backward compat — add_lead still works
    4. LeadQualifierAgent scores leads + emits LEAD_SCORED
    5. MessagingAgent generates message + emits MESSAGE_GENERATED
    6. CEOAgent handles strategy/analysis
    7. GenericTaskAgent catches unknown task types

Usage:
    python validate_stage3.py
"""

import os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.makedirs("data", exist_ok=True)

PASS_ = "✅"
FAIL_ = "❌"
SEP   = "═" * 60
results = {}

# ── 0. Bootstrap ──────────────────────────────────────────────────────────────
print(SEP)
print("0. BOOTSTRAP")
print(SEP)

from services.storage.db     import create_all_tables, health_check
from events.event_dispatcher import bootstrap
from events.event_bus        import event_bus
import events.event_types    as ET

create_all_tables()
assert health_check(), "DB not reachable"
bootstrap()

captured = []
def _cap(et, payload, meta):
    captured.append({"event_type": et, "payload": payload})

for ev in [ET.TASK_CREATED, ET.TASK_COMPLETED, ET.LEAD_CREATED,
           ET.LEAD_SCORED, ET.MESSAGE_GENERATED]:
    event_bus.subscribe(ev, _cap)

from agents.base.agent_registry import agent_registry
count = agent_registry.count()
print(f"  {PASS_ if count > 0 else FAIL_}  AgentRegistry: {count} agents registered")
for a in agent_registry.list_agents():
    print(f"    • {a.name:<30} dept={a.department}")
print()
results["bootstrap"] = count > 0

# ── 1. Routing ────────────────────────────────────────────────────────────────
print(SEP)
print("1. ROUTING")
print(SEP)

cases = [
    ("scoring",       "score_lead",        "LeadQualifierAgent"),
    ("sales",         "generate_content",  "MessagingAgent"),
    ("strategy",      "complex_reasoning", "CEOAgent"),
    ("analysis",      "analyze_market",    "CEOAgent"),
    ("summarization", "generate_report",   "CEOAgent"),
    ("unknown",       "unknown",           "GenericTaskAgent"),
]

routing_ok = True
for tt, action, expected in cases:
    agent = agent_registry.find(tt, action)
    got   = agent.__class__.__name__ if agent else "None"
    ok    = got == expected
    routing_ok = routing_ok and ok
    print(f"  {PASS_ if ok else FAIL_}  ({tt:<14}, {action:<22}) → {got}")

results["routing"] = routing_ok
print()

# ── 2. Stage 2 backward compat ────────────────────────────────────────────────
print(SEP)
print("2. BACKWARD COMPAT — add_lead (Stage 2 flow)")
print(SEP)

from orchestration.orchestrator import orchestrator
captured.clear()
r = orchestrator.handle_command("תוסיף ליד רחל לוי מחיפה טלפון 0521111111")
lead_events = [e for e in captured if e["event_type"] == ET.LEAD_CREATED]
compat_ok   = r.success and len(lead_events) > 0
print(f"  {PASS_ if r.success   else FAIL_}  orchestrator success")
print(f"  {PASS_ if lead_events else FAIL_}  LEAD_CREATED emitted")
results["stage2_compat"] = compat_ok
print()

# ── 3. LeadQualifier ─────────────────────────────────────────────────────────
print(SEP)
print("3. LEAD QUALIFIER — score_leads")
print(SEP)

captured.clear()
r2 = orchestrator.handle_command("דרג את כל הלידים")
scored_events = [e for e in captured if e["event_type"] == ET.LEAD_SCORED]
qual_ok       = r2.success and len(scored_events) > 0
print(f"  {PASS_ if r2.success         else FAIL_}  success={r2.success} message={r2.message!r}")
print(f"  {PASS_ if len(scored_events) > 0 else FAIL_}  LEAD_SCORED events: {len(scored_events)}")
results["lead_qualifier"] = qual_ok
print()

# ── 4. MessagingAgent ─────────────────────────────────────────────────────────
print(SEP)
print("4. MESSAGING AGENT — generate_content")
print(SEP)

captured.clear()
from orchestration.task_manager import task_manager

task = task_manager.create_task(
    type="sales", action="generate_content",
    input_data={"command": "כתוב הודעה",
                "intent": "generate_message",
                "params": {"name": "משה ישראלי", "city": "תל אביב", "attempts": 0}},
    priority=2, trace_id=str(uuid.uuid4()),
)
res       = task_manager.dispatch(task)
msg_events = [e for e in captured if e["event_type"] == ET.MESSAGE_GENERATED]
msg_ok     = res.get("success") and "message" in res.get("output", {})
print(f"  {PASS_ if res.get('success') else FAIL_}  dispatch success")
print(f"  {PASS_ if msg_ok            else FAIL_}  output has 'message'")
print(f"  {PASS_ if msg_events        else FAIL_}  MESSAGE_GENERATED emitted ({len(msg_events)})")
if msg_ok:
    print(f"  preview: {res['output']['message'][:80]}...")
results["messaging"] = msg_ok and bool(msg_events)
print()

# ── 5. CEOAgent ───────────────────────────────────────────────────────────────
print(SEP)
print("5. CEO AGENT — market_analysis")
print(SEP)

r3     = orchestrator.handle_command("ניתוח שוק האלומיניום בישראל")
ceo_ok = r3.success and r3.intent == "market_analysis"
print(f"  {PASS_ if ceo_ok else FAIL_}  success={r3.success} intent={r3.intent}")
results["ceo_agent"] = ceo_ok
print()

# ── 6. Generic fallback ───────────────────────────────────────────────────────
print(SEP)
print("6. GENERIC FALLBACK")
print(SEP)

fallback = agent_registry.find("totally_unknown", "totally_unknown")
fb_ok    = fallback.__class__.__name__ == "GenericTaskAgent"
print(f"  {PASS_ if fb_ok else FAIL_}  unknown → GenericTaskAgent")
results["fallback"] = fb_ok
print()

# ── Summary ───────────────────────────────────────────────────────────────────
print(SEP)
print("VALIDATION SUMMARY")
print(SEP)

labels = {
    "bootstrap":     "1. AgentRegistry bootstrapped with built-in agents",
    "routing":       "2. All routing cases correct",
    "stage2_compat": "3. Stage 2 add_lead flow still works",
    "lead_qualifier":"4. LeadQualifier scores leads + emits LEAD_SCORED",
    "messaging":     "5. MessagingAgent generates + emits MESSAGE_GENERATED",
    "ceo_agent":     "6. CEOAgent handles strategy/analysis",
    "fallback":      "7. GenericTaskAgent catches unknown tasks",
}

all_passed = True
for key, label in labels.items():
    ok = results.get(key, False)
    all_passed = all_passed and ok
    print(f"  {'✅' if ok else '❌'}  {label}")

print()
print(f"  {'✅  ALL CHECKS PASSED — Stage 3 complete' if all_passed else '❌  SOME CHECKS FAILED'}")
print(SEP)
sys.exit(0 if all_passed else 1)
