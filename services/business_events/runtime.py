"""Persistent idempotent inbox with CAS leases, bounded retries and task traces.

Processing performs local analysis and audit only. No sender, purchase or Google
write API is reachable from this module. A reclaimed lease can repeat pure local
computation; only the current lease can commit its result.
"""
import datetime as dt
import hashlib
import json
import os
import re
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from services.storage.db import get_session
from services.storage.models.business_event import BusinessEventModel
from services.storage.models.base import new_uuid
from services.storage.models.task import TaskModel

EVENT_TYPES = {'opportunity.discovered', 'quote.received', 'supplier.updated',
               'customer.updated', 'message.received', 'message.status', 'source.snapshot'}
MAX_ATTEMPTS = 3


def now():
    return dt.datetime.now(dt.timezone.utc)


def enabled():
    return os.getenv('ASHBEL_BUSINESS_EVENTS_ENABLED', '').lower() == 'true'


def tenant():
    return os.getenv('BUSINESS_ID', 'ashbel')


def _validate(envelope):
    if not isinstance(envelope, dict):
        raise ValueError('invalid_event')
    if envelope.get('business_id', tenant()) != tenant():
        raise ValueError('wrong_business')
    for key, limit in (('source', 120), ('source_event_id', 200), ('source_ref', 2000)):
        if not isinstance(envelope.get(key), str) or not envelope[key].strip() or len(envelope[key]) > limit:
            raise ValueError('invalid_' + key)
    if envelope.get('event_type') not in EVENT_TYPES:
        raise ValueError('invalid_event_type')
    if not isinstance(envelope.get('facts', {}), dict):
        raise ValueError('invalid_facts')
    if len(json.dumps(envelope, ensure_ascii=False, allow_nan=False).encode()) > 65536:
        raise ValueError('event_too_large')
    try:
        stamp = dt.datetime.fromisoformat(envelope['occurred_at'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError()
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError('invalid_occurred_at') from None
    # Received time is distinct from source occurrence time; retain both.
    data = {key: envelope[key].strip() for key in ('source', 'source_event_id', 'source_ref')}
    data.update(business_id=tenant(), event_type=envelope['event_type'],
                occurred_at=stamp.astimezone(dt.timezone.utc).isoformat(), facts=envelope.get('facts', {}))
    return data


def ingest_event(envelope):
    data = _validate(envelope)
    fingerprint_data = {key: value for key, value in data.items() if key != 'occurred_at'}
    fingerprint = hashlib.sha256(json.dumps(fingerprint_data, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()
    row = BusinessEventModel(id=new_uuid(), fingerprint=fingerprint, **data)
    try:
        with get_session() as s:
            s.add(row)
            s.flush()
        return {'id': row.id, 'status': 'pending', 'duplicate': False}
    except IntegrityError:
        with get_session() as s:
            old = s.query(BusinessEventModel).filter_by(business_id=tenant(), source=data['source'], source_event_id=data['source_event_id']).one()
            if old.fingerprint != fingerprint:
                raise ValueError('source_event_conflict') from None
            return {'id': old.id, 'status': old.status, 'duplicate': True}


def get_event(event_id):
    with get_session() as s:
        row = s.query(BusinessEventModel).filter_by(id=event_id, business_id=tenant()).one_or_none()
        return _serialize(row) if row else None


def recent_events(limit=30):
    with get_session() as s:
        rows = s.query(BusinessEventModel).filter_by(business_id=tenant()).order_by(BusinessEventModel.created_at.desc()).limit(min(max(limit, 1), 100)).all()
        return [_serialize(row) for row in rows]


def _serialize(row):
    return {key: getattr(row, key) for key in ('id', 'business_id', 'source', 'source_event_id', 'event_type',
            'source_ref', 'occurred_at', 'fingerprint', 'facts', 'status', 'attempts', 'lease_until',
            'next_attempt_at', 'last_error_code', 'trace_id', 'output')}


def _claim(event_id, clock):
    stamp = clock.isoformat()
    token = new_uuid()
    with get_session() as s:
        allowed = or_(BusinessEventModel.status.in_(['pending', 'retry', 'blocked']),
                      and_(BusinessEventModel.status == 'processing', BusinessEventModel.lease_until < stamp))
        due = or_(BusinessEventModel.next_attempt_at.is_(None), BusinessEventModel.next_attempt_at <= stamp)
        count = s.execute(update(BusinessEventModel).where(
            BusinessEventModel.id == event_id, BusinessEventModel.business_id == tenant(),
            allowed, due, BusinessEventModel.attempts < MAX_ATTEMPTS,
        ).values(status='processing', lease_token=token, lease_until=(clock + dt.timedelta(minutes=5)).isoformat(),
                 attempts=BusinessEventModel.attempts + 1)).rowcount
        if count != 1:
            return None
        return token


def _finish(event_id, token, **values):
    with get_session() as s:
        count = s.execute(update(BusinessEventModel).where(
            BusinessEventModel.id == event_id, BusinessEventModel.business_id == tenant(),
            BusinessEventModel.lease_token == token, BusinessEventModel.status == 'processing',
        ).values(lease_token=None, lease_until=None, **values)).rowcount
        if count == 1 and values.get('status') == 'analyzed' and values.get('output'):
            from services.business_events.work_items import persist_work_items
            row = s.get(BusinessEventModel, event_id)
            output = dict(values['output'])
            ids = persist_work_items(s, _serialize(row), output)
            output['work_item_ids'] = ids
            output['ceo_decision'] = {**output['ceo_decision'], 'work_item_ids': ids}
            # Assign JSON afresh; SQLAlchemy does not track nested mutation.
            row.output = output
        return count == 1


def _run_role(role, event, context, trace_id, previous=None):
    from agents.base.agent_registry import agent_registry
    from services.business_events.departments import DepartmentExpert, role_contract
    agent = agent_registry.find('business_event_department', role)
    if not isinstance(agent, DepartmentExpert) or agent.role != role:
        raise RuntimeError('department_not_registered')
    # One persisted task per actual invocation, including retries, gives honest
    # execution traces without pretending repeated computation is a new event.
    task = TaskModel(id=new_uuid(), type='business_event_department', action=role, status='running',
                     agent_id=agent.agent_id, trace_id=trace_id, started_at=now().isoformat(),
                     input_data={'event_id': event['id'], 'source_ref': event['source_ref'],
                                 'context_fingerprint': context.get('snapshot_sha256'),
                                 'contract': role_contract(role)},
                     model_used='native_deterministic', risk_level=1)
    with get_session() as s:
        s.add(task)
    task.input_data = {'event': event, 'context': context, 'previous': previous or {}}
    result = agent.execute(task)
    with get_session() as s:
        stored = s.get(TaskModel, task.id)
        stored.status = 'done' if result.success else 'failed'
        stored.output_data = result.output
        stored.completed_at = now().isoformat()
    if not result.success:
        raise RuntimeError('department_failed')
    return {**result.output, 'task_id': task.id, 'agent_id': agent.agent_id}


def process_event(event_id, context=None, clock=None):
    clock = clock or now()
    token = _claim(event_id, clock)
    if not token:
        return {'id': event_id, 'status': 'not_claimed'}
    event = get_event(event_id)
    try:
        if context is None:
            from services.integrations.business_source import load_business_context
            context = load_business_context()
        if context.get('health') != 'read_ok' or not context.get('snapshot_sha256'):
            _finish(event_id, token, status='blocked', last_error_code='business_source_unavailable',
                    attempts=max(0, event['attempts'] - 1), next_attempt_at=(clock + dt.timedelta(minutes=15)).isoformat())
            return {'id': event_id, 'status': 'blocked', 'reason': 'business_source_unavailable'}
        from services.business_events.departments import register_department_experts, roles_for
        register_department_experts()
        trace_id = new_uuid()
        departments = {role: _run_role(role, event, context, trace_id) for role in roles_for(event['event_type'])}
        from services.integrations.business_source import context_plan
        plan = context_plan(context)
        top = plan['priority_items'][0] if plan['priority_items'] else None
        decision = {'code': 'qualify_supplier' if context.get('capacity_state') != 'confirmed' else 'review_open_work',
                    'summary': plan['top_action'], 'next_action': top,
                    'executed_external_action': False, 'collected_ils': None,
                    'requires_owner_approval': False, 'execution_scope': 'internal_analysis_and_audit_only'}
        if event['event_type'] == 'message.received':
            decision.update(code='review_inbound', summary=departments['sales']['summary'],
                            next_action={'event_id': event_id, 'code': 'review_inbound',
                                         'execution': 'draft_for_owner_review_only'},
                            requires_owner_approval=True)
        elif event['event_type'] == 'message.status':
            decision.update(code='reconcile_provider_status', summary=departments['sales']['summary'],
                            next_action={'event_id': event_id, 'code': 'reconcile_provider_status',
                                         'execution': 'reconcile_persisted_evidence_only'})
        auditor = _run_role('auditor', event, context, trace_id, {'departments': departments, 'ceo_decision': decision})
        output = {'mode': 'native_deterministic', 'departments': departments, 'ceo_decision': decision,
                  'independent_auditor': auditor, 'source_fingerprint': context['snapshot_sha256'],
                  'source_writeback': {'status': 'not_attempted', 'reason': 'read_only_runtime'},
                  'external_execution': False}
        status = 'analyzed' if auditor['passed'] else 'review_required'
        committed = _finish(event_id, token, status=status, trace_id=trace_id, output=output,
                            next_attempt_at=None, last_error_code=None)
        return {'id': event_id, 'status': status if committed else 'lease_lost', 'trace_id': trace_id}
    except Exception as exc:
        exhausted = event['attempts'] >= MAX_ATTEMPTS
        _finish(event_id, token, status='dead_letter' if exhausted else 'retry',
                last_error_code=type(exc).__name__, next_attempt_at=(clock + dt.timedelta(minutes=2 ** event['attempts'])).isoformat())
        return {'id': event_id, 'status': 'dead_letter' if exhausted else 'retry', 'error_code': type(exc).__name__}


def process_pending(limit=20, context=None):
    stamp = now().isoformat()
    with get_session() as s:
        s.execute(update(BusinessEventModel).where(
            BusinessEventModel.business_id == tenant(), BusinessEventModel.status == 'processing',
            BusinessEventModel.lease_until < stamp, BusinessEventModel.attempts >= MAX_ATTEMPTS,
        ).values(status='dead_letter', lease_token=None, lease_until=None, last_error_code='lease_exhausted'))
        rows = s.query(BusinessEventModel.id).filter(
            BusinessEventModel.business_id == tenant(),
            or_(BusinessEventModel.status.in_(['pending', 'retry', 'blocked']),
                and_(BusinessEventModel.status == 'processing', BusinessEventModel.lease_until < stamp)),
            or_(BusinessEventModel.next_attempt_at.is_(None), BusinessEventModel.next_attempt_at <= stamp),
        ).order_by(BusinessEventModel.created_at).limit(min(max(limit, 1), 50)).all()
        ids = [row[0] for row in rows]
    return [process_event(event_id, context=context) for event_id in ids]


def enqueue_source_snapshot(context):
    if context.get('health') != 'read_ok' or not context.get('snapshot_sha256'):
        return None
    return ingest_event({'source': 'existing_google_crm', 'source_event_id': context['snapshot_sha256'],
                         'event_type': 'source.snapshot', 'source_ref': context.get('spreadsheet_id', 'existing_crm'),
                         'occurred_at': context['fetched_at'],
                         'facts': {'snapshot_sha256': context['snapshot_sha256'], 'lead_count': context['lead_count'],
                                   'work_count': context['work_count']}})


def poll_source_and_process():
    """Existing scheduled job entry: read sources and drain persisted events."""
    if not enabled():
        return {'status': 'disabled'}
    from services.integrations.business_source import load_business_context
    context = load_business_context()
    enqueue_source_snapshot(context)
    return {'source_health': context.get('health'), 'results': process_pending(context=context)}
