"""PostgreSQL integration proof using a disposable CI service only.

Normal local runs skip this module. Never point TEST_POSTGRES_URL at business data.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[1]
POSTGRES_URL = os.getenv("TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="disposable PostgreSQL service not configured")


def worker_env():
    assert POSTGRES_URL.startswith("postgresql://")
    return {**os.environ, "DATABASE_URL": POSTGRES_URL,
            "ENVIRONMENT": "test", "ENV": "test", "PYTHONPATH": str(ROOT),
            "BUSINESS_ID": "synthetic-postgres-ci",
            "ASHBEL_BUSINESS_EVENTS_ENABLED": "true",
            "ASHBEL_SOURCE_CONTEXT_ENABLED": "false"}


def run(code):
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                            env=worker_env(), capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()[-1]


def compete(code, count=6):
    workers = [subprocess.Popen([sys.executable, "-c", code], cwd=ROOT, env=worker_env(),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
               for _ in range(count)]
    outputs = []
    for process in workers:
        out, err = process.communicate(timeout=60)
        assert process.returncode == 0, err
        outputs.append(json.loads(out.strip().splitlines()[-1]))
    return outputs


@pytest.fixture(scope="module", autouse=True)
def initialize_disposable_database():
    if POSTGRES_URL:
        run("""from services.storage.db import engine, create_all_tables
assert engine.dialect.name == 'postgresql'
create_all_tables()
print('postgresql schema ready')
""")


def test_postgres_concurrent_inbox_insert_claim_restart_and_stale_worker():
    key = "synthetic-postgres-" + uuid.uuid4().hex
    envelope = dict(source="synthetic_ci", source_event_id=key,
                    source_ref="https://example.invalid/ci",
                    occurred_at="2026-11-17T00:00:00+00:00",
                    event_type="opportunity.discovered", facts={"contact_permission": "unverified"})
    results = compete("""import json
from services.business_events.runtime import ingest_event
print(json.dumps(ingest_event(%r)))
""" % envelope)
    assert len({result["id"] for result in results}) == 1
    assert sum(not result["duplicate"] for result in results) == 1
    eid = results[0]["id"]
    claims = compete("""import json
from services.business_events.runtime import _claim, now
print(json.dumps(_claim(%r, now())))
""" % eid)
    tokens = [token for token in claims if token]
    assert len(tokens) == 1
    context = dict(health="read_ok", snapshot_sha256=key, capacity_state="unknown",
                   lead_count=1, work_count=0, actions=[], decisions=[], source_ranges=[])
    # A new interpreter simulates restart. Expire the original lease, perform
    # actual role execution, then prove the old worker cannot replace the output.
    result = json.loads(run("""import datetime as dt, json
from services.storage.db import get_session
from services.storage.models.business_event import BusinessEventModel
from services.business_events.runtime import process_event, get_event, _finish, ingest_event, now
with get_session() as session:
    row = session.get(BusinessEventModel, %r)
    row.lease_until = (now() - dt.timedelta(minutes=1)).isoformat()
result = process_event(%r, context=%r)
assert result['status'] == 'analyzed', result
assert _finish(%r, %r, status='analyzed', output={'stale': True}) is False
stored = get_event(%r)
assert 'stale' not in stored['output']
assert stored['output']['independent_auditor']['passed'] is True
assert stored['output']['external_execution'] is False
assert ingest_event(%r)['duplicate'] is True
assert process_event(%r, context=%r)['status'] == 'not_claimed'
print(json.dumps({'status': result['status'], 'duplicate': True, 'stale_worker_rejected': True}))
""" % (eid, eid, context, eid, tokens[0], eid, envelope, eid, context)))
    assert result == dict(status="analyzed", duplicate=True, stale_worker_rejected=True)


def test_postgres_scheduled_occurrence_is_claimed_once_across_processes():
    job = "synthetic-pg-scheduler-" + uuid.uuid4().hex
    script = """import datetime as dt, json
from scheduler.job_claim import run_scheduled_once
result = run_scheduled_once(%r, lambda: {'executed': True},
                           dt.datetime(2026, 11, 17, tzinfo=dt.timezone.utc))
print(json.dumps(result))
""" % job
    results = compete(script)
    assert sum(result == {"executed": True} for result in results) == 1
    replay = json.loads(run(script))
    assert "already_claimed" in json.dumps(replay)


def test_postgres_two_events_share_one_stable_followup_set_under_worker_concurrency():
    project = "synthetic-concurrent-work-" + uuid.uuid4().hex
    base_event = dict(source="synthetic_work_ci", source_ref="https://example.invalid/ci-work",
                      occurred_at="2026-11-17T01:00:00+00:00", event_type="opportunity.discovered",
                      facts={"project_id": project, "contact_permission": "unverified"})
    events = [{**base_event, "source_event_id": project + "-" + str(i)} for i in range(2)]
    ids = json.loads(run("""import json
from services.business_events.runtime import ingest_event
print(json.dumps([ingest_event(event)['id'] for event in %r]))
""" % events))
    context = dict(health="read_ok", snapshot_sha256="synthetic", capacity_state="unknown",
                   lead_count=1, work_count=0, actions=[], decisions=[], source_ranges=[])
    outputs = compete("""import json
from services.business_events.runtime import process_pending
print(json.dumps(process_pending(context=%r)))
""" % context)
    analyzed = [row for rows in outputs for row in rows if row['status'] == 'analyzed']
    assert {row['id'] for row in analyzed} == set(ids)
    assert len(analyzed) == 2
    assert all(row['status'] in {'analyzed', 'not_claimed'} for rows in outputs for row in rows)
    count = int(run("""from services.storage.db import get_session
from services.storage.models.task import TaskModel
with get_session() as session:
    rows = session.query(TaskModel).filter(
        TaskModel.type == 'business_work_item',
        TaskModel.input_data['entity_ref'].as_string() == %r).all()
    assert all(row.status != 'done' for row in rows)
    print(len(rows))
""" % project))
    assert count == 8
