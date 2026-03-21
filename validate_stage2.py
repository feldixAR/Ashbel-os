"""
validate_stage2.py — Stage 2 Batch 1 validation script.

Usage:
    pip install -r requirements.txt
    python validate_stage2.py

Tests:
    1. IntentResult — correct intent + param extraction
    2. Created Task  — full object from TaskManager
    3. DB write      — task exists in real SQLAlchemy / SQLite DB
    4. Event emitted — TASK_CREATED captured from EventBus
"""

import os
import sys
import json

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Ensure data/ directory exists ─────────────────────────────────────────────
os.makedirs("data", exist_ok=True)

COMMAND = "תרשום ליד חדש יוסי כהן מתל אביב 0501234567"
PASS = "✅"
FAIL = "❌"
SEP  = "═" * 60

results = {}


# ─────────────────────────────────────────────────────────────────────────────
# STEP 0: Initialize database
# ─────────────────────────────────────────────────────────────────────────────
print(SEP)
print("0. DATABASE INIT")
print(SEP)

from services.storage.db import create_all_tables, health_check
create_all_tables()
db_ok = health_check()
print(f"  {'✅' if db_ok else '❌'}  DB reachable: {db_ok}")
print()

if not db_ok:
    print("FATAL: database not reachable — aborting.")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Bootstrap event system
# ─────────────────────────────────────────────────────────────────────────────
from events.event_dispatcher import bootstrap
from events.event_bus        import event_bus
import events.event_types    as ET

bootstrap()

# Capture TASK_CREATED events during this run
captured_events: list = []

def _capture(event_type: str, payload: dict, meta: dict) -> None:
    captured_events.append({
        "event_type": event_type,
        "payload":    payload,
        "meta":       meta,
    })

event_bus.subscribe(ET.TASK_CREATED, _capture)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Parse intent
# ─────────────────────────────────────────────────────────────────────────────
print(SEP)
print("1. INTENT RESULT")
print(SEP)

from orchestration.intent_parser import intent_parser, Intent

ir = intent_parser.parse(COMMAND)

print(f"  command    : {COMMAND!r}")
print(f"  intent     : {ir.intent}")
print(f"  confidence : {ir.confidence}")
print(f"  parse_path : {ir.parse_path}")
print(f"  params     :")
for k, v in ir.params.items():
    print(f"    {k:<12}: {v!r}")

intent_ok     = ir.intent == Intent.ADD_LEAD
confidence_ok = ir.confidence >= 0.9
name_ok       = ir.params.get("name")  == "יוסי כהן"
city_ok       = ir.params.get("city")  == "תל אביב"
phone_ok      = ir.params.get("phone") == "0501234567"

print()
print(f"  {PASS if intent_ok     else FAIL}  intent == add_lead")
print(f"  {PASS if confidence_ok else FAIL}  confidence >= 0.9")
print(f"  {PASS if name_ok       else FAIL}  name  == 'יוסי כהן'")
print(f"  {PASS if city_ok       else FAIL}  city  == 'תל אביב'")
print(f"  {PASS if phone_ok      else FAIL}  phone == '0501234567'")

results["intent"] = all([intent_ok, confidence_ok, name_ok, city_ok, phone_ok])
print()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Create task via TaskManager
# ─────────────────────────────────────────────────────────────────────────────
print(SEP)
print("2. CREATED TASK")
print(SEP)

import uuid
from orchestration.task_manager import task_manager

trace_id = str(uuid.uuid4())

task = task_manager.create_task(
    type="crm",
    action="update_crm_status",
    input_data={
        "command": COMMAND,
        "intent":  ir.intent,
        "params":  ir.params,
    },
    priority=5,
    trace_id=trace_id,
)

print(f"  task_id    : {task.id}")
print(f"  type       : {task.type}")
print(f"  action     : {task.action}")
print(f"  priority   : {task.priority}")
print(f"  status     : {task.status}")
print(f"  risk_level : {task.risk_level}")
print(f"  trace_id   : {task.trace_id}")
print(f"  input_data :")
for k, v in (task.input_data or {}).items():
    if k == "params":
        for pk, pv in v.items():
            print(f"    params.{pk:<8}: {pv!r}")
    else:
        print(f"    {k:<14}: {v!r}")

task_ok = bool(task.id)
print()
print(f"  {PASS if task_ok else FAIL}  task object created with id")
results["task_created"] = task_ok
print()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: Confirm DB write
# ─────────────────────────────────────────────────────────────────────────────
print(SEP)
print("3. DB WRITE CONFIRMATION")
print(SEP)

from services.storage.repositories.task_repo import TaskRepository

task_repo = TaskRepository()
db_task   = task_repo.get(task.id)

if db_task:
    print(f"  {PASS}  Task found in DB")
    print(f"  id         : {db_task.id}")
    print(f"  type       : {db_task.type}")
    print(f"  action     : {db_task.action}")
    print(f"  status     : {db_task.status}")
    print(f"  risk_level : {db_task.risk_level}")
    print(f"  created_at : {db_task.created_at}")
    params_in_db = (db_task.input_data or {}).get("params", {})
    print(f"  name       : {params_in_db.get('name')!r}")
    print(f"  city       : {params_in_db.get('city')!r}")
    print(f"  phone      : {params_in_db.get('phone')!r}")
    db_ok_write = True
else:
    print(f"  {FAIL}  Task NOT found in DB (id={task.id})")
    db_ok_write = False

results["db_write"] = db_ok_write
print()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5: Confirm event emitted
# ─────────────────────────────────────────────────────────────────────────────
print(SEP)
print("4. TASK_CREATED EVENT")
print(SEP)

task_events = [
    e for e in captured_events
    if e["event_type"] == ET.TASK_CREATED
]

if task_events:
    e = task_events[0]
    print(f"  {PASS}  Event emitted: {e['event_type']}")
    print(f"  payload    :")
    for k, v in e["payload"].items():
        print(f"    {k:<12}: {v!r}")
    print(f"  trace_id   : {e['meta'].get('trace_id')!r}")
    event_ok = e["payload"].get("task_id") == task.id
    print()
    print(f"  {PASS if event_ok else FAIL}  payload.task_id matches created task")
else:
    print(f"  {FAIL}  TASK_CREATED event NOT captured")
    event_ok = False

results["event_emitted"] = event_ok
print()


# ─────────────────────────────────────────────────────────────────────────────
# FINAL VERDICT
# ─────────────────────────────────────────────────────────────────────────────
print(SEP)
print("VALIDATION SUMMARY")
print(SEP)

labels = {
    "intent":        "1. Intent parsed correctly",
    "task_created":  "2. Task object created",
    "db_write":      "3. Task written to DB",
    "event_emitted": "4. TASK_CREATED event emitted",
}

all_passed = True
for key, label in labels.items():
    ok = results.get(key, False)
    all_passed = all_passed and ok
    print(f"  {'✅' if ok else '❌'}  {label}")

print()
if all_passed:
    print("  ✅  ALL CHECKS PASSED — ready for Batch 2")
else:
    print("  ❌  SOME CHECKS FAILED — do not proceed")
print(SEP)

sys.exit(0 if all_passed else 1)
