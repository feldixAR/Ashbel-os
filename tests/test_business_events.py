"""Real persistent inbox/agent execution; synthetic business records only."""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('ENV', 'test')
from services.business_events import runtime as rt
from services.storage.db import create_all_tables, get_session
from services.storage.models.business_event import BusinessEventModel
from services.storage.models.task import TaskModel


@pytest.fixture(autouse=True)
def database(monkeypatch):
    monkeypatch.setenv('BUSINESS_ID', 'ashbel')
    monkeypatch.setenv('ASHBEL_BUSINESS_EVENTS_ENABLED', 'true')
    create_all_tables()
    with get_session() as s:
        s.query(BusinessEventModel).delete()
        s.query(TaskModel).filter_by(type='business_event_department').delete()


def envelope(key='synthetic-1'):
    return dict(source='synthetic_public_source', source_event_id=key, event_type='opportunity.discovered',
                occurred_at='2026-11-16T10:00:00+00:00', source_ref='https://example.invalid/public-project',
                facts={'contact_permission': 'unverified', 'project_stage': 'not_verified'})


def context():
    return dict(health='read_ok', snapshot_sha256='synthetic-context-sha',
                capacity_state='unknown', lead_count=1, work_count=1, decisions=[
                    {'code':'supplier_capacity_unknown', 'instruction':'לאמת קיבולת לפני הרחבת פניות.'}],
                actions=[{'subject':'ספק סינתטי','kind':'supplier','action':'בדיקת ייצור',
                          'disposition':'actionable','blocked_reasons':[],'due_date':None,
                          'evidence':{'range':"'תור עבודה'!A2:H2"}}], source_ranges=["'תור עבודה'!A1:H50"])


def test_idempotency_conflict_and_business_isolation():
    first = rt.ingest_event(envelope())
    assert rt.ingest_event(envelope())['duplicate'] is True
    duplicate = envelope(); duplicate['occurred_at'] = '2026-11-16T12:00:00+00:00'
    assert rt.ingest_event(duplicate)['id'] == first['id']
    changed = envelope();changed['facts']['project_stage'] = 'different'
    with pytest.raises(ValueError, match='source_event_conflict'):
        rt.ingest_event(changed)
    changed = envelope('other');changed['business_id'] = 'other-business'
    with pytest.raises(ValueError, match='wrong_business'):
        rt.ingest_event(changed)
    with patch.dict(os.environ, {'BUSINESS_ID':'other-business'}):
        assert rt.get_event(first['id']) is None


def test_actual_department_execution_preserves_evidence_and_outbound_boundary():
    event = rt.ingest_event(envelope())
    result = rt.process_event(event['id'], context=context())
    assert result['status'] == 'analyzed'
    stored = rt.get_event(event['id'])
    out = stored['output']
    assert out['external_execution'] is False
    assert out['independent_auditor']['passed'] is True
    assert out['departments']['sales']['status'] == 'missing_data'
    assert out['departments']['finance']['financial_truth']['collected_ils'] is None
    assert out['ceo_decision']['code'] == 'qualify_supplier'
    assert out['source_writeback']['status'] == 'not_attempted'
    with get_session() as s:
        tasks = s.query(TaskModel).filter_by(trace_id=result['trace_id']).all()
        assert len(tasks) == len(out['departments']) + 1
        assert all(t.status=='done' and t.model_used=='native_deterministic' for t in tasks)
        assert all('context' not in t.input_data and 'event_id' in t.input_data for t in tasks)
    assert rt.process_event(event['id'], context=context())['status'] == 'not_claimed'


def test_missing_source_blocks_without_consuming_attempts_and_retry_preserves_event():
    eid = rt.ingest_event(envelope())['id']
    clock = dt.datetime.now(dt.timezone.utc)
    assert rt.process_event(eid, context={'health':'unavailable'}, clock=clock)['status']=='blocked'
    assert rt.get_event(eid)['attempts'] == 0
    assert rt.process_event(eid, context=context(), clock=clock+dt.timedelta(minutes=16))['status']=='analyzed'


def test_role_failure_redacted_retries_then_dead_letter():
    eid = rt.ingest_event(envelope())['id']
    clock = dt.datetime.now(dt.timezone.utc)
    with patch.object(rt, '_run_role', side_effect=RuntimeError('SECRET customer data')):
        for i in range(3):
            result = rt.process_event(eid, context=context(), clock=clock+dt.timedelta(minutes=20*i))
    assert result['status']=='dead_letter'
    stored = rt.get_event(eid)
    assert stored['attempts']==3 and stored['last_error_code']=='RuntimeError'
    assert 'SECRET' not in json.dumps(stored)


def test_restart_reclaims_expired_pure_analysis_and_rejects_stale_commit():
    eid = rt.ingest_event(envelope())['id']
    clock = dt.datetime.now(dt.timezone.utc)
    token = rt._claim(eid, clock)
    assert token
    assert rt.process_event(eid, context=context(), clock=clock)['status']=='not_claimed'
    assert rt.process_event(eid, context=context(), clock=clock+dt.timedelta(minutes=6))['status']=='analyzed'
    assert rt._finish(eid, token, status='analyzed', output={'stale':True}) is False
    assert 'stale' not in rt.get_event(eid)['output']


def test_auditor_is_independent_and_rejects_unsafe_ceo_decision():
    from services.business_events.departments import DepartmentExpert
    eid = rt.ingest_event(envelope())['id']
    verdict = DepartmentExpert('auditor').analyze(rt.get_event(eid), context(), {
        'departments':{'finance':{'mode':'native_deterministic','evidence':{'source_ref':'fixture'}}},
        'ceo_decision':{'code':'expand_outreach','executed_external_action':True,'collected_ils':100},
    })
    assert verdict['passed'] is False
    assert set(verdict['violations'])=={'capacity_gate_bypassed','external_execution_not_proven','unproven_collection'}


def test_snapshot_repeat_has_no_duplicate_even_with_different_fetch_time():
    c=context();c.update(spreadsheet_id='synthetic',fetched_at='2026-11-16T10:00:00+00:00')
    first=rt.enqueue_source_snapshot(c)
    c['fetched_at']='2026-11-16T12:00:00+00:00'
    assert rt.enqueue_source_snapshot(c)['id']==first['id']


def test_intake_auth_and_bounded_validation(monkeypatch):
    monkeypatch.setenv('OS_API_KEY','synthetic-key')
    from api.app import create_app
    with patch('scheduler.revenue_scheduler.start'):
        client=create_app().test_client()
    assert client.post('/api/business_events/ingest',json=envelope()).status_code==401
    headers={'X-API-Key':'synthetic-key'}
    assert client.post('/api/business_events/ingest',json=envelope(),headers=headers).status_code==201
    assert client.post('/api/business_events/ingest',json=envelope(),headers=headers).status_code==200
    bad=envelope('bad');bad['occurred_at']='2026-11-16'
    assert client.post('/api/business_events/ingest',json=bad,headers=headers).status_code==400
    monkeypatch.setenv('ASHBEL_BUSINESS_EVENTS_ENABLED','false')
    assert client.get('/api/business_events',headers=headers).status_code==503


def test_adapter_snapshot_routes_to_real_experts():
    from services.integrations.business_source import interpret_snapshot,WORK_HEADERS,LEAD_HEADERS
    payload={'valueRanges':[{'values':[list(LEAD_HEADERS),['דוגמה','s-1','חדש','בדיקה','']]},
             {'values':[list(WORK_HEADERS),['ספק סינתטי','הכשרת ספק','2026-11-16','טרם הוכשרה חלופה','בעלים','','fixture','תפעול'],
                        ['מעקבי לידים']]}]}
    c=interpret_snapshot(payload,'synthetic-sheet-id','2026-11-16T12:00:00+00:00')
    eid=rt.enqueue_source_snapshot(c)['id']
    assert rt.process_event(eid,context=c)['status']=='analyzed'
    assert rt.get_event(eid)['output']['departments']['procurement']['actions'][0]['code']=='qualify_supplier'


def test_multi_process_claims_are_exclusive(tmp_path):
    # Independent engines/processes share a file, as Gunicorn workers do. No
    # global threading lock or mocked session can satisfy this test.
    db=tmp_path/'shared.sqlite'
    base=Path(__file__).resolve().parents[1]
    env={**os.environ,'DATABASE_URL':f'sqlite:///{db}','PYTHONPATH':str(base),'ENV':'test','ENVIRONMENT':'test'}
    setup="""from services.storage.db import create_all_tables
from services.business_events.runtime import ingest_event
create_all_tables()
print(ingest_event(%r)['id'])
""" % envelope()
    eid=subprocess.check_output([sys.executable,'-c',setup],env=env,text=True).strip().splitlines()[-1]
    script="""from services.business_events.runtime import _claim,now
print('won' if _claim(%r,now()) else 'lost')
""" % eid
    workers=[subprocess.Popen([sys.executable,'-c',script],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(6)]
    outputs=[p.communicate(timeout=30)[0].strip().splitlines()[-1] for p in workers]
    assert outputs.count('won')==1 and outputs.count('lost')==5


def test_existing_followup_job_uses_governed_inbox_not_legacy_sender():
    from scheduler.revenue_scheduler import _job_followup
    with patch('services.business_events.runtime.poll_source_and_process', return_value={'results':[]}) as poll, \
         patch('engines.outreach_engine.outreach_engine.run_followup_batch', side_effect=AssertionError('legacy send')):
        assert _job_followup()=={'results':[]}
        poll.assert_called_once()


def test_expired_final_lease_becomes_dead_letter():
    eid=rt.ingest_event(envelope())['id']
    clock=dt.datetime.now(dt.timezone.utc)
    with get_session() as s:
        row=s.get(BusinessEventModel,eid)
        row.status='processing';row.attempts=rt.MAX_ATTEMPTS
        row.lease_until=(clock-dt.timedelta(minutes=1)).isoformat();row.lease_token='crashed'
    rt.process_pending(context=context())
    assert rt.get_event(eid)['status']=='dead_letter'


def test_storage_unavailable_never_invokes_department():
    with patch('services.business_events.runtime.get_session', side_effect=RuntimeError('unavailable')), \
         patch('services.business_events.runtime._run_role') as role:
        with pytest.raises(RuntimeError):
            rt.process_event('synthetic',context=context())
        role.assert_not_called()


def test_inbound_reply_gets_specific_ceo_action_without_automatic_response():
    e=envelope();e['event_type']='message.received'
    eid=rt.ingest_event(e)['id']
    rt.process_event(eid,context=context())
    out=rt.get_event(eid)['output']
    assert out['ceo_decision']['code']=='review_inbound'
    assert out['ceo_decision']['requires_owner_approval'] is True
    assert out['external_execution'] is False and out['independent_auditor']['passed'] is True


def test_healthy_processing_leases_do_not_starve_pending_batch():
    old=rt.ingest_event(envelope('old'))['id']
    assert rt._claim(old,dt.datetime.now(dt.timezone.utc))
    new=rt.ingest_event(envelope('new'))['id']
    results=rt.process_pending(limit=1,context=context())
    assert len(results)==1 and results[0]['id']==new and results[0]['status']=='analyzed'
