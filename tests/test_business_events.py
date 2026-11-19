"""Real persistent inbox/agent execution; synthetic business records only."""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('ENV', 'test')
from services.business_events import runtime as rt
from services.storage.db import create_all_tables, engine, get_session
from services.storage.models.business_event import BusinessEventModel
from services.storage.models.task import TaskModel


@pytest.fixture(autouse=True)
def database(monkeypatch):
    if engine.url.get_backend_name() != 'sqlite' or engine.url.database != ':memory:':
        pytest.fail('Business event tests require an isolated in-memory SQLite database.')
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


@pytest.mark.parametrize('match_count', (0, 1, 2))
def test_customer_update_uses_only_an_unambiguous_existing_work_item(match_count):
    source = context()
    item = {'subject': 'לקוח סינתטי', 'kind': 'customer', 'disposition': 'future',
            'action': 'מעקב פנימי', 'due_date': '2026-11-19', 'blocked_reasons': [],
            'evidence': {'range': "'תור עבודה'!A3:H3"}}
    source['actions'].extend(item.copy() for _ in range(match_count))
    event = envelope()
    event.update(event_type='customer.updated', facts={'work_item_subject': item['subject']})
    event_id = rt.ingest_event(event)['id']
    assert rt.process_event(event_id, context=source)['status'] == 'analyzed'
    output = rt.get_event(event_id)['output']
    decision = output['ceo_decision']
    assert decision['executed_external_action'] is False
    assert decision['next_action']['execution'] == 'internal_review_only'
    assert output['source_writeback']['status'] == 'not_attempted'
    if match_count == 1:
        assert decision['code'] == 'review_customer_work_item'
        assert decision['next_action']['work_item'] == item
    else:
        assert decision['code'] == 'resolve_customer_work_item'
        assert 'work_item' not in decision['next_action']


@pytest.mark.parametrize('event_type', ('customer.updated', 'quote.received', 'supplier.updated', 'console'))
def test_existing_event_pipeline_writes_and_reads_one_note(event_type, monkeypatch):
    from services.integrations import business_source
    from services.integrations.business_source import WORK_HEADERS, WORK_SECTION_END

    source = context()
    kind = 'supplier' if event_type == 'supplier.updated' else 'customer'
    source['spreadsheet_id'] = 'authorized_workbook_0001'
    source['actions'].append({
        'subject': kind, 'kind': kind, 'disposition': 'future',
        'action': 'internal follow-up', 'due_date': '2026-11-19', 'blocked_reasons': [],
        'evidence': {'range': "'תור עבודה'!A3:H3"},
    })
    rows = [list(WORK_HEADERS), [], [kind, 'next', 'date', 'open', 'owner', 'old note'],
            [WORK_SECTION_END]]
    event = envelope()
    event.update(event_type=event_type, facts={'work_item_subject': kind})
    if kind == 'supplier':
        event['facts']['prices_ils_ex_vat'] = {
            'manufacturing_oral': 20000, 'opening': 23000, 'manufacturing_estimate': 25000,
            'installation_low': 3000, 'installation_high': 4000, 'scenario_sale': 32000,
            'market_quote': 33000, 'market_floor': 31000,
        }
    monkeypatch.setenv('ASHBEL_CRM_WRITEBACK_ENABLED', 'true')
    monkeypatch.setenv('ASHBEL_CRM_WRITEBACK_SOURCE', event['source'])
    monkeypatch.setenv('ASHBEL_SOURCE_SPREADSHEET_ID', source['spreadsheet_id'])
    monkeypatch.setenv('ASHBEL_CRM_WORK_SHEET_ID', '12')
    monkeypatch.setenv('ASHBEL_CRM_WRITEBACK_SERVICE_ACCOUNT_JSON', json.dumps(
        {'type': 'service_account', 'token_uri': 'https://oauth2.googleapis.com/token'}))

    def get(url, **kwargs):
        payload = ({'values': rows} if '/values/' in url else
                   {'sheets': [{'properties': {'title': 'תור עבודה', 'sheetId': 12}}]})
        return Mock(json=Mock(return_value=payload))

    def post(url, *, json, **kwargs):
        request = json['requests'][0]['findReplace']
        assert request['find'] == rows[2][5]
        assert request['range']['startRowIndex'] == 2 and request['range']['startColumnIndex'] == 5
        rows[2][5] = request['replacement']
        return Mock(json=Mock(return_value={'replies': [{'findReplace': {'occurrencesChanged': 1}}]}))

    with patch('google.oauth2.service_account.Credentials.from_service_account_info'), \
         patch('google.auth.transport.requests.AuthorizedSession') as transport:
        session = transport.return_value.__enter__.return_value
        session.get.side_effect = get
        session.post.side_effect = post
        if event_type == 'console':
            from flask import Flask
            from api.routes.commands import bp

            app = Flask(__name__)
            app.register_blueprint(bp, url_prefix='/api')
            client = app.test_client()
            monkeypatch.setenv('OS_API_KEY', 'test-console')
            monkeypatch.setattr(business_source, 'load_business_context', lambda: source)
            headers = {'X-API-Key': 'test-console'}
            url = '/api/command'
            message = {'command': 'עדכון customer: קיבלנו מפרט לבדיקה.', 'mode': 'business_update'}
            assert client.post(url, json=message).status_code == 401
            ambiguous = dict(message, command='יש עדכון עבור customer, ספק סינתטי.')
            assert client.post(url, json=ambiguous, headers=headers).status_code == 422
            assert not rt.recent_events() and session.post.call_count == 0
            response = client.post(url, json=message, headers=headers)
            assert response.status_code == 200
            data = response.get_json()['data']
            assert "מנכ״ל AshbelOS" in data['message'] and data['crm_cell'] == "'תור עבודה'!F3"
            record = rt.get_event(data['event_id'])
            assert record['trace_id'] == data['trace_id']
            assert record['output']['independent_auditor']['passed'] is True
            assert record['output']['departments'] and not record['output']['external_execution']
            assert rows[2][5].count(message['command']) == 1 and 'החלטת מנכ״ל' in rows[2][5]
            again = client.post(url, json=message, headers=headers).get_json()['data']
            assert again['event_id'] == data['event_id'] and again['duplicate'] is True
            session.post.assert_called_once()
            followup = dict(message, command='בנוסף, הגיעו הערות למהנדס.', previous_event_id=data['event_id'])
            assert client.post(url, json=dict(followup, previous_event_id=None), headers=headers).status_code == 422
            result = client.post(url, json=followup, headers=headers)
            assert result.status_code == 200
            continuation = rt.get_event(result.get_json()['data']['event_id'])
            assert continuation['facts']['work_item_subject'] == record['facts']['work_item_subject']
            assert continuation['facts']['owner_update'] == followup['command']
            assert rows[2][5].count(followup['command']) == 1
            unclear = dict(message, command='ההצעה תגיע ביום חמישי.')
            assert client.post(url, json=unclear, headers=headers).status_code == 422
            clarification = dict(message, command='customer', pending_message=unclear['command'])
            result = client.post(url, json=clarification, headers=headers)
            assert result.status_code == 200
            clarified = rt.get_event(result.get_json()['data']['event_id'])
            assert clarified['facts']['owner_update'] == unclear['command']
            assert rows[2][5].count(unclear['command']) == 1
            assert session.post.call_count == 3

            view = dict(message, command='תן לי תמונת מצב של העסק')
            overview = client.post(url, json=view, headers=headers).get_json()['data']
            assert overview['intent'] == 'business_review' and overview['context_event_id'] is None
            record = rt.get_event(overview['event_id'])
            assert record['output']['source_writeback']['status'] == 'not_attempted'
            assert record['output']['independent_auditor']['passed'] is True
            assert record['output']['ceo_decision']['work_counts']['future'] == 1
            assert '2 פתוחים' in overview['message'] and 'טרם אומתו' in overview['message']
            replay = client.post(url, json=view, headers=headers).get_json()['data']
            assert replay['duplicate'] is True and replay['trace_id'] == overview['trace_id']
            priorities = dict(message, command='איזה עסקאות כדאי לקדם היום?')
            result = client.post(url, json=priorities, headers=headers).get_json()['data']
            assert result['event_id'] != overview['event_id']
            assert 'עסקאות לקידום' in result['message'] and 'אין עסקה עם צעד זמין' in result['message']
            deal = dict(message, command='איך לקדם את customer?')
            review = client.post(url, json=deal, headers=headers).get_json()['data']
            assert review['intent'] == 'business_review' and review['context_event_id'] == review['event_id']
            assert 'מועד המעקב' in review['message'] and 'internal follow-up' in review['message']
            next_step = dict(message, command='ומה הצעד הבא?', previous_event_id=review['context_event_id'])
            assert client.post(url, json=next_step, headers=headers).get_json()['data']['event_id'] == review['event_id']
            denied = dict(message, command='תשלח הודעה ללקוח customer')
            assert client.post(url, json=denied, headers=headers).status_code == 403
            assert session.post.call_count == 3
            return

        first = rt.ingest_event(event)
        result = rt.process_event(first['id'], context=source)
        audit = rt.get_event(first['id'])['output']
        assert result['status'] == 'analyzed' and audit['independent_auditor']['passed']
        assert audit['source_writeback'] == {'status': 'verified', 'replayed': False, 'cell': "'תור עבודה'!F3"}
        assert 'marketing' in audit['not_run_roles'] and audit['external_execution'] is False
        assert rt.ingest_event(event)['duplicate']
        assert rt.process_event(first['id'], context=source)['status'] == 'not_claimed'
        session.post.assert_called_once()
        assert session.get.call_count == 3
        assert rows[2][:5] == [kind, 'next', 'date', 'open', 'owner']
        if kind == 'supplier':
            assert {'sales', 'pricing', 'operations', 'procurement', 'engineering', 'finance'} <= audit['departments'].keys()
            review = audit['ceo_decision']['supplier_review']
            assert review['disposition'] == 'hold_commitment'
            assert review['manufacturing']['estimate_gap_pct'] == 20
            assert review['scenario']['gap_before_other_costs'] == [8000, 9000]
            assert all(value in rows[2][5] for value in ('20,000', '3,000–4,000', '8,000–9,000', '0.800'))


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


def test_supplier_event_resolves_existing_procurement_work_item_only(monkeypatch):
    from services.business_events.runtime import ingest_event, process_event, get_event
    from services.integrations import crm_writeback
    monkeypatch.setenv('ASHBEL_CRM_WRITEBACK_ENABLED', 'true')
    monkeypatch.setattr(crm_writeback, 'write_review_note', lambda event, context, decision: {'status': 'verified', 'replayed': False, 'cell': "'תור עבודה'!F16"} if decision.get('code') == 'review_supplier_work_item' else {'status': 'blocked', 'reason': 'wrong_target'})
    context_data = context()
    context_data['actions'] = [{'subject': 'פיילוט קבלן ראשי — רכש ייצור + צוות התקנה', 'kind': 'supplier', 'action': 'השוואה', 'disposition': 'actionable', 'blocked_reasons': [], 'due_date': None, 'evidence': {'range': "'תור עבודה'!A16:H16"}}]
    event = envelope('meeting-imad-yosef-20261118')
    event.update(event_type='supplier.updated', source='owner_internal', source_ref='existing_crm_work_item_16', facts={'work_item_subject': 'פיילוט קבלן ראשי — רכש ייצור + צוות התקנה', 'supplier_meeting': '18.11.2026', 'external_contact_authorized': False})
    e = ingest_event(event)
    assert process_event(e['id'], context=context_data)['status'] == 'analyzed'
    out = get_event(e['id'])['output']
    assert out['ceo_decision']['code'] == 'review_supplier_work_item'
    assert out['source_writeback']['status'] == 'verified'
    assert out['independent_auditor']['passed'] is True
    assert out['external_execution'] is False
    assert len(out['departments']) >= 6
    assert ingest_event(event)['duplicate'] is True
    assert process_event(e['id'], context=context_data)['status'] == 'not_claimed'


def test_owner_discovers_crm_candidates_without_using_call_queue_or_writing(monkeypatch):
    from flask import Flask
    from api.routes import owner_chat
    from routing.model_router import model_router

    source = context()
    base = dict(name="מועמד לדוגמה", area="מרכז", city="רעננה", stage="שלד",
                work_type="חלונות", relevance="חם", range="'לידים'!A2:AE2")
    source["prospect_records"] = [
        dict(base, id="existing-1", status="חדש"),
        dict(base, id="existing-2", status="לא רלוונטי", range="'לידים'!A3:AE3"),
    ]
    monkeypatch.setattr(owner_chat, "load_business_context", lambda: source)
    monkeypatch.setenv("ASHBEL_CRM_WRITEBACK_SOURCE", "owner_internal")
    model = Mock(side_effect=['{"intent":"calls"}', '{"intent":"prospecting","areas":["רעננה"]}'])
    monkeypatch.setattr(model_router, "call_model", model)
    with Flask(__name__).app_context():
        calls, _ = owner_chat.respond("איזה טלפונים כבר ממתינים לי בתור?", {})
        leads, status = owner_chat.respond("תוציא מהמאגר כמה הזדמנויות לחלונות ברעננה", {})
    calls, leads = (response.get_json()["data"] for response in (calls, leads))
    assert "חיוג" in calls["message"]
    assert status == 200 and leads["intent"] == "business_prospecting"
    assert "סיננתי 2" in leads["message"] and "נמצאו 1" in leads["message"]
    assert "מועמד לדוגמה" in leads["message"]
    assert "איתור מחוץ ל־CRM דורש מקור חיפוש מחובר" in leads["message"]
    output = rt.get_event(leads["event_id"])["output"]
    assert output["independent_auditor"]["passed"]
    assert output["external_execution"] is False
    assert output["source_writeback"]["status"] == "not_attempted"
    assert sorted(output["departments"]) == ["knowledge", "marketing", "sales"]
    assert model.call_count == 2
