"""Persistent idempotent inbox with CAS leases, bounded retries and task traces.

Processing performs local analysis and audit. An opt-in internal CRM note uses a
compare-and-replace request and independent readback. A reclaimed lease can
repeat processing, but the same event marker cannot be appended twice.
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
    except (ValueError, TypeError, KeyError):
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
        return s.execute(update(BusinessEventModel).where(
            BusinessEventModel.id == event_id, BusinessEventModel.business_id == tenant(),
            BusinessEventModel.lease_token == token, BusinessEventModel.status == 'processing',
        ).values(lease_token=None, lease_until=None, **values)).rowcount == 1


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
    ended_at = now().isoformat()
    with get_session() as s:
        stored = s.get(TaskModel, task.id)
        stored.status = 'done' if result.success else 'failed'
        stored.output_data = result.output
        stored.completed_at = ended_at
    if not result.success:
        raise RuntimeError('department_failed')
    return {**result.output, 'task_id': task.id, 'agent_id': agent.agent_id,
            'started_at': task.started_at, 'ended_at': ended_at,
            'input_ref': event['source_ref'], 'source_timestamp': event['occurred_at']}


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
        from services.business_events.departments import ROLES, register_department_experts, roles_for
        register_department_experts()
        trace_id = new_uuid()
        event_scope = event['facts'].get('review_scope')
        departments = {role: _run_role(role, event, context, trace_id)
                       for role in roles_for(event['event_type'], event_scope)}
        from services.integrations.business_source import context_plan
        plan = context_plan(context)
        top = plan['priority_items'][0] if plan['priority_items'] else None
        decision = {'code': 'qualify_supplier' if context.get('capacity_state') != 'confirmed' else 'review_open_work',
                    'summary': plan['top_action'], 'next_action': top,
                    'executed_external_action': False, 'collected_ils': None,
                    'requires_owner_approval': False, 'execution_scope': 'internal_analysis_and_audit_only'}
        if event['event_type'] in {'customer.updated', 'quote.received', 'supplier.updated'}:
            customer_update = event['event_type'] == 'customer.updated'
            supplier_update = event['event_type'] == 'supplier.updated'
            review_code = ('review_customer_work_item' if customer_update else
                           'review_supplier_work_item' if supplier_update else 'review_quote_work_item')
            resolve_code = ('resolve_customer_work_item' if customer_update else
                            'resolve_supplier_work_item' if supplier_update else 'resolve_quote_work_item')
            subject = event['facts'].get('work_item_subject')
            matches = [item for item in context['actions'] if subject and item['subject'] == subject
                       and item.get('kind') == ('supplier' if supplier_update else 'customer')]
            if len(matches) == 1:
                item = matches[0]
                decision.update(code=review_code,
                                summary='לבדוק פנימית את האירוע ברשומה הקיימת ולשמור על מועד המעקב.',
                                next_action={'event_id': event_id, 'code': review_code,
                                             'execution': 'internal_review_only', 'work_item': item})
                if supplier_update:
                    review = {
                        'manufacturing': departments['pricing'].get('manufacturing_comparison'),
                        'installation': departments['operations'].get('installation_estimate_ils_ex_vat'),
                        'market': departments['sales'].get('market_reference_ils_ex_vat'),
                        'scenario': departments['finance'].get('scenario_ils_ex_vat'),
                    }
                    if all(review.values()):
                        decision['supplier_review'] = {**review, 'disposition': 'hold_commitment'}
                        decision['summary'] = ('להמשיך בדיקה פנימית. לפני החלטת התקשרות לאמת הצעת ייצור והתקנה בכתב, '
                                               'להשוות תכולה, לבדוק שקילות לחלופה ולחשב עלות מלאה ותזרים.')
            else:
                decision.update(code=resolve_code,
                                summary='לאמת שיוך ייחודי של האירוע לרשומה קיימת לפני פעולה.',
                                next_action={'event_id': event_id, 'code': resolve_code,
                                             'execution': 'internal_review_only'})
        elif event['event_type'] == 'source.snapshot' and event_scope == 'prospecting':
            if event["facts"].get("snapshot_sha256") != context["snapshot_sha256"]:
                raise ValueError("review_snapshot_changed")
            selection = departments["marketing"]["prospecting"]
            areas = event["facts"].get("areas", [])
            lines = [f"סיננתי {selection['records_read']} רשומות קיימות ב־CRM."
                     f" נמצאו {selection['eligible']} מועמדים לבדיקה פנימית"
                     + (f" לפי אזור: {', '.join(areas)}." if areas else ".")]
            for record in selection["candidates"]:
                lines.append(f"• {record['name']} · {record['area'] or record['city'] or 'אזור לא ידוע'}"
                             f" · {record['stage'] or 'שלב לא ידוע'}")
            lines.append("הצעד הבא: לבדוק שהפרויקט עדיין פעיל ושיש צורך באלומיניום.")
            lines.append("איתור מחוץ ל־CRM דורש מקור חיפוש מחובר או רשימת מועמדים. "
                         "פנייה דורשת אישור נפרד.")
            decision.update(code="screen_existing_prospects", review_scope="prospecting",
                            prospecting=selection, review_message="\n".join(lines))
        elif event['event_type'] == 'source.snapshot' and event['facts'].get('review_scope') in {'portfolio', 'deal', 'deal_priorities'}:
            decision.update(_owner_review(event, context, plan))
        elif event['event_type'] == 'message.received':
            decision.update(code='review_inbound', summary=departments['sales']['summary'],
                            next_action={'event_id': event_id, 'code': 'review_inbound',
                                         'execution': 'draft_for_owner_review_only'},
                            requires_owner_approval=True)
        elif event['event_type'] == 'message.status':
            decision.update(code='reconcile_provider_status', summary=departments['sales']['summary'],
                            next_action={'event_id': event_id, 'code': 'reconcile_provider_status',
                                         'execution': 'reconcile_persisted_evidence_only'})
        auditor = _run_role('auditor', event, context, trace_id, {'departments': departments, 'ceo_decision': decision})
        from services.integrations.crm_writeback import write_review_note
        writeback = (write_review_note(event, context, decision) if auditor['passed']
                     else {'status': 'not_attempted', 'reason': 'audit_rejected'})
        output = {'mode': 'native_deterministic', 'departments': departments, 'ceo_decision': decision,
                  'independent_auditor': auditor, 'source_fingerprint': context['snapshot_sha256'],
                  'not_run_roles': [role for role in ROLES if role not in departments and role != 'auditor'],
                  'source_writeback': writeback,
                  'external_execution': False}
        status = 'analyzed' if auditor['passed'] and writeback['status'] != 'blocked' else 'review_required'
        committed = _finish(event_id, token, status=status, trace_id=trace_id, output=output,
                            next_attempt_at=None, last_error_code=None)
        return {'id': event_id, 'status': status if committed else 'lease_lost', 'trace_id': trace_id}
    except Exception as exc:
        exhausted = event['attempts'] >= MAX_ATTEMPTS
        _finish(event_id, token, status='dead_letter' if exhausted else 'retry',
                last_error_code=type(exc).__name__, next_attempt_at=(clock + dt.timedelta(minutes=2 ** event['attempts'])).isoformat())
        return {'id': event_id, 'status': 'dead_letter' if exhausted else 'retry', 'error_code': type(exc).__name__}



def _owner_review(event, context, plan):
    facts = event["facts"]
    if facts.get("snapshot_sha256") != context["snapshot_sha256"]:
        raise ValueError("review_snapshot_changed")
    subject = facts.get("work_item_subject")
    if subject:
        matches = [item for item in context["actions"] if item["subject"] == subject
                   and item["disposition"] != "completed"]
        if len(matches) != 1:
            raise ValueError("review_subject_not_unique")
        item = matches[0]
        gate = {
            "waiting": "להמתין לפי התנאי הרשום בתור העבודה.",
            "future": "לשמור על מועד המעקב הרשום.",
            "blocked": "לטפל בחסם לפני קידום העסקה.",
            "needs_review": "לאמת את הנתונים החסרים לפני החלטה.",
        }.get(item["disposition"], "לקדם את הצעד המורשה הבא.")
        pilot = item.get("pilot_gate")
        status = item.get("status") or "אין סטטוס מאומת"
        if pilot and pilot["state"] != "ready_for_review":
            gate = "להמשיך בבדיקה פנימית. אין בסיס להתחייבות לפני השלמת בדיקות הרכש, ההתקנה והתזרים."
            status = {"waiting": "ממתין לנתוני רכש, התקנה ותזרים", "stopped": "נעצר לפי בקרת הפיילוט",
                      "unverified": "מצב הפיילוט טרם אומת"}[pilot["state"]]
        lines = [f"מנכ״ל AshbelOS | {subject}", f"החלטה: {gate}",
                 f"מצב מאומת: {status}",
                 f"הצעד הבא: {item['action']}"]
        if item.get("owner") or item.get("due"):
            lines.append(f"אחראי: {item.get('owner') or 'לא תועד'} | מועד: {item.get('due') or 'לא תועד'}")
        lines.append("החלטה פנימית בלבד. לא נשלחה פנייה.")
        return {"code": "owner_deal_review", "summary": gate, "review_message": "\n".join(lines),
                "review_scope": "deal", "next_action": {"work_item": item, "execution": "internal_review_only"}}

    items = [a for a in context["actions"] if a["disposition"] != "completed"]
    counts = {key: sum(a["disposition"] == key for a in items) for key in
              ("actionable", "waiting", "future", "blocked", "needs_review")}
    deals_only = facts.get("review_scope") == "deal_priorities"
    lines = ["מנכ״ל AshbelOS | עסקאות לקידום" if deals_only else "מנכ״ל AshbelOS | תמונת העסק",
             f"תור עבודה: {len(items)} פתוחים. {counts['actionable']} זמינים לקידום, "
             f"{counts['waiting']} בהמתנה, {counts['future']} עתידיים, "
             f"{counts['blocked'] + counts['needs_review']} חסומים או טעוני בדיקה.",
             "גבייה ורווח בפועל טרם אומתו. סכומי הצעה אינם משמשים כגבייה."]
    if deals_only:
        from services.integrations.business_source import context_plan
        deal_context = {**context, "actions": [item for item in items if item["kind"] == "customer"]}
        plan = context_plan(deal_context)
    priorities = plan["priority_items"][:3]
    lines.extend(f"{i}. {item['subject']} — {item['action']}" for i, item in enumerate(priorities, 1))
    if not priorities:
        lines.append("אין עסקה עם צעד זמין לקידום לפי הנתונים המאומתים." if deals_only
                     else "אין בתור צעד שניתן לקדם כעת לפי הנתונים המאומתים.")
    if context["capacity_state"] != "confirmed":
        lines.append("יש לאמת קיבולת ספקים לפני הרחבת לידים.")
    return {"code": "owner_portfolio_review", "summary": plan["top_action"],
            "review_scope": "portfolio", "review_message": "\n".join(lines),
            "work_counts": counts, "priority_items": priorities}


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
